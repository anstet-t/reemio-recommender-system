"""Product synchronization service.

Syncs products from the e-commerce public schema to the recommender schema.
"""

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from recommendation_service.infrastructure.database.models import (
    ProductEmbedding,
    SyncStatus,
)

logger = structlog.get_logger()


class ProductSyncService:
    """Service for synchronizing products from e-commerce to recommender."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_ecommerce_products(
        self, limit: int = 1000, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Fetch products from the e-commerce public schema."""
        query = text("""
            SELECT
                p.id,
                p.name,
                p.description,
                p."priceCents" as price_cents,
                p.stock,
                p."isActive" as is_active,
                c.name as category_name
            FROM public.products p
            LEFT JOIN public.categories c ON p."categoryId" = c.id
            ORDER BY p."createdAt" DESC
            LIMIT :limit OFFSET :offset
        """)
        result = await self.session.execute(query, {"limit": limit, "offset": offset})
        rows = result.fetchall()
        return [
            {
                "id": row.id,
                "name": row.name,
                "description": row.description,
                "price_cents": row.price_cents,
                "stock": row.stock,
                "is_active": row.is_active,
                "category_name": row.category_name,
            }
            for row in rows
        ]

    async def get_ecommerce_product_count(self) -> int:
        """Get total count of products in e-commerce schema."""
        query = text("SELECT COUNT(*) FROM public.products")
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def upsert_product_embedding(
        self, product: dict[str, Any], embedding: list[float] | None = None
    ) -> ProductEmbedding:
        """Upsert a product to the product_embeddings table."""
        # Check if product already exists
        query = text("""
            SELECT id FROM recommender.product_embeddings
            WHERE external_product_id = :external_id
        """)
        result = await self.session.execute(query, {"external_id": product["id"]})
        existing = result.scalar()

        now = datetime.now()  # Use naive datetime for DB

        if existing:
            # Update existing product
            update_query = text("""
                UPDATE recommender.product_embeddings
                SET name = :name,
                    category = :category,
                    price_cents = :price_cents,
                    stock = :stock,
                    is_active = :is_active,
                    embedding = :embedding,
                    updated_at = :updated_at,
                    embedding_updated_at = CASE
                        WHEN :embedding IS NOT NULL THEN :updated_at
                        ELSE embedding_updated_at
                    END
                WHERE external_product_id = :external_id
                RETURNING id
            """)
            await self.session.execute(
                update_query,
                {
                    "external_id": product["id"],
                    "name": product["name"],
                    "category": product.get("category_name"),
                    "price_cents": product["price_cents"],
                    "stock": product["stock"],
                    "is_active": product["is_active"],
                    "embedding": embedding,
                    "updated_at": now,
                },
            )
            logger.debug("Updated product embedding", external_id=product["id"])
        else:
            # Insert new product
            insert_query = text("""
                INSERT INTO recommender.product_embeddings
                (external_product_id, name, category, price_cents, stock, is_active,
                 embedding, popularity_score, created_at, updated_at, embedding_updated_at)
                VALUES
                (:external_id, :name, :category, :price_cents, :stock, :is_active,
                 :embedding, 0.0, :created_at, :updated_at, :embedding_updated_at)
            """)
            await self.session.execute(
                insert_query,
                {
                    "external_id": product["id"],
                    "name": product["name"],
                    "category": product.get("category_name"),
                    "price_cents": product["price_cents"],
                    "stock": product["stock"],
                    "is_active": product["is_active"],
                    "embedding": embedding,
                    "created_at": now,
                    "updated_at": now,
                    "embedding_updated_at": now if embedding else None,
                },
            )
            logger.debug("Inserted new product embedding", external_id=product["id"])

        return product

    async def sync_all_products(
        self, batch_size: int = 100, generate_embeddings: bool = False
    ) -> dict[str, int]:
        """
        Sync all products from e-commerce to recommender schema.

        Args:
            batch_size: Number of products to process per batch
            generate_embeddings: Whether to generate embeddings (requires embedding service)

        Returns:
            Summary of sync operation
        """
        # Update sync status to running
        await self._update_sync_status("products", "running")

        total_count = await self.get_ecommerce_product_count()
        logger.info("Starting product sync", total_products=total_count)

        synced = 0
        created = 0
        updated = 0
        errors = 0
        offset = 0

        while offset < total_count:
            try:
                products = await self.get_ecommerce_products(
                    limit=batch_size, offset=offset
                )

                for product in products:
                    try:
                        # Check if product exists
                        query = text("""
                            SELECT id FROM recommender.product_embeddings
                            WHERE external_product_id = :external_id
                        """)
                        result = await self.session.execute(
                            query, {"external_id": product["id"]}
                        )
                        exists = result.scalar() is not None

                        await self.upsert_product_embedding(product)

                        synced += 1
                        if exists:
                            updated += 1
                        else:
                            created += 1

                    except Exception as e:
                        logger.error(
                            "Error syncing product",
                            external_id=product["id"],
                            error=str(e),
                        )
                        errors += 1

                await self.session.commit()
                offset += batch_size
                logger.info(
                    "Batch synced", synced=synced, total=total_count, offset=offset
                )

            except Exception as e:
                logger.error("Error in batch sync", offset=offset, error=str(e))
                errors += 1
                offset += batch_size

        # Update sync status to idle
        await self._update_sync_status(
            "products", "idle", records_synced=synced, cursor=str(offset)
        )

        summary = {
            "total_products": total_count,
            "synced": synced,
            "created": created,
            "updated": updated,
            "errors": errors,
        }
        logger.info("Product sync completed", **summary)
        return summary

    async def _update_sync_status(
        self,
        sync_id: str,
        status: str,
        records_synced: int = 0,
        cursor: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update sync status record."""
        now = datetime.now()  # Use naive datetime for DB

        # Upsert sync status
        query = text("""
            INSERT INTO recommender.sync_status (id, status, records_synced, last_sync_cursor, last_sync_at, updated_at, error_message)
            VALUES (:id, :status, :records_synced, :cursor, :last_sync_at, :updated_at, :error_message)
            ON CONFLICT (id) DO UPDATE SET
                status = :status,
                records_synced = CASE
                    WHEN :records_synced > 0 THEN :records_synced
                    ELSE recommender.sync_status.records_synced
                END,
                last_sync_cursor = COALESCE(:cursor, recommender.sync_status.last_sync_cursor),
                last_sync_at = CASE
                    WHEN :status = 'idle' THEN :last_sync_at
                    ELSE recommender.sync_status.last_sync_at
                END,
                updated_at = :updated_at,
                error_message = :error_message
        """)
        await self.session.execute(
            query,
            {
                "id": sync_id,
                "status": status,
                "records_synced": records_synced,
                "cursor": cursor,
                "last_sync_at": now if status == "idle" else None,
                "updated_at": now,
                "error_message": error_message,
            },
        )
        await self.session.commit()
