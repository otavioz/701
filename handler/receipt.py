import os
import logging
import tempfile
import calendar
import html
from typing import List, Dict, Any
from datetime import datetime
from urllib.parse import urlparse

# Third-party imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from consts import PRODUCT_DIR, TRANSFERS_DIR, DATABASE
from src.database import DatabaseManager
from src.user_session import UserSessionManager
from receipt.ocr import TesseractOCR
from receipt.pix import Pix
from receipt.product import Product
from receipt.qrcode import QRCodeProcessor
from receipt.webscrapping import WebScraper
from src.utils import save_img_bkp



logger = logging.getLogger(__name__)


class ReceiptBot:
    """Main Telegram bot for receipt processing"""

    def __init__(self):
        self.user_sessions = UserSessionManager()
        self.db = DatabaseManager(DATABASE)

    async def read_image(self,update): #,temp_path):
        # Download photo
        photo_file = await update.message.photo[-1].get_file()
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_path = temp_file.name
        
        await photo_file.download_to_drive(temp_path)

        # Detect QR codes
        qr_codes = QRCodeProcessor.detect_qr_codes(temp_path)
        
        user_id = update.message.from_user.id
        self.user_sessions.get_or_create(user_id, {
            'items': None,
            'selected_items': [],
            'pix': None,
            'temp_path': temp_path
        })
            
        if qr_codes:
            await self.read_receipt(update,qr_codes)
            os.unlink(temp_path)
            return
        
        #await update.message.reply_text("Não foi encontrado um QR Code na imagem enviada, analisando comprovantes.")
        receipt = TesseractOCR.extract_from_image(temp_path,save_raw=True)

        if receipt:
            await self.read_transaction(update,temp_path,receipt)
            os.unlink(temp_path)
            return
        
        #await update.message.reply_text("❌ Não identificamos QRCodes ou Comprovantes na imagem, certifique-se da qualidade.")

        # Download photo again
        photo_file = await update.message.photo[-1].get_file()

        # Add action buttons
        message_text = (
            'Não identificamos QRCodes ou Comprovantes na imagem, certifique-se da qualidade.\n'
            'Caso o envio seja de um QR Code, você pode lê-lo e enviar a URL resultante aqui. Ou ainda, pode solicitar inserção manual, salvando a imagem.')
        
        keyboard = [[
            InlineKeyboardButton("Salvar Imagem", callback_data="save_backup"),
            InlineKeyboardButton("Cancelar", callback_data="cancel_")
        ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)

        #os.unlink(temp_path)
        await update.message.reply_text(message_text, parse_mode='Markdown', reply_markup=reply_markup)

    async def read_url(self,update,qr_url):
        user_id = update.message.from_user.id
        await self.read_receipt(update,url_link=qr_url)

    
    async def read_transaction(self,update,temp_path,receipt: Pix):
        user_id = update.message.from_user.id

        message_text = (
            '💲 *Comprovante Salvo!*\n\n'
            f'Valor de: R$ {receipt.value:.2f}\n'
            f'De: {receipt.from_} \n'
            f'Para: {receipt.to_}\n'
            f'Realizado em: {receipt.date_.strftime("%d/%m/%Y %H:%M:%S")}')
        
        self.user_sessions.update(user_id, text=message_text)
        # Add action buttons
        keyboard = [[
            #InlineKeyboardButton("📝 Finalizar", callback_data="save_pix"),
            InlineKeyboardButton("❌ Tem algo errado", callback_data="adjust_pix")
        ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)

        #Save PIX
        receipt.doc_id = self.db.create_pix(receipt)
        self.user_sessions.update(user_id, pix=receipt)

        #os.unlink(temp_path)
        await update.message.reply_text(message_text,
                                         parse_mode='Markdown',
                                         reply_markup=reply_markup)

    async def read_receipt(self,update,qr_codes=None,url_link=None):
        user_id = update.message.from_user.id

        if not qr_codes and not url_link:
            await update.message.reply_text("URL ou QR Code não encontrado.")
            return

        if qr_codes:
            # Get first QR code that's a URL
            valid_qr = next((qr for qr in qr_codes if qr['is_url']), None)
            if not valid_qr:
                await update.message.reply_text("❌ Não há uma URL válida no QR Code enontrado.")
                return
            url_link = valid_qr['data']
        
        domain = urlparse(url_link).netloc
        await update.message.reply_text(f"🌐 Recibo encontrado: [{domain}]({url_link})\n\nAnalisando items...",parse_mode='Markdown')

        webscrapper = WebScraper()

        # Get URL Datakey
        url_datakey = webscrapper.get_datakey(url_link)
        if not url_datakey:
            await update.message.reply_text("Serviço da Receita Federal indisponível, tente novamente mais tarde!")
            return

        #Get Captcha Token
        token = webscrapper.get_captcha_token(url_link,url_datakey)
        if not token:
            await update.message.reply_text("Serviço de CAPTCHA indisponível, tente mais tarde!")
            return

        #Scrape webiste
        page = webscrapper.get_page_with_token(url_link, token)
        if not page:
            await update.message.reply_text("❌ Não foi possivel encontrar items em seu recibo, tente novamente mais tarde.")
            return

        #Get items from the page
        items = webscrapper.scrap_items(page, user_id)
        if not items:
            await update.message.reply_text("Erro na leitura dos items do recibo, tente novamente mais tarde.")
            return
        
        # Store items in user session
        self.user_sessions.set(user_id, {
            'items': items,
            'selected_items': []
        })

        # Send items for selection
        await self.send_item_selection(update, user_id, items)
    
    async def select_items(self, update: Update, user_id: int, data):
        query = update.callback_query

        session = self.user_sessions.get(user_id)
        if session is None:
            await query.edit_message_text("Sessão expirada, inicie novamente.")
            return
        
        items = session['items']
        
        if data.startswith("select_"):
            # Select item
            item_index = int(data.split("_")[1])
            if 0 <= item_index < len(items):
                items[item_index].selected = True
                await self.send_item_selection(update, user_id, items)
        
        elif data.startswith("deselect_"):
            # Deselect item
            item_index = int(data.split("_")[1])
            if 0 <= item_index < len(items):
                items[item_index].selected = False
                await self.send_item_selection(update, user_id, items)
        
        elif data == "confirm_save":
            # Save selected items
            await self.save_selected_items(update, user_id, items)
        
        elif data == "cancel_":
            # Cancel operation
            self.user_sessions.remove(user_id)
            await query.edit_message_text("Operação cancelada.")
        
        elif data == "save_pix":
            # Save transaction on file
            pix = session.get('pix')
            text = session.get('text')
            if pix is None or text is None:
                await query.edit_message_text("Sessão expirada, inicie novamente.")
                return
            self.user_sessions.remove(user_id)
            #pix.save()
            self.db.create_pix(pix)
            await query.edit_message_text(f'Transação salva!\n{text}',parse_mode='Markdown')

        elif data == "adjust_pix":
            # Save with exceptions
            pix = session.get('pix')
            if pix is None:
                await query.edit_message_text("Sessão expirada, inicie novamente.")
                return
            self.user_sessions.remove(user_id)
            pix.correction()
            self.db.update_pix_object(pix.doc_id,pix)
            message = query.message.text + "\n\n<i>Operação marcada para revisão manual.</i>"
            await query.edit_message_text(message)
            #await query.edit_message_text("Feito! Operação foi marcada para revisão manual.")


    async def clean_file(self, update: Update, user_id: int, data):
        query = update.callback_query

        if data == "clean_file_2":
            Pix.backup_file()
            await query.edit_message_caption("Arquivo limpo.")
        elif data == "clean_file":
            Product.backup_file()
            await query.edit_message_caption("Arquivo limpo.")
        elif data == 'save_backup':
            #Product.backup_file() #TODO MEIORA ISSO
            session = self.user_sessions.get(user_id)
            if session is not None and 'temp_path' in session:
                temp_path = session['temp_path']
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    save_img_bkp(temp_path,user_id)
                    os.unlink(temp_path)
                    return await query.edit_message_caption("Imagem salva para avaliação manual posterior.")
                return await query.edit_message_caption("Imagem não foi encontrada, gentileza enviar novamente.")
            return await query.edit_message_caption("Sessão expirada, inicie novamente.")
        elif data == "keep_":
            # Cancel operation
            self.user_sessions.remove(user_id)
            await query.edit_message_caption("Feito!")
    
        
    async def send_item_selection(self, update: Update, user_id: int, items: List[Dict]):
        """Send interactive message for item selection"""
        if not items:
            await update.message.reply_text("Nenhum item foi selecionado!.")
            return
        
        # Create keyboard with items
        keyboard = []
        for i, item in enumerate(items):
            checkbox = "✅" if item.selected else ""
            # Truncate if too long
            item_text = f"{item.product_name} - R${item.price}"
            if len(item_text) > 25:
                item_text = f"{item.product_name[:22]}... - R$ {item.price}"
            
            callback_data = f"deselect_{i}" if item.selected else f"select_{i}"
            keyboard.append([InlineKeyboardButton(
                f"{checkbox} {item_text}",
                callback_data=callback_data
            )])
        
        # Add action buttons
        keyboard.append([
            InlineKeyboardButton("📝 Salvar Items", callback_data="confirm_save"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel_")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = (
            "🛒 *Selecione os items a serem salvos:*\n\n"
            "Clique no item para selecionar/deselecionar.\n"
            "Quado finalizar clique em 'Salvar Items'."
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message_text, 
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    async def save_selected_items(self, update: Update, user_id: int, items: List[Product]):
        """Save selected items to TXT file"""
        selected_items = [item for item in items if item.selected]

        try:
            if not selected_items:
                await update.callback_query.edit_message_text(
                    "Nenhum item selecionado."
                )
                return
            
            # Create TXT content
            txt_content = "🛒 *Items salvos*:\n\n"           
            total = 0
            for i, item in enumerate(selected_items, 1):
                txt_content += f"  {i}. {item.product_name}\n"
                txt_content += f"  Qtd.: {item.quantity:.2f} {item.unity} - R$ {item.price}\n\n"
                #txt_content += f"  Preço: R$ {item.price}\n"
                
                # Try to extract numeric price for total
                try:
                    total += item.price
                except:
                    pass
            
            if total > 0:
                txt_content += f"*Total*: R$ {total:.2f}"
            
            # Save items on csv
            #Product.save_products(selected_items)
            for product in selected_items:
                self.db.create_product(product)

            # Save to temporary file
            #with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
            #    f.write(txt_content)
            #    temp_path = f.name
            
            # Send file to user
            #with open(temp_path, 'rb') as file:
            #    await update.callback_query.message.reply_document(
            #        document=file,
            #        filename="receipt_items.txt",
            #        caption=f"✅ Saved {len(selected_items)} items to file!"
            #    )
            
            # Cleanup
            #os.unlink(temp_path)
            
            self.user_sessions.remove(user_id)
            
            await update.callback_query.edit_message_text(txt_content, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error saving items: {e}")
            await update.callback_query.edit_message_text(
                "❌ Ocorreu um erro ao tentar salvar os items."
            )

    async def get_product_data(self, update: Update):
        #Send file to user
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("🧹 Limpar Arquivo", callback_data="clean_file"),
            InlineKeyboardButton("📝 Manter", callback_data="keep_")
        ]])
 
        try:
            with open(PRODUCT_DIR, 'rb') as file:
                await update.message.reply_document(
                    document=file,
                    reply_markup=reply_markup,
                    filename="compras.csv",
                    caption=f"Aqui está o arquivo! Gostaria de limpá-lo?"
                )
        except Exception as e:
            logger.error(f"Error sending file: {e}")
            await update.message.reply_text(
                "❌ Ocorreu um erro ao enviar o arquivo."
            )
      
    async def get_receipts(self, update: Update):
        #Send file to user
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("🧹 Limpar Arquivo", callback_data="clean_file_2"),
            InlineKeyboardButton("📝 Manter", callback_data="keep_")
        ]])
 
        try:
            with open(TRANSFERS_DIR, 'rb') as file:
                await update.message.reply_document(
                    document=file,  
                    reply_markup=reply_markup,
                    filename="recibos.csv",
                    caption=f"Aqui está o arquivo! Gostaria de limpá-lo?"
                )
        except Exception as e:
            logger.error(f"Error sending file: {e}")
            await update.message.reply_text(
                "❌ Ocorreu um erro ao enviar o arquivo."
            )  
    async def products_sumup(self, update: Update):
        try:
            now = datetime.now()
            period_start = datetime(now.year, now.month, 1)
            period_end = datetime(
                now.year,
                now.month,
                calendar.monthrange(now.year, now.month)[1],
                23, 59, 59, 999999,
            )
            products = sorted(
                (
                    product for product in self.db.get_all_products()
                    if period_start <= product.date <= period_end
                ),
                key=lambda product: (product.date, str(product.product_name).casefold()),
            )

            month_name = (
                "janeiro", "fevereiro", "março", "abril", "maio", "junho",
                "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
            )[now.month - 1].capitalize()
            lines = [f"<b>Compras de {month_name}/{now.year}</b>"]
            total = sum(product.price for product in products)

            if products:
                for product in products:
                    lines.extend([
                        "",
                        f"<b>{html.escape(str(product.product_name))}</b>",
                        f"Data: {product.date.strftime('%d/%m/%Y %H:%M')}",
                        f"Responsável: {html.escape(str(product.owner))}",
                        #f"Quantidade: {product.quantity:g} {html.escape(str(product.unity))}",
                        f"Valor: R$ {product.price:.2f}",
                        #f"Código: {html.escape(str(product.code))}",
                        f"Loja: {html.escape(str(product.shop))}",
                        #f"Chave de acesso: {html.escape(str(product.access_key or '—'))}",
                    ])
                lines.extend(["", f"<b>Total: R$ {total:.2f}</b>"])
            else:
                lines.append("Nenhum produto encontrado neste mês.")

            for message in self._split_summary_messages(lines):
                await update.effective_message.reply_text(message)

        except Exception as e:
            logger.error(f"Error during the products sumup file: {e}")
            await update.effective_message.reply_text(
                "❌ Ocorreu um erro ao preparar resumo das compras."
            )

    @staticmethod
    def _split_summary_messages(lines: List[str], limit: int = 3800) -> List[str]:
        messages = []
        current = ""
        for line in lines:
            candidate = f"{current}\n{line}" if current else line
            if len(candidate) > limit and current:
                messages.append(current)
                current = line
            else:
                current = candidate
        if current:
            messages.append(current)
        return messages