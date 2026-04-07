from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from itertools import count
from typing import List, Optional

from app.domain.models import Product, Order, Category
from app.infrastructure.db.session import DatabaseSessionManager
from app.repositories.p2pstore_repository import AbstractP2PStoreRepository


class SQLiteP2PStoreRepository(AbstractP2PStoreRepository):
    def __init__(self, session_manager: DatabaseSessionManager) -> None:
        self.session_manager = session_manager
        self._product_counter = count(1000)
        self._order_counter = count(1000)

    def initialize(self) -> None:
        self._create_tables()
        self._seed_if_empty()
        self._sync_counters()

    def generate_product_id(self) -> str:
        """Generate a new product ID"""
        return f"p{next(self._product_counter)}"

    def generate_order_id(self) -> str:
        """Generate a new order ID"""
        return f"o{next(self._order_counter)}"

    def list_products(self, category: Optional[str] = None, limit: int = 20) -> List[Product]:
        """List products with optional category filter"""
        query = """
        SELECT
            product_id, name, description, price, category, stock, seller_id, created_at, updated_at
        FROM p2pstore_products
        """
        params = []

        if category:
            query += " WHERE category = ?"
            params.append(category)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self.session_manager.connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._map_product(row) for row in rows]

    def get_product(self, product_id: str) -> Optional[Product]:
        """Get product by ID"""
        with self.session_manager.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    product_id, name, description, price, category, stock, seller_id, created_at, updated_at
                FROM p2pstore_products
                WHERE product_id = ?
                """,
                (product_id,),
            ).fetchone()

        if row is None:
            return None

        return self._map_product(row)

    def create_product(self, product: Product) -> Product:
        """Create a new product"""
        now = datetime.now(timezone.utc).isoformat()

        with self.session_manager.connect() as conn:
            conn.execute(
                """
                INSERT INTO p2pstore_products (
                    product_id,
                    name,
                    description,
                    price,
                    category,
                    stock,
                    seller_id,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product.product_id,
                    product.name,
                    product.description,
                    product.price,
                    product.category,
                    product.stock,
                    product.seller_id,
                    now,
                    now,
                ),
            )
            conn.commit()

        return self.get_product(product.product_id)

    def update_product(self, product: Product) -> Product:
        """Update a product"""
        now = datetime.now(timezone.utc).isoformat()

        with self.session_manager.connect() as conn:
            conn.execute(
                """
                UPDATE p2pstore_products
                SET name = ?, description = ?, price = ?, category = ?, stock = ?, updated_at = ?
                WHERE product_id = ?
                """,
                (
                    product.name,
                    product.description,
                    product.price,
                    product.category,
                    product.stock,
                    now,
                    product.product_id,
                ),
            )
            conn.commit()

        return self.get_product(product.product_id)

    def delete_product(self, product_id: str) -> bool:
        """Delete a product"""
        with self.session_manager.connect() as conn:
            result = conn.execute(
                "DELETE FROM p2pstore_products WHERE product_id = ?",
                (product_id,),
            )
            conn.commit()

        return result.rowcount > 0

    def list_categories(self) -> List[Category]:
        """List all categories"""
        with self.session_manager.connect() as conn:
            rows = conn.execute(
                """
                SELECT slug, name, description
                FROM p2pstore_categories
                ORDER BY sort_order ASC
                """
            ).fetchall()

        return [self._map_category(row) for row in rows]

    def create_order(self, order: Order) -> Order:
        """Create a new order"""
        now = datetime.now(timezone.utc).isoformat()

        with self.session_manager.connect() as conn:
            conn.execute(
                """
                INSERT INTO p2pstore_orders (
                    order_id,
                    product_id,
                    quantity,
                    buyer_id,
                    seller_id,
                    total_price,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order.order_id,
                    order.product_id,
                    order.quantity,
                    order.buyer_id,
                    order.seller_id,
                    order.total_price,
                    order.status,
                    now,
                ),
            )
            conn.commit()

        return self.get_order(order.order_id)

    def list_orders(self, limit: int = 20) -> List[Order]:
        """List orders"""
        with self.session_manager.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    order_id, product_id, quantity, buyer_id, seller_id, total_price, status, created_at
                FROM p2pstore_orders
                ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [self._map_order(row) for row in rows]

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        with self.session_manager.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    order_id, product_id, quantity, buyer_id, seller_id, total_price, status, created_at
                FROM p2pstore_orders
                WHERE order_id = ?
                """,
                (order_id,),
            ).fetchone()

        if row is None:
            return None

        return self._map_order(row)

    def _map_product(self, row: sqlite3.Row) -> Product:
        """Map a database row to a Product object"""
        return Product(
            product_id=row["product_id"],
            name=row["name"],
            description=row["description"],
            price=row["price"],
            category=row["category"],
            stock=row["stock"],
            seller_id=row["seller_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _map_category(self, row: sqlite3.Row) -> Category:
        """Map a database row to a Category object"""
        return Category(
            slug=row["slug"],
            name=row["name"],
            description=row["description"],
        )

    def _map_order(self, row: sqlite3.Row) -> Order:
        """Map a database row to an Order object"""
        return Order(
            order_id=row["order_id"],
            product_id=row["product_id"],
            quantity=row["quantity"],
            buyer_id=row["buyer_id"],
            seller_id=row["seller_id"],
            total_price=row["total_price"],
            status=row["status"],
            created_at=row["created_at"],
        )

    def _create_tables(self) -> None:
        """Create database tables"""
        with self.session_manager.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS p2pstore_categories (
                    slug TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    sort_order INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS p2pstore_products (
                    product_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    price REAL NOT NULL,
                    category TEXT NOT NULL,
                    stock INTEGER NOT NULL,
                    seller_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(category) REFERENCES p2pstore_categories(slug)
                );

                CREATE TABLE IF NOT EXISTS p2pstore_orders (
                    order_id TEXT PRIMARY KEY,
                    product_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    buyer_id TEXT NOT NULL,
                    seller_id TEXT NOT NULL,
                    total_price REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(product_id) REFERENCES p2pstore_products(product_id)
                );
                """
            )
            conn.commit()

    def _seed_if_empty(self) -> None:
        """Seed initial data if tables are empty"""
        with self.session_manager.connect() as conn:
            category_count = conn.execute("SELECT COUNT(1) AS count FROM p2pstore_categories").fetchone()["count"]
            if category_count > 0:
                return

            # Seed categories
            conn.executemany(
                """
                INSERT INTO p2pstore_categories (slug, name, description, sort_order)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        "electronics",
                        "Electronics",
                        "Electronic devices and accessories",
                        1,
                    ),
                    (
                        "clothing",
                        "Clothing & Accessories",
                        "Apparel and fashion items",
                        2,
                    ),
                    (
                        "books",
                        "Books & Media",
                        "Books, movies, music, and other media",
                        3,
                    ),
                    (
                        "other",
                        "Other Items",
                        "Various other items",
                        4,
                    ),
                ],
            )

            # Seed products
            conn.executemany(
                """
                INSERT INTO p2pstore_products (
                    product_id,
                    name,
                    description,
                    price,
                    category,
                    stock,
                    seller_id,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "p1001",
                        "Vintage Laptop",
                        "Old but functional laptop from the 90s",
                        99.99,
                        "electronics",
                        2,
                        "aria",
                        "2000-01-15T10:00:00",
                        "2000-01-15T10:00:00",
                    ),
                    (
                        "p1002",
                        "Retro Phone",
                        "Classic rotary phone in good condition",
                        49.99,
                        "electronics",
                        5,
                        "eve",
                        "2000-02-20T14:30:00",
                        "2000-02-20T14:30:00",
                    ),
                    (
                        "p1003",
                        "Vintage Jeans",
                        "80s style jeans, size 32",
                        29.99,
                        "clothing",
                        3,
                        "milo",
                        "2000-03-10T09:15:00",
                        "2000-03-10T09:15:00",
                    ),
                    (
                        "p1004",
                        "Vintage Camera",
                        "Analog camera with film",
                        79.99,
                        "electronics",
                        1,
                        "aria",
                        "2000-04-05T16:45:00",
                        "2000-04-05T16:45:00",
                    ),
                    (
                        "p1005",
                        "Classic Book Collection",
                        "Set of 5 classic novels",
                        39.99,
                        "books",
                        2,
                        "eve",
                        "2000-05-12T11:20:00",
                        "2000-05-12T11:20:00",
                    ),
                ],
            )

            conn.commit()

    def _sync_counters(self) -> None:
        """Sync counters with existing data"""
        with self.session_manager.connect() as conn:
            product_row = conn.execute(
                "SELECT COALESCE(MAX(CAST(SUBSTR(product_id, 2) AS INTEGER)), 999) AS max_id FROM p2pstore_products"
            ).fetchone()
            order_row = conn.execute(
                "SELECT COALESCE(MAX(CAST(SUBSTR(order_id, 2) AS INTEGER)), 999) AS max_id FROM p2pstore_orders"
            ).fetchone()

        self._product_counter = count(int(product_row["max_id"]) + 1)
        self._order_counter = count(int(order_row["max_id"]) + 1)