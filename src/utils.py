from collections import deque
import json
from consts import USERS_DIR
from PIL import Image



def get_users():
    with open(USERS_DIR, 'r', encoding='utf-8') as f:
        # Use json.load() to convert JSON data into a Python list
        data_list = json.load(f)
    return data_list

def save_img_bkp(path,user_id):
    img = Image.open(path)
    img.save(f'downloas/{user_id}_{img.filename}')

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
