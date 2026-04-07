from __future__ import annotations

from typing import List, Optional
from app.domain.models import Product, Order, Category
from app.repositories.p2pstore_repository import AbstractP2PStoreRepository
from app.schemas.p2pstore import ProductCreate, ProductUpdate, OrderCreate


class P2PStoreService:
    def __init__(self, repository: AbstractP2PStoreRepository):
        self.repository = repository

    def list_products(self, category: Optional[str] = None, limit: int = 20) -> List[Product]:
        """List products with optional category filter"""
        return self.repository.list_products(category=category, limit=limit)

    def get_product(self, product_id: str) -> Optional[Product]:
        """Get product by ID"""
        return self.repository.get_product(product_id)

    def create_product(self, product_data: ProductCreate) -> Product:
        """Create a new product"""
        product = Product(
            product_id=self.repository.generate_product_id(),
            name=product_data.name,
            description=product_data.description,
            price=product_data.price,
            category=product_data.category,
            stock=product_data.stock,
            seller_id=product_data.seller_id,
        )
        return self.repository.create_product(product)

    def update_product(self, product_id: str, product_data: ProductUpdate) -> Optional[Product]:
        """Update a product"""
        product = self.repository.get_product(product_id)
        if not product:
            return None
        
        if product_data.name is not None:
            product.name = product_data.name
        if product_data.description is not None:
            product.description = product_data.description
        if product_data.price is not None:
            product.price = product_data.price
        if product_data.category is not None:
            product.category = product_data.category
        if product_data.stock is not None:
            product.stock = product_data.stock
        
        return self.repository.update_product(product)

    def delete_product(self, product_id: str) -> bool:
        """Delete a product"""
        return self.repository.delete_product(product_id)

    def list_categories(self) -> List[Category]:
        """List all categories"""
        return self.repository.list_categories()

    def create_order(self, order_data: OrderCreate) -> Order:
        """Create a new order"""
        product = self.repository.get_product(order_data.product_id)
        if not product:
            raise ValueError(f"Product not found: {order_data.product_id}")
        
        if product.stock < order_data.quantity:
            raise ValueError(f"Insufficient stock: requested {order_data.quantity}, available {product.stock}")
        
        # Calculate total price
        total_price = product.price * order_data.quantity
        
        # Create order
        order = Order(
            order_id=self.repository.generate_order_id(),
            product_id=order_data.product_id,
            quantity=order_data.quantity,
            buyer_id=order_data.buyer_id,
            seller_id=product.seller_id,
            total_price=total_price,
            status="pending",
        )
        
        # Update product stock
        product.stock -= order_data.quantity
        self.repository.update_product(product)
        
        return self.repository.create_order(order)

    def list_orders(self, limit: int = 20) -> List[Order]:
        """List orders"""
        return self.repository.list_orders(limit=limit)

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        return self.repository.get_order(order_id)