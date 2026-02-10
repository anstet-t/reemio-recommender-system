"""Add full text search support with tsvector and pg_trgm.

Enables PostgreSQL full-text search and trigram fuzzy matching on
product_embeddings for search-based recommendations.

Revision ID: b7e2f4a19c83
Revises: 016b2a819b85
Create Date: 2026-02-10 11:00:00.000000+00:00
"""

from alembic import op

revision = "b7e2f4a19c83"
down_revision = "016b2a819b85"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pg_trgm extension for fuzzy matching
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Add search_vector tsvector column
    op.execute("""
        ALTER TABLE recommender.product_embeddings
        ADD COLUMN IF NOT EXISTS search_vector tsvector
    """)

    # Populate search_vector from existing data
    # name gets weight A (highest), category gets weight B
    op.execute("""
        UPDATE recommender.product_embeddings
        SET search_vector =
            setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(category, '')), 'B')
    """)

    # GIN index on search_vector for fast full-text search
    op.execute("""
        CREATE INDEX ix_pe_search_vector
        ON recommender.product_embeddings
        USING GIN (search_vector)
    """)

    # GIN trigram index on name for fuzzy matching
    op.execute("""
        CREATE INDEX ix_pe_name_trgm
        ON recommender.product_embeddings
        USING GIN (name gin_trgm_ops)
    """)

    # Trigger to auto-update search_vector on INSERT/UPDATE of name or category
    op.execute("""
        CREATE OR REPLACE FUNCTION recommender.update_search_vector()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.name, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.category, '')), 'B');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        CREATE TRIGGER trg_update_search_vector
        BEFORE INSERT OR UPDATE OF name, category
        ON recommender.product_embeddings
        FOR EACH ROW
        EXECUTE FUNCTION recommender.update_search_vector()
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_update_search_vector ON recommender.product_embeddings"
    )
    op.execute("DROP FUNCTION IF EXISTS recommender.update_search_vector()")
    op.execute("DROP INDEX IF EXISTS recommender.ix_pe_name_trgm")
    op.execute("DROP INDEX IF EXISTS recommender.ix_pe_search_vector")
    op.execute(
        "ALTER TABLE recommender.product_embeddings DROP COLUMN IF EXISTS search_vector"
    )
