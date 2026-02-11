import os
import logging
import tempfile
from typing import List, Dict, Any
from urllib.parse import urlparse

# Third-party imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from consts import PRODUCT_DIR, UNDEFINED
from receipt.ocr import TesseractOCR
from receipt.pix import Pix
import receipt.product as Pdt
from receipt.qrcode import QRCodeProcessor
from receipt.webscrapping import WebScraper

logger = logging.getLogger(__name__)


class ReceiptBot:
    """Main Telegram bot for receipt processing"""

    def __init__(self):
        self.user_sessions = {}

    async def read_image(self,update,temp_path):
        # Detect QR codes
        qr_codes = QRCodeProcessor.detect_qr_codes(temp_path)
        
        user_id = update.message.from_user.id
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                'items': None,
                'selected_items': [],
                'pix': None
            }
            
        if qr_codes:
            await self.read_receipt(update,temp_path,qr_codes)
            return
        
        await update.message.reply_text("Não foi encontrado um QR Code na imagem enviada, analisando comprovantes.")
        receipt = TesseractOCR.extract_from_image(temp_path,save_raw=True)

        if receipt:
            await self.read_transaction(update,temp_path,receipt)
            return
        
        os.unlink(temp_path)
        await update.message.reply_text("❌ Não identificamos QRCodes ou Comprovantes na imagem, certifique-se da qualidade.")
    
    async def read_transaction(self,update,temp_path,receipt: Pix):
        user_id = update.message.from_user.id

        #receipt.save()
        self.user_sessions[user_id]['pix'] = receipt

        message_text = (
            '💲 *Comprovante de Transferência/Pagamento:*\n\n'
            f'Valor de: R$ {receipt.value:.2f}\n'
            f'De: {receipt.from_} \n'
            f'Para: {receipt.to_}\n'
            f'Realizado em: {receipt.date_.strftime("%d/%m/%Y %H:%M:%S")}')
        
        # Add action buttons
        keyboard = [[
            InlineKeyboardButton("📝 Salvar", callback_data="save_pix"),
            InlineKeyboardButton("❌ Tem algo errado", callback_data="adjust_pix")
        ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)

        os.unlink(temp_path)
        await update.message.reply_text(message_text,
                                         parse_mode='Markdown',
                                         reply_markup=reply_markup)


    async def read_receipt(self,update,temp_path,qr_codes):
        user_id = update.message.from_user.id
        
        # Get first QR code that's a URL
        valid_qr = next((qr for qr in qr_codes if qr['is_url']), None)
        if not valid_qr:
            await update.message.reply_text("❌ Não há uma URL válida no QR Code enontrado.")
            os.unlink(temp_path)
            return
        
        qr_url = valid_qr['data']
        domain = urlparse(qr_url).netloc
        await update.message.reply_text(f"🌐 Recibo encontrado: [{domain}]({qr_url})\n\nAnalisando items...",parse_mode='Markdown')
        
        # Scrape receipt items
        items = WebScraper().scrape_receipt_items(qr_url, user_id)
        
        if not items:
            await update.message.reply_text("❌ Não foi possivel encontrar items em seu recibo.")
            os.unlink(temp_path)
            return
        
        # Store items in user session
        self.user_sessions[user_id] = {
            'items': items,
            'selected_items': []
        }
        # Send items for selection
        os.unlink(temp_path)
        await self.send_item_selection(update, user_id, items)
    
    async def select_items(self, update: Update, user_id: int, data):
        query = update.callback_query

        if user_id not in self.user_sessions: # self.user_sessions is not global
            await query.edit_message_text("Sessão expirada, inicie novamente.")
            return
        
        items = self.user_sessions[user_id]['items']
        
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
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
            await query.edit_message_text("Operação cancelada.")
        
        elif data == "save_pix":
            # Save transaction on file
            pix = self.user_sessions[user_id]['pix']
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
            pix.save()
            await query.edit_message_text("Feito!")

        elif data == "adjust_pix":
            # Save with exceptions
            pix = self.user_sessions[user_id]['pix']
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
            pix.correction()
            pix.save()
            await query.edit_message_text("Foi inserido um aviso para validação manual dos dados.")


    async def clean_file(self, update: Update, user_id: int, data):
        query = update.callback_query

        #if user_id not in self.user_sessions: # self.user_sessions is not global
        #    return await query.edit_message_text("Sessão expirada, inicie novamente.")

        if data == "clean_file":
            # Cancel operation
            Pdt.backup_file()
            await query.edit_message_caption("Arquivo limpo.")
        elif data == "keep_":
            # Cancel operation
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
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
    
    async def save_selected_items(self, update: Update, user_id: int, items: List[Pdt.Product]):
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
            Pdt.save_products(selected_items)

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
            
            # Clear user session
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
            
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
            InlineKeyboardButton("📝 Manter", callback_data="keep_2")
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
    async def products_sumup(self, update: Update):
        try:
            items = {}
            messsage = '📈 *Resumo das Últimas Compras:*\n\n'
            total = 0
            for pdt in Pdt.load_products():
                date = pdt.date.strftime("%d/%m")
                owner = pdt.owner
                if not date in items: items[date] = {}
                if not owner in items[date]: items[date][owner] = 0
                items[date][owner] += pdt.price
                total += pdt.price

            for date,owners in items.items():
                messsage += f'\[{date}]\n'
                for o,v in owners.items():
                    messsage += f'{o}: R$ {v:.2f}\n'
                messsage += '\n'

            if total > 0:
                messsage += f"\n*Total*: R$ {total:.2f}"

            await update.message.reply_text(messsage, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error during the products sumup file: {e}")
            await update.message.reply_text(
                "❌ Ocorreu um erro ao preparar resumo das compras."
            )