"""
Main Telegram bot for receipt processing
"""
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
            MessageHandler(filters.PHOTO, self._safe_handler(self.handle_photo)),
            #MessageHandler(filters.Document.IMAGE, self._safe_handler(self.handle_document_image)),
            CallbackQueryHandler(
                self._safe_handler(self.handle_button_click), 
                pattern="^(select_|deselect_|confirm_|cancel_)"
            ),
             MessageHandler(filters.TEXT & ~filters.COMMAND, self.echo)
        ]
        
        for handler in handlers:
            self.application.add_handler(handler)
    def _safe_handler(self, handler_func):
        """Decorator to safely wrap handler functions"""
        async def wrapped_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            try:
                #self._clean_expired_sessions()
                self._log_user_interaction(update)
                return await handler_func(update, context)
            except Exception as e:
                self.logger.error(f"Handler error: {e}")
                await self.error_handler(update, context)
        
        return wrapped_handler
    
    async def echo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_text = f"Não entendi! Digite /help para ver uma lista de funcionalidades do bot."

        await update.message.reply_text(welcome_text, parse_mode='Markdown')

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
       
        welcome_text = f"""
        🛒 **Bot do 701** 🛒
                       
        **Comandos:**
        /qr ou foto enviada: 
            Ao enviar uma foto de uma nota fiscal com o QR visível irei:
            1. 📱 Scanear o QR para encontrar as compras feitas no portal da Fazenda.
            2. 📋 Extrairei os items comprados.
            4. ✅ Você seleciona quais os items fazem parte das dispesas da casa.
            5. 🛒 Os items são salvos automaticamente na planilha de gastos.
        
        /lproducts:
            Retorna um _.csv_ contendo todos as compras realizadas no mês por todos os moradores.
        
        /sumup:
            Lista um resumo das ultimas compras feitas, contendo **Data**, **Autor** e **Valor Total**.

        /bills: [🚧 Ainda em Construção 🚧]
            Lista os valores das contas da casa, bem como o saldo em conta da casa e dos moradores.
            
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')

    async def error_handler(self,update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log the error and send a telegram message to notify the developer."""
        # Log the error before we do anything else, so we can see it even if something breaks.
        logging.error("Exception while handling an update:", exc_info=context.error)

        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        #message = (f"Warning: \n{html.escape(tb_list[-1]).split(':')[-1]}")
        #chat_id = update.message.chat.id
        # Finally, send the message
         # Optionally, send a message to the user
        if update.effective_message:
            await update.effective_message.reply_text(
                "Opa! Algo deu errado! Contate o adminstrador."
            )
        #await context.bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.HTML)

    async def products_sumup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.receipt.products_sumup(update)

    async def monthly_bills(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = f"🚧 Ainda em Construção 🚧"

        await update.message.reply_text(text, parse_mode='Markdown')

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

    async def read_qrcode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Para começar é só enviar uma foto da nota fiscal com o QR  visível.")

    async def download_products(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.receipt.get_product_data(update)

    async def handle_button_click(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button clicks"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        await self.receipt.select_items(update, user_id, data)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
        🏳‍🌈 **Bot do 701** 🏢
                       
        **Comandos:**
        /qr ou foto enviada: 
            Ao enviar uma foto de uma nota fiscal com o QR visível irei:
            1. 📱 Scanear o QR para encontrar as compras feitas no portal da Fazenda.
            2. 📋 Extrairei os items comprados.
            4. ✅ Você seleciona quais os items fazem parte das dispesas da casa.
            5. 🛒 Os items são salvos automaticamente na planilha de gastos.
        
        /lproducts:
            Retorna um _.csv_ contendo todos as compras realizadas no mês por todos os moradores.
        
        /sumup:
            Lista um resumo das ultimas compras feitas, contendo **Data**, **Autor** e **Valor Total**.

        /bills: [🚧 Ainda em Construção 🚧]
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