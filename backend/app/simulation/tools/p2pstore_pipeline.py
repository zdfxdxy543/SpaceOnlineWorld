from __future__ import annotations

from app.consistency.checker import ConsistencyChecker
from app.domain.events import StoryEvent
from app.infrastructure.llm.structured_content import AbstractStructuredContentGenerator
from app.services.p2pstore_service import P2PStoreService
from app.simulation.protocol import (
    ActionRequest,
    CapabilitySpec,
    ConsistencyCheckResult,
    ContentGenerationRequest,
    FactExecutionResult,
    GeneratedContent,
    PublicationResult,
)
from app.simulation.tools.workflow import AbstractCapabilityWorkflow, FiveStageToolExecutor


class P2PStoreCreateProductWorkflow(AbstractCapabilityWorkflow):
    def __init__(
        self,
        p2pstore_service: P2PStoreService,
        consistency_checker: ConsistencyChecker,
    ) -> None:
        self.p2pstore_service = p2pstore_service
        self.consistency_checker = consistency_checker

    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="p2pstore.create_product",
            site="p2pstore",
            description="Create a new product listing through the fact-first pipeline.",
            input_schema={
                "name": "string",
                "description": "string",
                "price": "number",
                "category": "string",
                "allowed_categories": self._available_category_slugs(),
                "stock": "integer",
                "seller_id": "string",
            },
            read_only=False,
        )

    def _available_category_slugs(self) -> list[str]:
        return [item.slug for item in self.p2pstore_service.list_categories()]

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        name = str(request.payload.get("name", ""))
        description = str(request.payload.get("description", ""))
        price = float(request.payload.get("price", 0.0))
        category = str(request.payload.get("category", "")).strip()
        stock = int(request.payload.get("stock", 0))
        seller_id = str(request.payload.get("seller_id", request.actor_id)).strip()

        if not category:
            category = "other"

        allowed_categories = self._available_category_slugs()
        if category not in allowed_categories:
            raise ValueError(
                f"Invalid category '{category}'. Allowed categories: {', '.join(allowed_categories)}"
            )

        if not name or not description or price <= 0 or not category or stock <= 0 or not seller_id:
            raise ValueError("Missing required product fields")

        # Generate product ID
        product_id = self.p2pstore_service.repository.generate_product_id()

        return FactExecutionResult(
            capability=request.capability,
            site="p2pstore",
            actor_id=request.actor_id,
            facts=[
                f"产品ID={product_id}",
                f"产品名称={name}",
                f"产品类别={category}",
                f"产品价格={price}",
                f"产品库存={stock}",
                f"卖家ID={seller_id}",
            ],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="P2P商店产品创建事实已记录，等待内容生成。",
                    metadata={"product_id": product_id, "name": name},
                ),
                StoryEvent(
                    name="FactPersisted",
                    detail="P2P商店产品事实已持久化到数据库。",
                    metadata={"product_id": product_id},
                ),
            ],
            output={
                "product_id": product_id,
                "name": name,
                "category": category,
                "status": "draft_created",
            },
            generation_context={
                "product_id": product_id,
                "name": name,
                "description": description,
                "price": price,
                "category": category,
                "stock": stock,
                "seller_id": seller_id,
            },
            requires_content_generation=True,
        )

    def build_generation_request(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
    ) -> ContentGenerationRequest:
        return ContentGenerationRequest(
            capability=request.capability,
            site="p2pstore",
            actor_id=request.actor_id,
            instruction=(
                "Based on the product information, generate a detailed and attractive product description. "
                "The description should highlight the product's features, benefits, and any unique selling points. "
                "Make it sound professional and enticing for potential buyers."
            ),
            desired_fields=["description"],
            fact_context=fact_result.generation_context,
            style_context={"tone": "product_description", "avoid_meta_prompt": True, "language": "en"},
        )

    def validate_generated_content(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        generated_content: GeneratedContent,
    ) -> ConsistencyCheckResult:
        description = str(generated_content.fields.get("description", ""))
        normalized_fields = {"description": description}
        violations = []
        violations.extend(self.consistency_checker.validate_required_fields(normalized_fields, ["description"]))
        violations.extend(self.consistency_checker.detect_unresolved_references(normalized_fields))
        return ConsistencyCheckResult(
            passed=not violations,
            violations=violations,
            normalized_fields=normalized_fields,
        )

    def publish(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        validation_result: ConsistencyCheckResult,
    ) -> PublicationResult:
        from app.schemas.p2pstore import ProductCreate

        product_data = ProductCreate(
            name=fact_result.generation_context["name"],
            description=validation_result.normalized_fields["description"],
            price=fact_result.generation_context["price"],
            category=fact_result.generation_context["category"],
            stock=fact_result.generation_context["stock"],
            seller_id=fact_result.generation_context["seller_id"],
        )

        product = self.p2pstore_service.create_product(product_data)
        return PublicationResult(
            output={
                "product_id": product.product_id,
                "product": {
                    "product_id": product.product_id,
                    "name": product.name,
                    "description": product.description,
                    "price": product.price,
                    "category": product.category,
                    "stock": product.stock,
                    "seller_id": product.seller_id,
                    "created_at": product.created_at,
                },
                "publication_status": "published",
            },
            facts=[f"已创建产品={product.product_id}"],
            events=[
                StoryEvent(
                    name="ContentPublished",
                    detail="P2P商店产品已通过五步骤链正式发布。",
                    metadata={"product_id": product.product_id, "name": product.name},
                )
            ],
        )


