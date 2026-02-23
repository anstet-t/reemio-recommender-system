"""User preference embedding service.

Builds user preference vectors from interaction history with weighted signals.
"""

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import orjson
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class UserPreferenceService:
    """Service for building and updating user preference embeddings."""

    # Interaction type weights
    INTERACTION_WEIGHTS = {
        "PURCHASE": 5.0,
        "CART_ADD": 3.0,
        "CART_REMOVE": -1.0,
        "WISHLIST_ADD": 2.0,
        "VIEW": 1.0,
        "RECOMMENDATION_CLICK": 1.5,
        "RECOMMENDATION_VIEW": 0.5,
    }

    # Recency decay: weight = base_weight * exp(-days / decay_factor)
    RECENCY_DECAY_DAYS = 30.0

    def __init__(self, session: AsyncSession):
        self.session = session

    async def update_user_preference(
        self, user_id: str, lookback_days: int = 90
    ) -> dict[str, Any]:
        """
        Build or update user preference embedding from interaction history.

        Args:
            user_id: The user's ID
            lookback_days: Number of days to look back for interactions

        Returns:
            Summary of the operation
        """
        cutoff_date = datetime.now() - timedelta(days=lookback_days)

        # Get user interactions with product embeddings
        query = text("""
            SELECT
                ui.interaction_type,
                ui.external_product_id,
                ui.created_at,
                pe.embedding,
                pe.category,
                pe.price_cents
            FROM recommender.user_interactions ui
            JOIN recommender.product_embeddings pe
                ON ui.external_product_id = pe.external_product_id
            WHERE ui.external_user_id = :user_id
            AND ui.created_at >= :cutoff_date
            AND pe.embedding IS NOT NULL
            ORDER BY ui.created_at DESC
        """)

        result = await self.session.execute(
            query, {"user_id": user_id, "cutoff_date": cutoff_date}
        )
        interactions = result.fetchall()

        if not interactions:
            logger.info("No interactions found for user", user_id=user_id)
            return {"user_id": user_id, "interactions_processed": 0}

        # Build weighted embedding
        weighted_embeddings = []
        category_counts: dict[str, int] = defaultdict(int)
        prices = []
        now = datetime.now()  # Use naive datetime for DB

        for interaction in interactions:
            interaction_type = interaction.interaction_type
            created_at = interaction.created_at
            embedding = interaction.embedding
            category = interaction.category
            price_cents = interaction.price_cents

            # Parse embedding
            if isinstance(embedding, str):
                embedding = orjson.loads(embedding)

            # Calculate weight with recency decay
            if hasattr(interaction_type, "value"):
                interaction_key = str(interaction_type.value)
            elif hasattr(interaction_type, "name"):
                interaction_key = str(interaction_type.name)
            else:
                interaction_key = str(interaction_type)
            base_weight = self.INTERACTION_WEIGHTS.get(
                interaction_key,
                self.INTERACTION_WEIGHTS.get(interaction_key.upper(), 1.0),
            )
            days_old = (now - created_at).days
            recency_factor = self._calculate_recency_weight(days_old)
            final_weight = base_weight * recency_factor

            # Add weighted embedding
            weighted_embeddings.append((embedding, final_weight))

            # Track category and price stats
            if category:
                category_counts[category] += 1
            if price_cents:
                prices.append(price_cents)

        # Aggregate embeddings
        aggregated_embedding = self._aggregate_weighted_embeddings(weighted_embeddings)

        # Calculate stats
        top_categories = sorted(
            category_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]
        top_categories_list = [cat for cat, _ in top_categories]

        avg_price_min = min(prices) if prices else None
        avg_price_max = max(prices) if prices else None

        # Upsert user preference embedding
        await self._upsert_user_preference(
            user_id=user_id,
            embedding=aggregated_embedding,
            top_categories=top_categories_list,
            avg_price_min=avg_price_min,
            avg_price_max=avg_price_max,
            interaction_count=len(interactions),
        )

        logger.info(
            "Updated user preference",
            user_id=user_id,
            interactions=len(interactions),
            top_categories=top_categories_list[:3],
        )

        return {
            "user_id": user_id,
            "interactions_processed": len(interactions),
            "top_categories": top_categories_list,
        }

    async def update_all_active_users(
        self, min_interactions: int = 3, batch_size: int = 100
    ) -> dict[str, int]:
        """
        Update preference embeddings for all active users.

        Args:
            min_interactions: Minimum interactions required to build preference
            batch_size: Number of users to process per batch

        Returns:
            Summary of the operation
        """
        # Get active users with enough interactions
        query = text("""
            SELECT DISTINCT external_user_id, COUNT(*) as interaction_count
            FROM recommender.user_interactions
            WHERE created_at >= NOW() - INTERVAL '90 days'
            GROUP BY external_user_id
            HAVING COUNT(*) >= :min_interactions
            ORDER BY COUNT(*) DESC
        """)

        result = await self.session.execute(query, {"min_interactions": min_interactions})
        users = result.fetchall()

        updated = 0
        errors = 0

        for user in users:
            try:
                await self.update_user_preference(user.external_user_id)
                updated += 1
            except Exception as e:
                logger.error(
                    "Error updating user preference",
                    user_id=user.external_user_id,
                    error=str(e),
                )
                errors += 1

        return {"updated": updated, "errors": errors, "total_users": len(users)}

    def _calculate_recency_weight(self, days_old: int) -> float:
        """Calculate recency decay weight."""
        return math.exp(-days_old / self.RECENCY_DECAY_DAYS)

    def _aggregate_weighted_embeddings(
        self, weighted_embeddings: list[tuple[list[float], float]]
    ) -> list[float]:
        """Aggregate multiple embeddings with weights using numpy."""
        if not weighted_embeddings:
            return []

        embeddings = np.array([e for e, _ in weighted_embeddings], dtype=np.float32)
        weights = np.array([w for _, w in weighted_embeddings], dtype=np.float32)
        total_weight = weights.sum()

        if total_weight > 0:
            aggregated = (embeddings * weights[:, np.newaxis]).sum(axis=0) / total_weight
        else:
            aggregated = embeddings.mean(axis=0)

        # Normalize the vector
        norm = np.linalg.norm(aggregated)
        if norm > 0:
            aggregated = aggregated / norm

        return aggregated.tolist()

    async def _upsert_user_preference(
        self,
        user_id: str,
        embedding: list[float],
        top_categories: list[str],
        avg_price_min: int | None,
        avg_price_max: int | None,
        interaction_count: int,
    ) -> None:
        """Upsert user preference embedding to database."""
        now = datetime.now()  # Use naive datetime for DB

        query = text("""
            INSERT INTO recommender.user_preference_embeddings
            (external_user_id, embedding, top_categories, avg_price_min, avg_price_max,
             interaction_count, created_at, updated_at, last_active_at)
            VALUES
            (:user_id, :embedding, :top_categories, :avg_price_min, :avg_price_max,
             :interaction_count, :now, :now, :now)
            ON CONFLICT (external_user_id) DO UPDATE SET
                embedding = :embedding,
                top_categories = :top_categories,
                avg_price_min = :avg_price_min,
                avg_price_max = :avg_price_max,
                interaction_count = :interaction_count,
                updated_at = :now,
                last_active_at = :now
        """)

        await self.session.execute(
            query,
            {
                "user_id": user_id,
                "embedding": orjson.dumps(embedding).decode(),
                "top_categories": orjson.dumps(top_categories).decode(),
                "avg_price_min": avg_price_min / 100 if avg_price_min else None,
                "avg_price_max": avg_price_max / 100 if avg_price_max else None,
                "interaction_count": interaction_count,
                "now": now,
            },
        )
        await self.session.commit()
