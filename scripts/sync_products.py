#!/usr/bin/env python3
"""CLI script to sync products from e-commerce to recommender schema and generate embeddings."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog

from recommendation_service.infrastructure.database.connection import get_db_session
from recommendation_service.services.embedding import EmbeddingService
from recommendation_service.services.product_sync import ProductSyncService

logger = structlog.get_logger()


async def main():
    """Main sync function."""
    logger.info("Starting product sync")

    async with get_db_session() as session:
        # Sync products
        sync_service = ProductSyncService(session)
        logger.info("Syncing products from e-commerce database")
        sync_result = await sync_service.sync_all_products(batch_size=100)
        logger.info("Product sync completed", **sync_result)

        # Generate embeddings
        embedding_service = EmbeddingService(session)
        logger.info("Generating embeddings for products")
        embedding_result = await embedding_service.update_product_embeddings(
            batch_size=50, only_missing=True
        )
        logger.info("Embedding generation completed", **embedding_result)

    logger.info("All operations completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
