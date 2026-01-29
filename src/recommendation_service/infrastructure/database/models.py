"""SQLAlchemy models for the recommendation system.

These models are stored in the 'recommender' schema, separate from the
e-commerce tables but in the same database for efficient joins.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, Optional

# Try to import pgvector, fall back to JSON if not available
try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False
    Vector = None
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from recommendation_service.config import get_settings

# Get embedding dimension from settings
settings = get_settings()
EMBEDDING_DIM = settings.embedding_dimension

# Schema for all recommendation tables
SCHEMA = "recommender"


class Base(DeclarativeBase):
    """Base class for all models."""

    __table_args__ = {"schema": SCHEMA}


# =============================================================================
# Enums
# =============================================================================


class InteractionType(str, PyEnum):
    """Types of user interactions."""

    VIEW = "view"
    CART_ADD = "cart_add"
    CART_REMOVE = "cart_remove"
    PURCHASE = "purchase"
    WISHLIST_ADD = "wishlist_add"
    SEARCH = "search"
    RECOMMENDATION_CLICK = "recommendation_click"
    RECOMMENDATION_VIEW = "recommendation_view"


class EmailType(str, PyEnum):
    """Types of email campaigns."""

    CART_ABANDONMENT = "cart_abandonment"
    NEW_PRODUCTS = "new_products"
    WEEKLY_DIGEST = "weekly_digest"
    PERSONALIZED_PICKS = "personalized_picks"
    BACK_IN_STOCK = "back_in_stock"


class EmailStatus(str, PyEnum):
    """Email campaign status."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"


# =============================================================================
# Product Embeddings
# =============================================================================


class ProductEmbedding(Base):
    """Product embeddings for similarity search.

    Links to the products table in the public schema via external_product_id.
    """

    __tablename__ = "product_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_product_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(255))
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Vector embedding (384 dimensions for all-MiniLM-L6-v2)
    # Uses pgvector if available, otherwise stores as JSON
    if HAS_PGVECTOR:
        embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    else:
        embedding: Mapped[Any] = mapped_column(JSON, nullable=True)  # type: ignore

    # Popularity score (0-1, updated periodically)
    popularity_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    embedding_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    __table_args__ = (
        Index("ix_product_embeddings_category", "category"),
        Index("ix_product_embeddings_active", "is_active"),
        {"schema": SCHEMA},
    )


# =============================================================================
# User Preference Embeddings
# =============================================================================


class UserPreferenceEmbedding(Base):
    """User preference embeddings for personalization.

    Links to the users table in the public schema via external_user_id.
    """

    __tablename__ = "user_preference_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_user_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    # Vector embedding representing user preferences
    # Uses pgvector if available, otherwise stores as JSON
    if HAS_PGVECTOR:
        embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    else:
        embedding: Mapped[Any] = mapped_column(JSON, nullable=True)  # type: ignore

    # Aggregated preferences (for transparency/debugging)
    top_categories: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    avg_price_min: Mapped[Optional[float]] = mapped_column(Float)
    avg_price_max: Mapped[Optional[float]] = mapped_column(Float)
    interaction_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    __table_args__ = ({"schema": SCHEMA},)


# =============================================================================
# User Interactions (Recommendation-specific tracking)
# =============================================================================


class UserInteraction(Base):
    """User interaction tracking for recommendations.

    This supplements the e-commerce events table with recommendation-specific
    data like recommendation context, position, and attribution.
    """

    __tablename__ = "user_interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    external_product_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)

    interaction_type: Mapped[InteractionType] = mapped_column(
        Enum(InteractionType), nullable=False, index=True
    )

    # For search interactions
    search_query: Mapped[Optional[str]] = mapped_column(Text)

    # Recommendation attribution
    recommendation_context: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # homepage, product_page, cart, email
    recommendation_position: Mapped[Optional[int]] = mapped_column(Integer)
    recommendation_request_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Session tracking
    session_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Additional data
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (
        Index(
            "ix_user_interactions_user_type_created",
            "external_user_id",
            "interaction_type",
            "created_at",
        ),
        {"schema": SCHEMA},
    )


# =============================================================================
# Cart Abandonment
# =============================================================================


class CartAbandonment(Base):
    """Track abandoned carts for email reminders."""

    __tablename__ = "cart_abandonments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    external_cart_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Snapshot of cart at abandonment
    cart_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Reminder tracking
    abandonment_detected_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    reminder_count: Mapped[int] = mapped_column(Integer, default=0)

    # Recovery tracking
    recovered: Mapped[bool] = mapped_column(Boolean, default=False)
    recovered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    __table_args__ = (
        Index(
            "ix_cart_abandonments_pending",
            "external_user_id",
            "reminder_sent_at",
        ),
        {"schema": SCHEMA},
    )


# =============================================================================
# Email Campaigns
# =============================================================================


class EmailCampaign(Base):
    """Track email campaigns and their performance."""

    __tablename__ = "email_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    email_type: Mapped[EmailType] = mapped_column(Enum(EmailType), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)

    # Recommended products included
    recommended_product_ids: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    # Status tracking
    status: Mapped[EmailStatus] = mapped_column(
        Enum(EmailStatus), default=EmailStatus.PENDING, index=True
    )

    # Timestamps
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_email_campaigns_scheduled", "scheduled_at"),
        {"schema": SCHEMA},
    )


# =============================================================================
# User Email Preferences
# =============================================================================


class UserEmailPreference(Base):
    """User preferences for email notifications."""

    __tablename__ = "user_email_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_user_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    # Email type preferences
    cart_abandonment_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    new_products_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    weekly_digest_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    personalized_picks_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    back_in_stock_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Frequency cap
    frequency_cap_per_week: Mapped[int] = mapped_column(Integer, default=3)

    # Timestamps
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = ({"schema": SCHEMA},)


# =============================================================================
# Recommendation Performance
# =============================================================================


class RecommendationPerformance(Base):
    """Daily aggregated recommendation performance metrics."""

    __tablename__ = "recommendation_performance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    context: Mapped[str] = mapped_column(String(50), nullable=False)

    # Metrics
    total_impressions: Mapped[int] = mapped_column(Integer, default=0)
    total_clicks: Mapped[int] = mapped_column(Integer, default=0)
    total_conversions: Mapped[int] = mapped_column(Integer, default=0)
    avg_position_clicked: Mapped[Optional[float]] = mapped_column(Float)
    revenue_attributed_cents: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_rec_performance_date_context", "date", "context", unique=True),
        {"schema": SCHEMA},
    )


# =============================================================================
# Sync Status
# =============================================================================


class SyncStatus(Base):
    """Track data synchronization status."""

    __tablename__ = "sync_status"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # 'products', 'orders', etc.
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_sync_cursor: Mapped[Optional[str]] = mapped_column(String(255))
    records_synced: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="idle")  # idle, running, error
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = ({"schema": SCHEMA},)