class P2PStoreReadProductsWorkflow(AbstractCapabilityWorkflow):
    def __init__(self, p2pstore_service: P2PStoreService) -> None:
        self.p2pstore_service = p2pstore_service

    @property
    def capability(self) -> CapabilitySpec:
        return CapabilitySpec(
            name="p2pstore.read_products",
            site="p2pstore",
            description="Read products with optional category filter.",
            input_schema={
                "category": "string optional",
                "limit": "integer optional",
            },
            read_only=True,
        )

    def execute_facts(self, request: ActionRequest) -> FactExecutionResult:
        category = request.payload.get("category")
        limit = int(request.payload.get("limit", 20))
        products = self.p2pstore_service.list_products(category=category, limit=limit)

        return FactExecutionResult(
            capability=request.capability,
            site="p2pstore",
            actor_id=request.actor_id,
            facts=[
                f"读取分类={category or 'all'}",
                f"读取产品数量={len(products)}",
            ],
            events=[
                StoryEvent(
                    name="WorldActionExecuted",
                    detail="P2P商店产品读取完成。",
                    metadata={"category": category},
                ),
            ],
            output={
                "products": [
                    {
                        "product_id": product.product_id,
                        "name": product.name,
                        "description": product.description,
                        "price": product.price,
                        "category": product.category,
                        "stock": product.stock,
                        "seller_id": product.seller_id,
                    }
                    for product in products
                ],
                "total": len(products),
                "category": category,
            },
            generation_context={"category": category},
            requires_content_generation=False,
        )

    def publish(
        self,
        request: ActionRequest,
        fact_result: FactExecutionResult,
        validation_result: ConsistencyCheckResult,
    ) -> PublicationResult:
        return PublicationResult(output=fact_result.output, facts=[], events=[])


class P2PStorePipelineToolExecutor(FiveStageToolExecutor):
    def __init__(
        self,
        p2pstore_service: P2PStoreService,
        consistency_checker: ConsistencyChecker,
        content_generator: AbstractStructuredContentGenerator,
    ) -> None:
        workflows = [
            P2PStoreReadProductsWorkflow(p2pstore_service),
            P2PStoreCreateProductWorkflow(p2pstore_service, consistency_checker),
        ]
        super().__init__(workflows=workflows, content_generator=content_generator)