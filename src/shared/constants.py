"""Shared constants across the application."""

# Interaction weights for preference calculation
INTERACTION_WEIGHTS = {
    "purchase": 5.0,
    "cart_add": 3.0,
    "wishlist_add": 2.5,
    "recommendation_click": 1.5,
    "view": 1.0,
    "search": 0.5,
}

# Recommendation contexts
RECOMMENDATION_CONTEXTS = [
    "homepage",
    "product_page",
    "cart",
    "email",
    "frequently_bought_together",
]

# Email types
EMAIL_TYPES = [
    "cart_abandonment",
    "new_products",
    "weekly_digest",
    "personalized_picks",
    "back_in_stock",
]

# Default limits
DEFAULT_RECOMMENDATION_LIMIT = 12
MAX_RECOMMENDATION_LIMIT = 50
DEFAULT_ANALYTICS_LIMIT = 20
MAX_ANALYTICS_LIMIT = 100

# Batch sizes
PINECONE_BATCH_SIZE = 96  # Max for text records
INTERACTION_BATCH_SIZE = 100
SYNC_BATCH_SIZE = 100

# Time windows
ATTRIBUTION_WINDOW_DAYS = 7
USER_PREFERENCE_LOOKBACK_DAYS = 30
CART_ABANDONMENT_HOURS = 2
