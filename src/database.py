import json
import logging
from tinydb import TinyDB, Query
from datetime import datetime
from typing import Dict, List, Optional, Union
import uuid
from src.exceptions import DuplicatedValue
from receipt.pix import Pix
from receipt.product import Product


class DatabaseManager:
    """
    A class to manage TinyDB operations for Pix and Product objects.
    """
    
    def __init__(self, db_path: str = 'database.json'):
        """
        Initialize the database manager.
        
        Args:
            db_path: Path to the JSON database file
        """
        self.db = TinyDB(db_path)
        self.pix_table = self.db.table('pix')
        self.products_table = self.db.table('products')
        self.PixQuery = Query()
        self.ProductQuery = Query()

        self.logger = logging.getLogger(__name__)
    
    # ==================== PIX CRUD OPERATIONS ====================
    
    def create_pix(self, pix: Pix) -> int:
        """
        Create a new Pix transaction.
        
        Args:
            pix: Pix object to insert
        
        Returns:
            Document ID of the inserted Pix
        """
        # Check if Pix with same ID already exists
        if self.pix_table.contains(self.PixQuery.id_ == pix.id_):
            self.logger.error(f"Pix with ID {pix.id_} already exists")
            raise DuplicatedValue(pix.id_)
        
        doc_id = self.pix_table.insert(pix.to_dict())
        return doc_id
    
    def create_pix_from_dict(self, data: Dict) -> int:
        """
        Create a new Pix transaction from dictionary.
        
        Args:
            data: Dictionary containing Pix data
        
        Returns:
            Document ID of the inserted Pix
        """
        pix = Pix.from_dict(data)
        return self.create_pix(pix)
    
    def get_pix(self, doc_id: int) -> Optional[Pix]:
        """
        Get a Pix transaction by document ID.
        
        Args:
            doc_id: Document ID
        
        Returns:
            Pix object or None if not found
        """
        data = self.pix_table.get(doc_id=doc_id)
        if data:
            return Pix.from_dict(data)
        return None
    
    def get_pix_by_id(self, pix_id: str) -> Optional[Pix]:
        """
        Get a Pix transaction by its ID.
        
        Args:
            pix_id: Pix transaction ID
        
        Returns:
            Pix object or None if not found
        """
        data = self.pix_table.get(self.PixQuery.id_ == pix_id)
        if data:
            return Pix.from_dict(data)
        return None
    
    def get_pix_by_sender(self, from_: str) -> List[Pix]:
        """
        Get all Pix transactions from a specific sender.
        
        Args:
            from_: Sender account
        
        Returns:
            List of Pix objects
        """
        results = self.pix_table.search(self.PixQuery.from_ == from_)
        return [Pix.from_dict(data) for data in results]
    
    def get_pix_by_receiver(self, to_: str) -> List[Pix]:
        """
        Get all Pix transactions to a specific receiver.
        
        Args:
            to_: Receiver account
        
        Returns:
            List of Pix objects
        """
        results = self.pix_table.search(self.PixQuery.to_ == to_)
        return [Pix.from_dict(data) for data in results]
    
    def get_pix_by_value_range(self, min_value: float, max_value: float) -> List[Pix]:
        """
        Get Pix transactions within a value range.
        
        Args:
            min_value: Minimum value
            max_value: Maximum value
        
        Returns:
            List of Pix objects
        """
        results = self.pix_table.search(
            (self.PixQuery.value >= min_value) & (self.PixQuery.value <= max_value)
        )
        return [Pix.from_dict(data) for data in results]
    
    def get_pix_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Pix]:
        """
        Get Pix transactions within a date range.
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            List of Pix objects
        """
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()
        results = self.pix_table.search(
            (self.PixQuery.date_ >= start_str) & (self.PixQuery.date_ <= end_str)
        )
        return [Pix.from_dict(data) for data in results]
    
    def get_all_pix(self) -> List[Pix]:
        """Get all Pix transactions."""
        results = self.pix_table.all()
        return [Pix.from_dict(data,doc_id = data.doc_id) for data in results]
    
    def update_pix(self, doc_id: int, update_data: Dict) -> bool:
        """
        Update a Pix transaction.
        
        Args:
            doc_id: Document ID
            update_data: Dictionary with fields to update
        
        Returns:
            True if update was successful, False otherwise
        """
        # Remove fields that shouldn't be updated
        update_data.pop('id_', None)
        update_data.pop('include_date', None)
        
        # Convert date to string if present
        if 'date_' in update_data and isinstance(update_data['date_'], datetime):
            update_data['date_'] = update_data['date_'].isoformat()

        updated = self.pix_table.update(update_data, doc_ids=[doc_id])
        return len(updated) > 0
    
    def update_pix_object(self, doc_id: int, pix: Pix) -> bool:
        """
        Update a Pix transaction with a new Pix object.
        
        Args:
            doc_id: Document ID
            pix: New Pix object
        
        Returns:
            True if update was successful, False otherwise
        """
        return self.pix_table.update(pix.to_dict(), doc_ids=[doc_id]) > 0
    
    def delete_pix(self, doc_id: int) -> bool:
        """
        Delete a Pix transaction by document ID.
        
        Args:
            doc_id: Document ID
        
        Returns:
            True if deletion was successful, False otherwise
        """
        return len(self.pix_table.remove(doc_ids=[doc_id])) > 0
    
    def delete_pix_by_id(self, pix_id: str) -> bool:
        """
        Delete a Pix transaction by its ID.
        
        Args:
            pix_id: Pix transaction ID
        
        Returns:
            True if deletion was successful, False otherwise
        """
        return len(self.pix_table.remove(self.PixQuery.id_ == pix_id)) > 0
    
    def delete_all_pix(self) -> int:
        """
        Delete all Pix transactions.
        
        Returns:
            Number of deleted records
        """
        return len(self.pix_table.truncate())
    
    # ==================== PRODUCT CRUD OPERATIONS ====================
    
    def create_product(self, product: Product) -> int:
        """
        Create a new Product.
        
        Args:
            product: Product object to insert
        
        Returns:
            Document ID of the inserted Product
        """
        # Check if product with same code already exists
        #if self.products_table.contains(self.ProductQuery.code == product.code):
        #    raise ValueError(f"Product with code {product.code} already exists")
        
        doc_id = self.products_table.insert(product.to_dict())
        return doc_id
    
    def create_product_from_dict(self, data: Dict) -> int:
        """
        Create a new Product from dictionary.
        
        Args:
            data: Dictionary containing Product data
        
        Returns:
            Document ID of the inserted Product
        """
        product = Product.from_dict(data)
        return self.create_product(product)
    
    def get_product(self, doc_id: int) -> Optional[Product]:
        """
        Get a Product by document ID.
        
        Args:
            doc_id: Document ID
        
        Returns:
            Product object or None if not found
        """
        data = self.products_table.get(doc_id=doc_id)
        if data:
            return Product.from_dict(data)
        return None
    
    def get_product_by_code(self, code: str) -> Optional[Product]:
        """
        Get a Product by its code.
        
        Args:
            code: Product code
        
        Returns:
            Product object or None if not found
        """
        data = self.products_table.get(self.ProductQuery.code == code)
        if data:
            return Product.from_dict(data)
        return None
    
    def get_products_by_name(self, name: str) -> List[Product]:
        """
        Get all products with a specific name (partial match).
        
        Args:
            name: Product name to search for
        
        Returns:
            List of Product objects
        """
        results = self.products_table.search(
            self.ProductQuery.product_name.matches(f'.*{name}.*')
        )
        return [Product.from_dict(data) for data in results]
    
    def get_products_by_owner(self, owner: str) -> List[Product]:
        """
        Get all products owned by a specific person.
        
        Args:
            owner: Owner name
        
        Returns:
            List of Product objects
        """
        results = self.products_table.search(self.ProductQuery.owner == owner)
        return [Product.from_dict(data) for data in results]
    
    def get_products_by_shop(self, shop: str) -> List[Product]:
        """
        Get all products from a specific shop.
        
        Args:
            shop: Shop name
        
        Returns:
            List of Product objects
        """
        results = self.products_table.search(self.ProductQuery.shop == shop)
        return [Product.from_dict(data) for data in results]
    
    def get_products_by_price_range(self, min_price: float, max_price: float) -> List[Product]:
        """
        Get products within a price range.
        
        Args:
            min_price: Minimum price
            max_price: Maximum price
        
        Returns:
            List of Product objects
        """
        results = self.products_table.search(
            (self.ProductQuery.price >= min_price) & (self.ProductQuery.price <= max_price)
        )
        return [Product.from_dict(data) for data in results]
    
    def get_all_products(self) -> List[Product]:
        """Get all products."""
        results = self.products_table.all()
        return [Product.from_dict(data, doc_id = data.doc_id) for data in results]
    
    def update_product(self, doc_id: int, update_data: Dict) -> bool:
        """
        Update a Product.
        
        Args:
            doc_id: Document ID
            update_data: Dictionary with fields to update
        
        Returns:
            True if update was successful, False otherwise
        """
        # Remove fields that shouldn't be updated
        update_data.pop('code', None)
        update_data.pop('created_at', None)
        
        # Convert date to string if present
        if 'date' in update_data and isinstance(update_data['date'], datetime):
            update_data['date'] = update_data['date'].isoformat()
        
        return len(self.products_table.update(update_data, doc_ids=[doc_id])) > 0
    
    def update_product_object(self, doc_id: int, product: Product) -> bool:
        """
        Update a Product with a new Product object.
        
        Args:
            doc_id: Document ID
            product: New Product object
        
        Returns:
            True if update was successful, False otherwise
        """
        return self.products_table.update(product.to_dict(), doc_ids=[doc_id]) > 0
    
    def update_product_quantity(self, doc_id: int, new_quantity: int) -> bool:
        """
        Update a product's quantity.
        
        Args:
            doc_id: Document ID
            new_quantity: New quantity value
        
        Returns:
            True if update was successful, False otherwise
        """
        if new_quantity < 0:
            raise ValueError("Quantity cannot be negative")
        return len(self.products_table.update({'quantity': new_quantity}, doc_ids=[doc_id])) > 0
    
    def update_product_price(self, doc_id: int, new_price: float) -> bool:
        """
        Update a product's price.
        
        Args:
            doc_id: Document ID
            new_price: New price value
        
        Returns:
            True if update was successful, False otherwise
        """
        if new_price < 0:
            raise ValueError("Price cannot be negative")
        return len(self.products_table.update({'price': new_price}, doc_ids=[doc_id])) > 0
    
    def delete_product(self, doc_id: int) -> bool:
        """
        Delete a Product by document ID.
        
        Args:
            doc_id: Document ID
        
        Returns:
            True if deletion was successful, False otherwise
        """
        return len(self.products_table.remove(doc_ids=[doc_id])) > 0
    
    def delete_product_by_code(self, code: str) -> bool:
        """
        Delete a Product by its code.
        
        Args:
            code: Product code
        
        Returns:
            True if deletion was successful, False otherwise
        """
        return len(self.products_table.remove(self.ProductQuery.code == code)) > 0
    
    def delete_all_products(self) -> int:
        """
        Delete all products.
        
        Returns:
            Number of deleted records
        """
        return len(self.products_table.truncate())
    
    # ==================== UTILITY METHODS ====================
    
    def clear_database(self):
        """Clear all data from the database."""
        self.pix_table.truncate()
        self.products_table.truncate()
    
    def get_database_stats(self) -> Dict:
        """Get statistics about the database."""
        pix_list = self.get_all_pix()
        products_list = self.get_all_products()
        
        total_pix_value = sum(pix.value for pix in pix_list)
        total_product_value = sum(product.price * product.quantity for product in products_list)
        
        return {
            'total_pix_transactions': len(pix_list),
            'total_pix_value': total_pix_value,
            'total_products': len(products_list),
            'total_product_value': total_product_value,
            'total_inventory_items': sum(p.quantity for p in products_list)
        }
    
    def close(self):
        """Close the database connection."""
        self.db.close()