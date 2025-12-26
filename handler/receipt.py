import os
import logging
import tempfile
from typing import List, Dict, Any

# Third-party imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from consts import UNDEFINED
import receipt.product as Pdt
from receipt.qrcode import QRCodeProcessor
from receipt.webscrapping import WebScraper

logger = logging.getLogger(__name__)


class ReceiptBot:
    """Main Telegram bot for receipt processing"""

    def __init__(self):
        self.user_sessions = {}
        
    async def read_receipt(self,update,temp_path):
        user_id = update.message.from_user.id

        # Detect QR codes
        qr_codes = QRCodeProcessor.detect_qr_codes(temp_path)
        
        if not qr_codes:
            await update.message.reply_text("❌ Não foram encontrados QR Code na imagem enviada, certifique-se da qualidade.")
            os.unlink(temp_path)
            return
        
        # Get first QR code that's a URL
        valid_qr = next((qr for qr in qr_codes if qr['is_url']), None)
        if not valid_qr:
            await update.message.reply_text("❌ Não há uma URL válida no QR Code enontrado.")
            os.unlink(temp_path)
            return
        
        qr_url = valid_qr['data']
        await update.message.reply_text(f"🌐 Recibo encontrado: [fazenda.mg.gov]({qr_url})\n\nAnalisando items...",parse_mode='Markdown')
        
        # Scrape receipt items
        items = WebScraper().scrape_receipt_items(qr_url)
        
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
        await self.send_item_selection(update, user_id, items)
    
    async def select_items(self, update: Update, user_id: int, data):
        query = update.callback_query

        if user_id not in self.user_sessions: # self.user_sessions is not global
            await query.edit_message_text("Session expired. Please send a new QR code.")
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
        
        elif data == "cancel":
            # Cancel operation
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
            await query.edit_message_text("Operação cancelada.")
        
    async def send_item_selection(self, update: Update, user_id: int, items: List[Dict]):
        """Send interactive message for item selection"""
        if not items:
            await update.message.reply_text("No items found to display.")
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
        user = update.effective_user.username
        selected_items = [item for item in items if item.selected]

        try:
            if not selected_items:
                await update.callback_query.edit_message_text(
                    "Nenhum item selecionado."
                )
                return
            
            # Create TXT content
            txt_content = "🛒 *Items salvos*: \n"           
            total = 0
            for i, item in enumerate(selected_items, 1):
                txt_content += f"{i}. {item.product_name}\n"
                txt_content += f"Qtd.: {item.quantity} {item.unity} "
                txt_content += f"Preço: R$ {item.price}\n\n"

                if item.owner == UNDEFINED:
                    item.owner = user
                
                # Try to extract numeric price for total
                try:
                    price_clean = item.price.replace('R$', '').replace(',', '.').strip()
                    price_num = float(price_clean)
                    total += price_num
                except:
                    pass
            
            if total > 0:
                txt_content += f"Total: R$ {total:.2f}\n"
            
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
            
            await update.callback_query.edit_message_text(txt_content)
            
        except Exception as e:
            logger.error(f"Error saving items: {e}")
            await update.callback_query.edit_message_text(
                "❌ Ocorreu um erro ao tentar salvar os items."
            )

    async def get_product_data(self, update: Update):
        #Send file to user
        try:
            with open(Pdt.PRODUCT_DIR, 'rb') as file:
                await update.message.reply_document(
                    document=file,
                    filename="compras.csv",
                    caption=f"Aqui está o .csv!"
                )
        except Exception as e:
            logger.error(f"Error sending file: {e}")
            await update.message.reply_text(
                "❌ Ocorreu um erro ao enviar o arquivo."
            )
    
    async def products_sumup(self, update: Update):
        """
            25/07:{Otavio:12,Enzo:45}
        """
        try:
            items = {}
            messsage = '🛒 *Resumo das Últimas Compras*\n'
            for pdt in Pdt.load_products():
                date = pdt.date.strftime("%d/%m")
                owner = pdt.owner
                if not date in items: items[date] = {}
                if not owner in items[date]: items[date][owner] = 0
                items[date][owner] += pdt.price

            for date,owners in items.items():
                messsage += f'\[{date}]\n'
                for o,v in owners.items():
                    messsage += f'{o}: R$ {v}\n'
                messsage += '\n'

            await update.message.reply_text(messsage, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error during the products sumup file: {e}")
            await update.message.reply_text(
                "❌ Ocorreu um erro ao preparar resumo das compras."
            )