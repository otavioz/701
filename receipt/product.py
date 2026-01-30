
import json
import logging
import os
import re
from datetime import datetime
import re
from bs4 import BeautifulSoup as BS

from consts import BKP_PRODUCT_DIR, PRODUCT_DIR, UNDEFINED, USERS_DIR
from src.utils import get_users

#PRODUCTS_FILEHEADER = 'product_name;code;quantity;unity;price;date;shop;owner;datetime'
PRODUCTS_FILEHEADER = 'product_name;price;owner;date;code;quantity;unity;shop;datetime'

class Product():
    def __init__(self,product_name, quantity, unity, price, owner, shop, code=None, date=None, formatted=False):
        
        #Basics attrs
        self.formatted = formatted
        self.product_name = self._set_name(product_name)
        self.code = self._set_code(code,product_name)
        self.quantity = self._set_quantity(quantity)
        self.unity = self._set_unity(unity)
        self.price = self._set_amount(price)
        self.owner = self._set_owner(owner)
        self.shop = shop
        self.date = self._set_date(date)

        #On reading attrs
        self.selected = False

    def __str__(self):
        return f'{self.product_name}|{self.code}|{self.quantity}|{self.unity}|{self.price}'

    def _set_amount(self,value):
        if self.formatted:
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
    
    def _set_name(self,value):
        if self.formatted:
            return value
        try:
            value_aux = value.split('(Código:')
            return value_aux[0].strip()
        except IndexError:
            return value
        except AttributeError:
            return value
    
    def _set_code(self,code,product_name=None):
        try:
            if code:
                return code
            value_aux = product_name.split('(Código:')
            return value_aux[1].replace(')','').strip()
        except IndexError:
            return '0'

    def _set_unity(self,value):
        value_aux = value.split(':')
        try:
            return value_aux[1].strip()
        except IndexError:
            return value

    def _set_quantity(self,value):
        value_aux = value.split('Qtde total de ítens: ')
        try:
            return float(value_aux[1].strip())
        except IndexError:
            return 0
    
    def _set_owner(self,owner):
        if self.formatted:
            return owner
        users = get_users()
        for key,value in users.items():
            if owner in value:
                owner = key
                break
        if owner == '':
            return UNDEFINED
        return owner.strip()
    
    def _set_date(self,date):
        if type(date) == str:
            return datetime.strptime(date, "%d/%m/%Y %H:%M:%S")
        elif type(date) == datetime:
            return date
        return datetime.now()


@staticmethod
def save_products(product_list:list[Product]):
    now = datetime.now()
    with open(PRODUCT_DIR, 'a', encoding='utf-8') as f:
        for p in product_list:
            f.write('\n')
            line = f'{p.product_name};{p.price};{p.owner};{p.date.strftime("%d/%m/%Y %H:%M:%S")};{p.code};{p.quantity};{p.unity};{p.shop};{now.strftime("%d/%m/%Y %H:%M:%S")}'
            f.write(line)

@staticmethod
def load_products() -> list[Product]:
    items = []
    with open(PRODUCT_DIR, 'r', encoding='utf-8') as f:
        f.readline()
        for p in f.readlines():
            p = p.split(';')
            items.append(Product(product_name = p[0],
                                    code = p[1],
                                    quantity = p[2],
                                    unity = p[3],
                                    price = p[4],
                                    date = p[5],
                                    shop = p[6],
                                    owner = p[7],
                                    formatted=True))
    return items

@staticmethod
def backup_file():
    source_file = PRODUCT_DIR
    destination_file = BKP_PRODUCT_DIR
    try:
        os.replace(source_file, destination_file)
        logging.info(f"File '{source_file}' renamed to '{destination_file}' (overwritten if existed).")
        with open(source_file, 'w') as file:
            file.write(PRODUCTS_FILEHEADER)
            #file.write('\n')
    except FileNotFoundError:
        #print(f"Error: Source file '{source_file}' not found.")
        os.rename(source_file,destination_file)
    except OSError:
        raise OSError("Erro ao tentar limpar arquivo!")

