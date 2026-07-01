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
        return [Pix.from_dict(data) for data in results]
    
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
    
    def get_products_in_stock(self) -> List[Product]:
        """
        Get all products with quantity > 0.
        
        Returns:
            List of Product objects in stock
        """
        results = self.products_table.search(self.ProductQuery.quantity > 0)
        return [Product.from_dict(data) for data in results]
    
    def get_all_products(self) -> List[Product]:
        """Get all products."""
        results = self.products_table.all()
        return [Product.from_dict(data) for data in results]
    
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


# ==================== EXAMPLE USAGE ====================

def main():
    """Example usage of the DatabaseManager class with Pix and Product."""
    
    # Initialize database
    db = DatabaseManager('example_db.json')
    
    # Clear database for fresh start
    db.clear_database()
    
    print("=" * 60)
    print("PIX CRUD OPERATIONS")
    print("=" * 60)
    
    # ========== PIX EXAMPLES ==========
    
    # 1. CREATE Pix transactions
    print("\n1. Creating Pix transactions...")
    
    pix1 = Pix(
        from_="John Doe",
        to_="Jane Smith",
        value=150.50,
        bank_="Banco do Brasil",
        correction_=False
    )
    
    pix2 = Pix(
        from_="Jane Smith",
        to_="John Doe",
        value=75.25,
        bank_="Nubank",
        correction_=True
    )
    
    pix3 = Pix(
        from_="John Doe",
        to_="Company XYZ",
        value=1000.00,
        bank_="Itaú",
        correction_=False
    )
    
    pix_id1 = db.create_pix(pix1)
    pix_id2 = db.create_pix(pix2)
    pix_id3 = db.create_pix(pix3)
    
    print(f"  Created Pix 1: {pix1} (Doc ID: {pix_id1})")
    print(f"  Created Pix 2: {pix2} (Doc ID: {pix_id2})")
    print(f"  Created Pix 3: {pix3} (Doc ID: {pix_id3})")
    
    # 2. READ Pix transactions
    print("\n2. Reading Pix transactions...")
    
    # Get by document ID
    retrieved_pix = db.get_pix(pix_id1)
    print(f"  Retrieved Pix by doc ID {pix_id1}: {retrieved_pix}")
    
    # Get by transaction ID
    pix_by_id = db.get_pix_by_id(pix1.id_)
    print(f"  Retrieved Pix by transaction ID {pix1.id_}: {pix_by_id}")
    
    # Get by sender
    sender_pix = db.get_pix_by_sender("John Doe")
    print(f"  Pix from John Doe: {len(sender_pix)} transactions")
    for p in sender_pix:
        print(f"    - To: {p.to_}, Value: ${p.value}")
    
    # Get by receiver
    receiver_pix = db.get_pix_by_receiver("Jane Smith")
    print(f"  Pix to Jane Smith: {len(receiver_pix)} transactions")
    for p in receiver_pix:
        print(f"    - From: {p.from_}, Value: ${p.value}")
    
    # Get all Pix
    all_pix = db.get_all_pix()
    print(f"  Total Pix transactions: {len(all_pix)}")
    
    # 3. UPDATE Pix transactions
    print("\n3. Updating Pix transactions...")
    
    # Update value
    db.update_pix(pix_id1, {'value': 200.75, 'bank_': 'Santander'})
    updated_pix = db.get_pix(pix_id1)
    print(f"  Updated Pix {pix1.id_}: New value ${updated_pix.value}, Bank: {updated_pix.bank_}")
    
    # 4. DELETE Pix transactions
    print("\n4. Deleting Pix transactions...")
    
    # Delete by document ID
    db.delete_pix(pix_id3)
    print(f"  Deleted Pix with doc ID {pix_id3}")
    
    # Delete by transaction ID
    db.delete_pix_by_id(pix2.id_)
    print(f"  Deleted Pix with transaction ID {pix2.id_}")
    
    # Check remaining Pix
    remaining_pix = db.get_all_pix()
    print(f"  Remaining Pix transactions: {len(remaining_pix)}")
    
    print("\n" + "=" * 60)
    print("PRODUCT CRUD OPERATIONS")
    print("=" * 60)
    
    # ========== PRODUCT EXAMPLES ==========
    
    # 1. CREATE Products
    print("\n1. Creating Products...")
    
    product1 = Product(
        product_name="Laptop Dell XPS",
        code="DELL-XPS-001",
        quantity=10,
        unity="units",
        price=1500.00,
        owner="John Doe",
        shop="TechStore",
        formatted=True
    )
    
    product2 = Product(
        product_name="Keyboard Mechanical",
        code="KEY-MEC-002",
        quantity=25,
        unity="units",
        price=89.99,
        owner="John Doe",
        shop="TechStore",
        formatted=True
    )
    
    product3 = Product(
        product_name="Monitor 4K",
        code="MON-4K-003",
        quantity=5,
        unity="units",
        price=450.00,
        owner="Jane Smith",
        shop="DisplayWorld",
        formatted=True
    )
    
    prod_id1 = db.create_product(product1)
    prod_id2 = db.create_product(product2)
    prod_id3 = db.create_product(product3)
    
    print(f"  Created Product 1: {product1} (Doc ID: {prod_id1})")
    print(f"  Created Product 2: {product2} (Doc ID: {prod_id2})")
    print(f"  Created Product 3: {product3} (Doc ID: {prod_id3})")
    
    # 2. READ Products
    print("\n2. Reading Products...")
    
    # Get by document ID
    retrieved_product = db.get_product(prod_id1)
    print(f"  Retrieved Product by doc ID {prod_id1}: {retrieved_product}")
    
    # Get by code
    product_by_code = db.get_product_by_code("DELL-XPS-001")
    print(f"  Retrieved Product by code: {product_by_code}")
    
    # Get by owner
    owner_products = db.get_products_by_owner("John Doe")
    print(f"  Products owned by John Doe: {len(owner_products)}")
    for p in owner_products:
        print(f"    - {p.product_name} (Code: {p.code})")
    
    # Get by shop
    shop_products = db.get_products_by_shop("TechStore")
    print(f"  Products from TechStore: {len(shop_products)}")
    for p in shop_products:
        print(f"    - {p.product_name} (Price: ${p.price})")
    
    # Get products in stock
    in_stock = db.get_products_in_stock()
    print(f"  Products in stock: {len(in_stock)}")
    
    # Get all products
    all_products = db.get_all_products()
    print(f"  Total products: {len(all_products)}")
    
    # 3. UPDATE Products
    print("\n3. Updating Products...")
    
    # Update quantity
    db.update_product_quantity(prod_id1, 8)
    updated_product = db.get_product(prod_id1)
    print(f"  Updated {updated_product.product_name} quantity to: {updated_product.quantity}")
    
    # Update price
    db.update_product_price(prod_id2, 99.99)
    updated_product = db.get_product(prod_id2)
    print(f"  Updated {updated_product.product_name} price to: ${updated_product.price}")
    
    # Update multiple fields
    db.update_product(prod_id3, {
        'quantity': 15,
        'price': 425.00,
        'shop': 'TechWorld'
    })
    updated_product = db.get_product(prod_id3)
    print(f"  Updated {updated_product.product_name}: Quantity={updated_product.quantity}, "
          f"Price=${updated_product.price}, Shop={updated_product.shop}")
    
    # 4. DELETE Products
    print("\n4. Deleting Products...")
    
    # Delete by document ID
    db.delete_product(prod_id3)
    print(f"  Deleted Product with doc ID {prod_id3}")
    
    # Delete by code
    db.delete_product_by_code("KEY-MEC-002")
    print(f"  Deleted Product with code KEY-MEC-002")
    
    # Check remaining products
    remaining_products = db.get_all_products()
    print(f"  Remaining products: {len(remaining_products)}")
    for p in remaining_products:
        print(f"    - {p.product_name} (Quantity: {p.quantity})")
    
    # ========== STATISTICS ==========
    
    print("\n" + "=" * 60)
    print("DATABASE STATISTICS")
    print("=" * 60)
    
    stats = db.get_database_stats()
    print(f"  Total Pix Transactions: {stats['total_pix_transactions']}")
    print(f"  Total Pix Value: ${stats['total_pix_value']:.2f}")
    print(f"  Total Products: {stats['total_products']}")
    print(f"  Total Inventory Value: ${stats['total_product_value']:.2f}")
    print(f"  Total Inventory Items: {stats['total_inventory_items']}")
    
    # Clean up
    db.close()
    print("\nDatabase closed.")


if __name__ == "__main__":
    main()