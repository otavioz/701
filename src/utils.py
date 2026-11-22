from collections import deque
import json
from typing import Any, Dict, List, Optional

from PIL import Image

from consts import USERS_DIR


def get_users() -> List[Dict[str, Any]]:
    with open(USERS_DIR, 'r', encoding='utf-8') as f:
        users = json.load(f)

    if not isinstance(users, list):
        raise ValueError(f"Expected a list of users in {USERS_DIR}")
    for user in users:
        if (
            not isinstance(user, dict)
            or not isinstance(user.get('nome'), str)
            or not isinstance(user.get('alias'), list)
            or any(not isinstance(alias, str) for alias in user.get('alias', []))
            or type(user.get('user_type')) is not int
            or user['user_type'] not in (0, 1)
        ):
            raise ValueError(f"Invalid user record in {USERS_DIR}: {user!r}")
    return users


def find_user_name(alias: str, users: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
    normalized_alias = alias.strip().casefold()
    if not normalized_alias:
        return None

    for user in users if users is not None else get_users():
        names = [user['nome'], *user['alias']]
        if any(
            normalized_alias == name.strip().casefold()
            or normalized_alias in name.strip().casefold()
            for name in names
            if isinstance(name, str)
        ):
            return user['nome']
    return None


def add_unknown_user(name: str, users: List[Dict[str, Any]] = None) -> str:
    name = name.strip()
    if not name:
        raise ValueError("A user's name cannot be empty.")

    if not users:
        users = get_users()

    users.append({'nome': name, 'alias': [], 'user_type': 0})
    with open(USERS_DIR, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)
        f.write('\n')
    return name

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
