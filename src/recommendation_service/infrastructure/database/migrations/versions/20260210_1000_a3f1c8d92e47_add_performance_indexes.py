"""Add performance indexes for recommendation queries.

Partial and covering indexes targeting the exact query patterns used by
the recommendation engine's hot path: similar product search, collaborative
filtering, and user preference lookups.

Revision ID: a3f1c8d92e47
Revises: 016b2a819b85
Create Date: 2026-02-10 10:00:00.000000+00:00
"""

from alembic import op

revision = "a3f1c8d92e47"
down_revision = "016b2a819b85"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Partial index for _search_similar_products():
    # WHERE is_active = true AND embedding IS NOT NULL ORDER BY popularity_score DESC
    # Only indexes active products with embeddings, much smaller than a full index.
    op.execute("""
        CREATE INDEX ix_pe_active_embedding_popularity
        ON recommender.product_embeddings (popularity_score DESC NULLS LAST)
        WHERE is_active = true AND embedding IS NOT NULL
    """)

    # Filtered index for collaborative filtering queries:
    # Speeds up the recommended_products CTE that filters by high-value interaction types.
    op.execute("""
        CREATE INDEX ix_ui_product_type_purchase
        ON recommender.user_interactions (external_product_id, external_user_id)
        WHERE interaction_type IN ('PURCHASE', 'CART_ADD', 'WISHLIST_ADD')
    """)

    # Composite index for product embedding joins in collaborative filtering
    op.create_index(
        "ix_pe_external_product_active",
        "product_embeddings",
        ["external_product_id", "is_active"],
        schema="recommender",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pe_external_product_active",
        table_name="product_embeddings",
        schema="recommender",
    )
    op.execute("DROP INDEX IF EXISTS recommender.ix_ui_product_type_purchase")
    op.execute("DROP INDEX IF EXISTS recommender.ix_pe_active_embedding_popularity")
