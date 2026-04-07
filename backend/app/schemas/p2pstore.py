from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ProductBase(BaseModel):
    name: str = Field(..., description="Product name")
    description: str = Field(..., description="Product description")
    price: float = Field(..., gt=0, description="Product price")
    category: str = Field(..., description="Product category")
    stock: int = Field(..., ge=0, description="Product stock")


class ProductCreate(ProductBase):
    seller_id: str = Field(..., description="Seller ID")


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Product name")
    description: Optional[str] = Field(None, description="Product description")
    price: Optional[float] = Field(None, gt=0, description="Product price")
    category: Optional[str] = Field(None, description="Product category")
    stock: Optional[int] = Field(None, ge=0, description="Product stock")


class Product(ProductBase):
    product_id: str = Field(..., description="Product ID")
    seller_id: str = Field(..., description="Seller ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    products: List[Product] = Field(default_factory=list, description="List of products")
    total: int = Field(0, description="Total number of products")


class ProductDetailResponse(BaseModel):
    product: Product = Field(..., description="Product details")


class Category(BaseModel):
    slug: str = Field(..., description="Category slug")
    name: str = Field(..., description="Category name")
    description: Optional[str] = Field(None, description="Category description")

    class Config:
        from_attributes = True


class CategoryListResponse(BaseModel):
    categories: List[Category] = Field(default_factory=list, description="List of categories")


class OrderBase(BaseModel):
    product_id: str = Field(..., description="Product ID")
    quantity: int = Field(..., gt=0, description="Order quantity")


class OrderCreate(OrderBase):
    buyer_id: str = Field(..., description="Buyer ID")


class Order(OrderBase):
    order_id: str = Field(..., description="Order ID")
    buyer_id: str = Field(..., description="Buyer ID")
    seller_id: str = Field(..., description="Seller ID")
    total_price: float = Field(..., description="Total order price")
    status: str = Field(..., description="Order status")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    orders: List[Order] = Field(default_factory=list, description="List of orders")
    total: int = Field(0, description="Total number of orders")


class OrderDetailResponse(BaseModel):
    order: Order = Field(..., description="Order details")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code")