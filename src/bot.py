"""
Main Telegram bot for receipt processing
"""
from functools import wraps
import os
import tempfile
import logging
import traceback
from typing import Dict, List, Any
from datetime import timedelta, datetime, timezone
from telegram.constants import ParseMode

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters, Defaults
)
from src.config import get_permitted_users, set_permitted_user
from handler.receipt import ReceiptBot

#https://core.telegram.org/bots/api#formatting-options

class AP701Bot:
    """Main Telegram bot for receipt processing"""
    
    def __init__(self, telegram_token: str, admin_chat_id: str = None):
        self.token = telegram_token
        self.admin_chat_id = admin_chat_id
        
        # Setup application
        defaults = Defaults(parse_mode=ParseMode.HTML, tzinfo=timezone(timedelta(hours=-3))) #tzinfo.timezone('America/Sao_Paulo'))
        #persistence = PicklePersistence(filepath="db/conversationbot")

        self.application = Application.builder().token(self.token).defaults(defaults).build()
                
        # User sessions
        self.user_sessions = {}
        self.session_timeout = 3600
        
        # Setup handlers
        self._setup_handlers()
        self.receipt = ReceiptBot()
        
        # Add error handler
        self.application.add_error_handler(self.error_handler)
        
        self.logger = logging.getLogger(__name__)
    
    def _setup_handlers(self):
        """Setup all bot handlers"""
        handlers = [
            CommandHandler("start", self._safe_handler(self.start_command)),
            CommandHandler("help", self._safe_handler(self.help_command)),
            CommandHandler("qr", self._safe_handler(self.read_qrcode)),
            CommandHandler("lproducts", self._safe_handler(self.download_products)),
            CommandHandler("sumup", self._safe_handler(self.products_sumup)),
            CommandHandler("bills", self._safe_handler(self.monthly_bills)),
            CommandHandler("add", self._safe_handler(self.add_user)),
            MessageHandler(filters.PHOTO, self._safe_handler(self.handle_photo)),
            #MessageHandler(filters.Document.IMAGE, self._safe_handler(self.handle_document_image)),
            CallbackQueryHandler(
                self._safe_handler(self.handle_product_click), 
                pattern="^(select_|deselect_|confirm_|cancel_)"
            ),
            CallbackQueryHandler(
                self._safe_handler(self.handle_product_file), 
                pattern="^(clean_file|keep_)"
            ),
             MessageHandler(filters.TEXT & ~filters.COMMAND, self.echo)
        ]
        
        for handler in handlers:
            self.application.add_handler(handler)
    def _safe_handler(self, handler_func):
        """Decorator to safely wrap handler functions"""
        async def wrapped_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            try:
                user_id = update.effective_user.id
                permitted_users = get_permitted_users()
                #self._clean_expired_sessions()
                if user_id not in permitted_users:
                    self.logger.warning("Unauthorized access denied for {}.".format(user_id))
                    return await update.message.reply_text("Usuário \<{}> não autorizado!".format(user_id), parse_mode='Markdown')
                self._log_user_interaction(update)
                return await handler_func(update, context)
            except Exception as e:
                self.logger.error(f"Handler error: {e}")
                await self.error_handler(update, context)
        
        return wrapped_handler
    
    #def restricted(func):
    #    @wraps(func)
    #    async def wrapped(self, update: Update, context: ContextTypes, *args, **kwargs):
    #        user_id = update.effective_user.id
    #        permitted_users = get_permitted_users()
    #        if user_id not in permitted_users:
    #            #print("Unauthorized access denied for {}.".format(user_id))
    #            self.logger.warning("Unauthorized access denied for {}.".format(user_id))
    #            await update.message.reply_text("Usuário não autorizado!", parse_mode='Markdown')
    #            return
    #        await func(self, update, context, *args, **kwargs)
    #        return
    #    return wrapped

    async def echo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat.type not in ['group', 'supergroup']:
            welcome_text = f"Não entendi! Digite /help para ver uma lista de funcionalidades do bot."
            await update.message.reply_text(welcome_text, parse_mode='Markdown')

    #@restricted
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
       
        welcome_text = f"""
        *Bot do 701*
        
        Utilize /help para mais informações!

        Criado por: Otávio V.
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')

    #@restricted
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log the error and send a telegram message to notify the developer."""
        # Log the error before we do anything else, so we can see it even if something breaks.
        self.logger.error("Exception while handling an update:", exc_info=context.error)

        #tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        #message = (f"Warning: \n{html.escape(tb_list[-1]).split(':')[-1]}")
        #chat_id = update.message.chat.id
        # Finally, send the message
         # Optionally, send a message to the user
        if update.effective_message:
            await update.effective_message.reply_text(
                "Opa! Algo deu errado! Contate o adminstrador."
            )
        #await context.bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.HTML)

    #@restricted
    async def products_sumup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.receipt.products_sumup(update)

    #@restricted
    async def monthly_bills(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = f"🚧 Ainda em Construção 🚧"

        await update.message.reply_text(text, parse_mode='Markdown')

    #@restricted
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo messages containing QR codes"""
        user_id = update.message.from_user.id
        try:
            await update.message.reply_text("🔍 Procurando QR Code...")
            
            # Download photo
            photo_file = await update.message.photo[-1].get_file()
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                temp_path = temp_file.name
            
            await photo_file.download_to_drive(temp_path)
            await self.receipt.read_receipt(update,temp_path)
            
        except Exception as e:
            self.logger.error(f"Error processing photo: {e}")
            await update.message.reply_text("❌ Houve um erro durante o processamento da sua imagem, tente novamente.")
        finally:
            # Cleanup
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)

    #@restricted
    async def read_qrcode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Para começar é só enviar uma foto da nota fiscal com o QR  visível.\n"
        "Ao enviar uma foto irei:\n"
        "   1. 📱 Escanear o QR para encontrar as compras feitas através portal da Fazenda.\n"
        "   2. 📋 Extrair os items comprados.\n"
        "   4. ✅ E ai, *você* seleciona quais os items fazem parte das dispesas da casa.\n"
        "   5. 🛒 Os items são salvos automaticamente na planilha de gastos.", parse_mode='Markdown')

    #@restricted
    async def download_products(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.receipt.get_product_data(update)


    #@restricted
    async def add_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.text.replace('/add','').strip()
        try:
            user_id = float(user_id)
            if not user_id:
                await update.message.reply_text("Para adicionar um usuário envie o texto _/add userid_", parse_mode='Markdown')
                return
            set_permitted_user(user_id)
            await update.message.reply_text("Usuário {} adicionado a lista de usuários permitidos!".format(user_id))
        except ValueError:
            await update.message.reply_text("Certifique-se se enviar o ID do usuário!\n _{}_ Não é um ID válido.".format(user_id))

    #@restricted
    async def handle_product_click(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button clicks"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        await self.receipt.select_items(update, user_id, data)
    
    #@restricted
    async def handle_product_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button clicks"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        await self.receipt.clean_file(update, user_id, data)

    #@restricted
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
        🏳‍🌈 *Bot do 701* 🏢
                       
        *Comandos:*
        /qr ou foto enviada: 
            Extrairei as compras feitas pelo QRCode.
        
        /lproducts:
            Retorna um _.csv_ contendo todos as compras realizadas no mês por todos os moradores.
        
        /sumup:
            Lista um resumo das ultimas compras feitas, contendo *Data*, *Autor* e *Valor Total*.

        /bills: \[🚧 Breve 🚧]
            Lista os valores das contas da casa, bem como o saldo em conta da casa e dos moradores.
            
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    def _log_user_interaction(self, update: Update):
        """Log user interactions"""
        user = update.effective_user
        if user:
            self.logger.info(f"User {user.username} ({user.id}) - Action")
    
    def run(self):
        """Start the bot"""
        self.logger.info("Starting bot...")
        self.application.run_polling()