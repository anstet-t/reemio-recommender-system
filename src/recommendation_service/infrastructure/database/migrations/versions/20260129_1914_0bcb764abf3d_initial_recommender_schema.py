"""Initial recommender schema

Revision ID: 0bcb764abf3d
Revises:
Create Date: 2026-01-29 19:14:12.750415+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0bcb764abf3d'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use JSON for embeddings since pgvector extension is not available on the server
    # This can be changed to Vector(384) if pgvector is installed later
    embedding_type = sa.JSON()

    # Create cart_abandonments table
    op.create_table('cart_abandonments',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('external_user_id', sa.String(length=255), nullable=False),
    sa.Column('external_cart_id', sa.String(length=255), nullable=False),
    sa.Column('cart_snapshot', sa.JSON(), nullable=False),
    sa.Column('abandonment_detected_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('reminder_sent_at', sa.DateTime(), nullable=True),
    sa.Column('reminder_count', sa.Integer(), nullable=False),
    sa.Column('recovered', sa.Boolean(), nullable=False),
    sa.Column('recovered_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='recommender'
    )
    op.create_index('ix_cart_abandonments_pending', 'cart_abandonments', ['external_user_id', 'reminder_sent_at'], unique=False, schema='recommender')
    op.create_index(op.f('ix_recommender_cart_abandonments_external_user_id'), 'cart_abandonments', ['external_user_id'], unique=False, schema='recommender')

    # Create email_campaigns table
    op.create_table('email_campaigns',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('external_user_id', sa.String(length=255), nullable=False),
    sa.Column('email_type', sa.Enum('CART_ABANDONMENT', 'NEW_PRODUCTS', 'WEEKLY_DIGEST', 'PERSONALIZED_PICKS', 'BACK_IN_STOCK', name='emailtype', schema='recommender'), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('recommended_product_ids', sa.JSON(), nullable=True),
    sa.Column('status', sa.Enum('PENDING', 'SENT', 'DELIVERED', 'OPENED', 'CLICKED', 'BOUNCED', 'UNSUBSCRIBED', name='emailstatus', schema='recommender'), nullable=False),
    sa.Column('scheduled_at', sa.DateTime(), nullable=True),
    sa.Column('sent_at', sa.DateTime(), nullable=True),
    sa.Column('opened_at', sa.DateTime(), nullable=True),
    sa.Column('clicked_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='recommender'
    )
    op.create_index('ix_email_campaigns_scheduled', 'email_campaigns', ['scheduled_at'], unique=False, schema='recommender')
    op.create_index(op.f('ix_recommender_email_campaigns_external_user_id'), 'email_campaigns', ['external_user_id'], unique=False, schema='recommender')
    op.create_index(op.f('ix_recommender_email_campaigns_status'), 'email_campaigns', ['status'], unique=False, schema='recommender')

    # Create product_embeddings table
    op.create_table('product_embeddings',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('external_product_id', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=500), nullable=False),
    sa.Column('category', sa.String(length=255), nullable=True),
    sa.Column('price_cents', sa.Integer(), nullable=False),
    sa.Column('stock', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('embedding', embedding_type, nullable=True),
    sa.Column('popularity_score', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('embedding_updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='recommender'
    )
    op.create_index('ix_product_embeddings_active', 'product_embeddings', ['is_active'], unique=False, schema='recommender')
    op.create_index('ix_product_embeddings_category', 'product_embeddings', ['category'], unique=False, schema='recommender')
    op.create_index(op.f('ix_recommender_product_embeddings_external_product_id'), 'product_embeddings', ['external_product_id'], unique=True, schema='recommender')

    # Create recommendation_performance table
    op.create_table('recommendation_performance',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('date', sa.DateTime(), nullable=False),
    sa.Column('context', sa.String(length=50), nullable=False),
    sa.Column('total_impressions', sa.Integer(), nullable=False),
    sa.Column('total_clicks', sa.Integer(), nullable=False),
    sa.Column('total_conversions', sa.Integer(), nullable=False),
    sa.Column('avg_position_clicked', sa.Float(), nullable=True),
    sa.Column('revenue_attributed_cents', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='recommender'
    )
    op.create_index('ix_rec_performance_date_context', 'recommendation_performance', ['date', 'context'], unique=True, schema='recommender')

    # Create sync_status table
    op.create_table('sync_status',
    sa.Column('id', sa.String(length=50), nullable=False),
    sa.Column('last_sync_at', sa.DateTime(), nullable=True),
    sa.Column('last_sync_cursor', sa.String(length=255), nullable=True),
    sa.Column('records_synced', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='recommender'
    )

    # Create user_email_preferences table
    op.create_table('user_email_preferences',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('external_user_id', sa.String(length=255), nullable=False),
    sa.Column('cart_abandonment_enabled', sa.Boolean(), nullable=False),
    sa.Column('new_products_enabled', sa.Boolean(), nullable=False),
    sa.Column('weekly_digest_enabled', sa.Boolean(), nullable=False),
    sa.Column('personalized_picks_enabled', sa.Boolean(), nullable=False),
    sa.Column('back_in_stock_enabled', sa.Boolean(), nullable=False),
    sa.Column('frequency_cap_per_week', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='recommender'
    )
    op.create_index(op.f('ix_recommender_user_email_preferences_external_user_id'), 'user_email_preferences', ['external_user_id'], unique=True, schema='recommender')

    # Create user_interactions table
    op.create_table('user_interactions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('external_user_id', sa.String(length=255), nullable=False),
    sa.Column('external_product_id', sa.String(length=255), nullable=True),
    sa.Column('interaction_type', sa.Enum('VIEW', 'CART_ADD', 'CART_REMOVE', 'PURCHASE', 'WISHLIST_ADD', 'SEARCH', 'RECOMMENDATION_CLICK', 'RECOMMENDATION_VIEW', name='interactiontype', schema='recommender'), nullable=False),
    sa.Column('search_query', sa.Text(), nullable=True),
    sa.Column('recommendation_context', sa.String(length=50), nullable=True),
    sa.Column('recommendation_position', sa.Integer(), nullable=True),
    sa.Column('recommendation_request_id', sa.String(length=255), nullable=True),
    sa.Column('session_id', sa.String(length=255), nullable=True),
    sa.Column('extra_data', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='recommender'
    )
    op.create_index(op.f('ix_recommender_user_interactions_created_at'), 'user_interactions', ['created_at'], unique=False, schema='recommender')
    op.create_index(op.f('ix_recommender_user_interactions_external_product_id'), 'user_interactions', ['external_product_id'], unique=False, schema='recommender')
    op.create_index(op.f('ix_recommender_user_interactions_external_user_id'), 'user_interactions', ['external_user_id'], unique=False, schema='recommender')
    op.create_index(op.f('ix_recommender_user_interactions_interaction_type'), 'user_interactions', ['interaction_type'], unique=False, schema='recommender')
    op.create_index('ix_user_interactions_user_type_created', 'user_interactions', ['external_user_id', 'interaction_type', 'created_at'], unique=False, schema='recommender')

    # Create user_preference_embeddings table
    op.create_table('user_preference_embeddings',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('external_user_id', sa.String(length=255), nullable=False),
    sa.Column('embedding', embedding_type, nullable=True),
    sa.Column('top_categories', sa.JSON(), nullable=True),
    sa.Column('avg_price_min', sa.Float(), nullable=True),
    sa.Column('avg_price_max', sa.Float(), nullable=True),
    sa.Column('interaction_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_active_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='recommender'
    )
    op.create_index(op.f('ix_recommender_user_preference_embeddings_external_user_id'), 'user_preference_embeddings', ['external_user_id'], unique=True, schema='recommender')


def downgrade() -> None:
    # Drop all recommender schema tables
    op.drop_index(op.f('ix_recommender_user_preference_embeddings_external_user_id'), table_name='user_preference_embeddings', schema='recommender')
    op.drop_table('user_preference_embeddings', schema='recommender')

    op.drop_index('ix_user_interactions_user_type_created', table_name='user_interactions', schema='recommender')
    op.drop_index(op.f('ix_recommender_user_interactions_interaction_type'), table_name='user_interactions', schema='recommender')
    op.drop_index(op.f('ix_recommender_user_interactions_external_user_id'), table_name='user_interactions', schema='recommender')
    op.drop_index(op.f('ix_recommender_user_interactions_external_product_id'), table_name='user_interactions', schema='recommender')
    op.drop_index(op.f('ix_recommender_user_interactions_created_at'), table_name='user_interactions', schema='recommender')
    op.drop_table('user_interactions', schema='recommender')

    op.drop_index(op.f('ix_recommender_user_email_preferences_external_user_id'), table_name='user_email_preferences', schema='recommender')
    op.drop_table('user_email_preferences', schema='recommender')

    op.drop_table('sync_status', schema='recommender')

    op.drop_index('ix_rec_performance_date_context', table_name='recommendation_performance', schema='recommender')
    op.drop_table('recommendation_performance', schema='recommender')

    op.drop_index(op.f('ix_recommender_product_embeddings_external_product_id'), table_name='product_embeddings', schema='recommender')
    op.drop_index('ix_product_embeddings_category', table_name='product_embeddings', schema='recommender')
    op.drop_index('ix_product_embeddings_active', table_name='product_embeddings', schema='recommender')
    op.drop_table('product_embeddings', schema='recommender')

    op.drop_index(op.f('ix_recommender_email_campaigns_status'), table_name='email_campaigns', schema='recommender')
    op.drop_index(op.f('ix_recommender_email_campaigns_external_user_id'), table_name='email_campaigns', schema='recommender')
    op.drop_index('ix_email_campaigns_scheduled', table_name='email_campaigns', schema='recommender')
    op.drop_table('email_campaigns', schema='recommender')

    op.drop_index(op.f('ix_recommender_cart_abandonments_external_user_id'), table_name='cart_abandonments', schema='recommender')
    op.drop_index('ix_cart_abandonments_pending', table_name='cart_abandonments', schema='recommender')
    op.drop_table('cart_abandonments', schema='recommender')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS recommender.emailtype')
    op.execute('DROP TYPE IF EXISTS recommender.emailstatus')
    op.execute('DROP TYPE IF EXISTS recommender.interactiontype')
