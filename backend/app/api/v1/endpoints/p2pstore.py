from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional
from app.schemas.p2pstore import (
    ProductListResponse, ProductDetailResponse, ProductCreate, ProductUpdate,
    CategoryListResponse,
    OrderListResponse, OrderDetailResponse, OrderCreate,
    ErrorResponse
)
from app.services.p2pstore_service import P2PStoreService

router = APIRouter()


def _get_service(request: Request) -> P2PStoreService:
    return request.app.state.container.p2pstore_service


@router.get("/products", response_model=ProductListResponse)
async def get_products(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of products"),
):
    """Get list of products"""
    try:
        service = _get_service(request)
        products = service.list_products(category=category, limit=limit)
        return ProductListResponse(products=products, total=len(products))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}", response_model=ProductDetailResponse)
async def get_product(
    product_id: str,
    request: Request,
):
    """Get product details"""
    try:
        service = _get_service(request)
        product = service.get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return ProductDetailResponse(product=product)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products", response_model=ProductDetailResponse)
async def create_product(
    product: ProductCreate,
    request: Request,
):
    """Create a new product"""
    try:
        service = _get_service(request)
        created_product = service.create_product(product)
        return ProductDetailResponse(product=created_product)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/products/{product_id}", response_model=ProductDetailResponse)
async def update_product(
    product_id: str,
    product: ProductUpdate,
    request: Request,
):
    """Update a product"""
    try:
        service = _get_service(request)
        updated_product = service.update_product(product_id, product)
        if not updated_product:
            raise HTTPException(status_code=404, detail="Product not found")
        return ProductDetailResponse(product=updated_product)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: str,
    request: Request,
):
    """Delete a product"""
    try:
        service = _get_service(request)
        success = service.delete_product(product_id)
        if not success:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"message": "Product deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories", response_model=CategoryListResponse)
async def get_categories(
    request: Request,
):
    """Get list of categories"""
    try:
        service = _get_service(request)
        categories = service.list_categories()
        return CategoryListResponse(categories=categories)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders", response_model=OrderDetailResponse)
async def create_order(
    order: OrderCreate,
    request: Request,
):
    """Create a new order"""
    try:
        service = _get_service(request)
        created_order = service.create_order(order)
        return OrderDetailResponse(order=created_order)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders", response_model=OrderListResponse)
async def get_orders(
    request: Request,
    limit: int = Query(20, ge=1, le=100, description="Maximum number of orders"),
):
    """Get list of orders"""
    try:
        service = _get_service(request)
        orders = service.list_orders(limit=limit)
        return OrderListResponse(orders=orders, total=len(orders))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders/{order_id}", response_model=OrderDetailResponse)
async def get_order(
    order_id: str,
    request: Request,
):
    """Get order details"""
    try:
        service = _get_service(request)
        order = service.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return OrderDetailResponse(order=order)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))