
import re
from datetime import datetime
import re
from bs4 import BeautifulSoup as BS
from collections import deque

from consts import UNDEFINED

PRODUCT_DIR = 'data/products.csv'

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
            return value_aux[1].strip()
        except IndexError:
            return value
    
    def _set_owner(self,owner):
        if owner == '':
            return UNDEFINED
        return owner.replace('null','').strip()
    
    def _set_date(self,date):
        if type(date) == str:
            return datetime.strptime(date, "%d/%m/%Y %H:%M:%S")
        elif type(date) == datetime:
            return date
        return datetime.now()
@staticmethod
def save_products(product_list:list[Product]):
    now = datetime.now()
    with open(PRODUCT_DIR,'a') as f:
        for p in product_list:
            f.write('\n')
            line = f'{p.product_name};{p.code};{p.quantity};{p.unity};{p.price};{p.date.strftime("%d/%m/%Y %H:%M:%S")};{p.shop};{p.owner};{now.strftime("%d/%m/%Y %H:%M:%S")}'
            f.write(line)

@staticmethod
def load_products() -> list[Product]:
    items = []
    with open(PRODUCT_DIR,'r') as f:
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

class FixedSizeArray:
    def __init__(self, max_size):
        self.max_size = max_size
        self.array = deque(maxlen=max_size)
    
    def push(self, item):
        """Add item, automatically removes oldest if full"""
        self.array.append(item)
    
    def erase(self):
        """Delete all items"""
        self.array = deque(maxlen=self.max_size)
    
    def index(self,item):
        return self.array.index(item)
    
    def pop_last(self):
        """Remove and return the last (newest) item"""
        if self.array:
            return self.array.pop()
        raise IndexError("Array is empty")
    
    def pop_first(self):
        """Remove and return the first (oldest) item"""
        if self.array:
            return self.array.popleft()
        raise IndexError("Array is empty")
    
    def __getitem__(self, index):
        return self.array[index]
    
    def __len__(self):
        return len(self.array)
    
    def __str__(self):
        return str(list(self.array))
    
    def is_full(self):
        return len(self.array) == self.max_size
    
    def is_empty(self):
        return len(self.array) == 0
