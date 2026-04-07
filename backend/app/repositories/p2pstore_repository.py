from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.models import Product, Order, Category


class AbstractP2PStoreRepository(ABC):
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the repository"""
        raise NotImplementedError

    @abstractmethod
    def generate_product_id(self) -> str:
        """Generate a new product ID"""
        raise NotImplementedError

    @abstractmethod
    def generate_order_id(self) -> str:
        """Generate a new order ID"""
        raise NotImplementedError

    @abstractmethod
    def list_products(self, category: Optional[str] = None, limit: int = 20) -> List[Product]:
        """List products with optional category filter"""
        raise NotImplementedError

    @abstractmethod
    def get_product(self, product_id: str) -> Optional[Product]:
        """Get product by ID"""
        raise NotImplementedError

    @abstractmethod
    def create_product(self, product: Product) -> Product:
        """Create a new product"""
        raise NotImplementedError

    @abstractmethod
    def update_product(self, product: Product) -> Product:
        """Update a product"""
        raise NotImplementedError

    @abstractmethod
    def delete_product(self, product_id: str) -> bool:
        """Delete a product"""
        raise NotImplementedError

    @abstractmethod
    def list_categories(self) -> List[Category]:
        """List all categories"""
        raise NotImplementedError

    @abstractmethod
    def generate_order_id(self) -> str:
        """Generate a new order ID"""
        raise NotImplementedError

    @abstractmethod
    def create_order(self, order: Order) -> Order:
        """Create a new order"""
        raise NotImplementedError

    @abstractmethod
    def list_orders(self, limit: int = 20) -> List[Order]:
        """List orders"""
        raise NotImplementedError

    @abstractmethod
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        raise NotImplementedError