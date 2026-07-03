from itertools import product
import json
import logging
import os
import re
from datetime import datetime
import re
from typing import Dict
from bs4 import BeautifulSoup as BS

from consts import PRODUCT_DIR, UNDEFINED, USERS_DIR
from src.utils import get_users

#PRODUCTS_FILEHEADER = 'product_name;code;quantity;unity;price;date;shop;owner;datetime'
PRODUCTS_FILEHEADER = 'product_name;price;owner;date;code;quantity;unity;shop;datetime;reference_year;reference_month'

class Product():
    def __init__(self, product_name, quantity, unity, price, owner, shop, 
                 code=None, date=None, formatted=False,
                 reference_year=None, reference_month=None,doc_id=None):
        
        #Basics attrs
        self.formatted = formatted
        self.product_name = self._set_name(product_name)
        self.code = self._set_code(code, product_name)
        self.quantity = self._set_quantity(quantity)
        self.unity = self._set_unity(unity)
        self.price = self._set_amount(price)
        self.owner = self._set_owner(owner)
        self.shop = shop
        self.date = self._set_date(date)
        self.created_at = datetime.now()
        
        if reference_year is not None:
            self.reference_year = reference_year
        else:
            self.reference_year = self.date.year
            
        if reference_month is not None:
            self.reference_month = reference_month
        else:
            self.reference_month = self.date.month

        #On reading attrs
        self.selected = False
        self.doc_id = doc_id

    def __str__(self):
        return f'{self.product_name}|{self.code}|{self.quantity}|{self.unity}|{self.price}'

    def _set_amount(self, value):
        if self.formatted or isinstance(value,float):
            return float(value)
        try:
            pattern = r"\d{1,3}(.\d{3})*,\d{2}" #r'^\d+\,\d{2}'        
            value = re.search(pattern, value)
            if value:
                value = value.group().replace('.','').replace(',','.')
                return float(value)
            return 0
        except ValueError:
            return 0
    
    def _set_name(self, value):
        if self.formatted:
            return value
        try:
            value_aux = value.split('(Código:')
            return value_aux[0].strip()
        except IndexError:
            return value
        except AttributeError:
            return value
    
    def _set_code(self, code, product_name=None):
        try:
            if code:
                return code
            value_aux = product_name.split('(Código:')
            return value_aux[1].replace(')','').strip()
        except IndexError:
            return '0'

    def _set_unity(self, value):
        value_aux = value.split(':')
        try:
            return value_aux[1].strip()
        except IndexError:
            return value

    def _set_quantity(self, value):
        if self.formatted:
            return float(value)
        
        if isinstance(value,float):
            return value
        
        value_aux = value.split('Qtde total de ítens: ')
        try:
            return float(value_aux[1].strip())
        except IndexError:
            return 0
    
    def _set_owner(self, owner):
        if self.formatted:
            return owner
        
        owner_aux = None
        users = get_users()
        for key, value in users.items():
            if owner in value:
                owner_aux = key
                break
        if not owner_aux:
            return f'(NOVO){owner}'
        return owner_aux.strip()
    
    def _set_date(self, date):
        if type(date) == str:
            return datetime.strptime(date, "%d/%m/%Y %H:%M:%S")
        elif type(date) == datetime:
            return date
        return datetime.now()

    def to_dict(self) -> Dict:
        """Convert Product object to dictionary for storage."""
        return {
            'formatted': self.formatted,
            'product_name': self.product_name,
            'code': self.code,
            'quantity': self.quantity,
            'unity': self.unity,
            'price': self.price,
            'owner': self.owner,
            'shop': self.shop,
            'date': self.date.isoformat(),
            'created_at': self.created_at.isoformat(),
            'reference_year': self.reference_year,
            'reference_month': self.reference_month
        }
    
    @classmethod
    def from_dict(cls, data: Dict, doc_id: int = None) -> 'Product':
        """Create Product object from dictionary."""
        product = cls(
            product_name=data['product_name'],
            code=data['code'],
            quantity=data['quantity'],
            unity=data['unity'],
            price=data['price'],
            owner=data['owner'],
            shop=data['shop'],
            date=datetime.fromisoformat(data['date']) if isinstance(data['date'], str) else data['date'],
            formatted=data['formatted'],
            reference_year=data.get('reference_year'),
            reference_month=data.get('reference_month'),

            doc_id = doc_id
        )
        product.created_at = datetime.fromisoformat(data['created_at']) if isinstance(data['created_at'], str) else data['created_at']
        return product
    
    def update_quantity(self, new_quantity: int) -> None:
        """Update product quantity with validation."""
        self.quantity = self._set_quantity(new_quantity)
    
    def update_price(self, new_price: float) -> None:
        """Update product price with validation."""
        self.price = self._set_amount(new_price)
    
    def update_reference_period(self, year: int, month: int) -> None:
        """Update reference year and month."""
        self.reference_year = year
        self.reference_month = month
    
    def to_csv_line(self) -> str:
        """Convert to CSV line format."""
        return f'{self.product_name};{self.price};{self.owner};{self.date.strftime("%d/%m/%Y %H:%M:%S")};{self.code};{self.quantity};{self.unity};{self.shop};{self.created_at.strftime("%d/%m/%Y %H:%M:%S")};{self.reference_year};{self.reference_month}'
    
    def __str__(self) -> str:
        return f"Product(name={self.product_name}, code={self.code}, quantity={self.quantity}, price={self.price}, ref_period={self.reference_year}-{self.reference_month:02d})"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    @staticmethod
    def save_products(product_list: list):
        now = datetime.now()
        with open(PRODUCT_DIR, 'a', encoding='utf-8') as f:
            for p in product_list:
                f.write('\n')
                # Updated to include reference_year and reference_month
                line = f'{p.product_name};{p.price};{p.owner};{p.date.strftime("%d/%m/%Y %H:%M:%S")};{p.code};{p.quantity};{p.unity};{p.shop};{now.strftime("%d/%m/%Y %H:%M:%S")};{p.reference_year};{p.reference_month}'
                f.write(line)
    
    @staticmethod
    def load_products() -> list:
        items = []
        with open(PRODUCT_DIR, 'r', encoding='utf-8') as f:
            f.readline()  # Skip header
            for p in f.readlines():
                p = p.strip().split(';')
                # Handle both old and new format
                if len(p) >= 11:  # New format with reference_year and reference_month
                    items.append(Product(
                        product_name=p[0],
                        price=p[1],
                        owner=p[2],
                        date=p[3],
                        code=p[4],
                        quantity=p[5],
                        unity=p[6],
                        shop=p[7],
                        formatted=True,
                        reference_year=int(p[9]) if p[9] else None,
                        reference_month=int(p[10]) if p[10] else None
                    ))
                else:  # Old format without reference fields
                    product = Product(
                        product_name=p[0],
                        price=p[1],
                        owner=p[2],
                        date=p[3],
                        code=p[4],
                        quantity=p[5],
                        unity=p[6],
                        shop=p[7],
                        formatted=True
                    )
                    # Set reference period from date for old records
                    product.reference_year = product.date.year
                    product.reference_month = product.date.month
                    items.append(product)
        return items

    @staticmethod
    def backup_file():
        source_file = PRODUCT_DIR
        destination_file = PRODUCT_DIR.replace('.csv', '_bkp.csv')
        try:
            os.replace(source_file, destination_file)
            logging.info(f"File '{source_file}' renamed to '{destination_file}' (overwritten if existed).")
            with open(source_file, 'w') as file:
                file.write(PRODUCTS_FILEHEADER)
                #file.write('\n')
        except FileNotFoundError:
            #print(f"Error: Source file '{source_file}' not found.")
            os.rename(source_file, destination_file)
        except OSError:
            raise OSError("Erro ao tentar limpar arquivo!")
    
    @staticmethod
    def migrate_existing_file():
        """
        Migrate existing product CSV file to include reference_year and reference_month.
        This adds the new columns to all existing records.
        """
        try:
            # Check if file exists and has content
            if not os.path.exists(PRODUCT_DIR):
                logging.warning(f"File {PRODUCT_DIR} does not exist. No migration needed.")
                return
            
            # Load all existing products
            products = Product.load_products()
            
            # Backup the original file
            Product.backup_file()
            
            # Save all products with new format
            Product.save_products(products)
            
            logging.info(f"Successfully migrated {len(products)} products to new format")
            
        except Exception as e:
            logging.error(f"Error during migration: {e}")
            raise