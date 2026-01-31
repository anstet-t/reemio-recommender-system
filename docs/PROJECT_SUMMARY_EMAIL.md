# Project Delivery: Reemio Recommendation System

**To:** Reemio Engineering Team
**From:** Development Team
**Date:** January 31, 2026
**Subject:** Recommendation System Implementation Complete - Summary & Handover

---

Dear Reemio Team,

We are pleased to deliver the completed **Reemio Recommendation System**. This document summarizes the work completed, architecture decisions, known limitations, and recommendations for production deployment.

---

## Executive Summary

We have built a **hybrid recommendation engine** that provides personalized product recommendations across multiple contexts (homepage, product pages, cart, and email campaigns). The system combines content-based filtering, collaborative filtering, and popularity signals to deliver relevant recommendations even for new users (cold-start handling).

---

## What Was Built

### 1. Recommendation API (FastAPI)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/recommendations/homepage` | Personalized homepage recommendations |
| `GET /api/v1/recommendations/product/{id}` | Similar products for product pages |
| `GET /api/v1/recommendations/cart` | "Complete your order" suggestions |
| `GET /api/v1/recommendations/frequently-bought-together/{id}` | Co-purchase recommendations |
| `POST /api/v1/interactions` | Track user behavior for learning |

### 2. 4-Stage Hybrid Pipeline

```
Candidate Generation → Hybrid Scoring → Reranking → Business Rules
      ↓                    ↓               ↓            ↓
   Content +          Weighted        Cross-encoder   Diversity +
   Collaborative +    blending        model for       Stock filter
   Popularity         of signals      precision
```

**Scoring Formula:**
```
final_score = 0.5 × content_similarity + 0.3 × collaborative_signal + 0.2 × popularity
```

### 3. User Interaction Tracking

The system tracks comprehensive engagement data:

| Interaction Type | Weight | Purpose |
|-----------------|--------|---------|
| PURCHASE | 5.0x | Strongest signal of preference |
| CART_ADD | 3.0x | High purchase intent |
| WISHLIST_ADD | 2.0x | Saved interest |
| RECOMMENDATION_CLICK | 1.5x | Validates recommendation quality |
| VIEW | 1.0x | Browsing interest |
| RECOMMENDATION_VIEW | 0.5x | Impression tracking |
| CART_REMOVE | -1.0x | Negative signal |

**Engagement Metrics Captured:**
- `timeOnPageSeconds` - Time spent on each page
- `sessionDurationSeconds` - Total session length
- `scrollDepthPercent` - Engagement depth indicator
- `recommendation_context` - Attribution for recommendation clicks
- `recommendation_position` - Position tracking for CTR analysis

### 4. Database Schema

Created dedicated `recommender` schema with:
- `user_interactions` - Behavioral data
- `product_embeddings` - 384-dimensional product vectors
- `user_preference_embeddings` - Aggregated user taste profiles
- `recommendation_performance` - Daily metrics aggregation
- `email_campaigns` - Email recommendation tracking
- `cart_abandonments` - Recovery workflow support

### 5. Demo Frontend

Interactive frontend showcasing:
- Personalized homepage recommendations
- "View Similar" product suggestions
- Cart-based recommendations
- User switching to demonstrate personalization
- Real Kenyan user names for realistic demo
- **API Docs link** in navbar for easy access to Swagger documentation

### 6. Single-Host Deployment

The API server serves both the frontend and API documentation from a single host:

| URL | Content |
|-----|---------|
| `/` | Frontend demo application |
| `/app` | Frontend (alternate path) |
| `/docs` | Swagger UI (interactive API docs) |
| `/redoc` | ReDoc (alternative API docs) |
| `/api/v1/*` | API endpoints |
| `/static/*` | Static frontend assets |

This eliminates CORS issues and simplifies deployment - no separate frontend server needed.

### 7. Seeded Test Data

| Data | Count | Details |
|------|-------|---------|
| Users | 21 | With Kenyan names (Wanjiku, Otieno, Akinyi, etc.) |
| Products | 1,900 | With embeddings |
| Public Events | 492 | PRODUCT_VIEWED, CART_ITEM_ADDED, PURCHASED |
| User Interactions | 698 | Across all interaction types |
| User Preferences | 10 | Built from interaction history |

**Demo User Personas:**

| Name | Persona | Top Categories | Interactions |
|------|---------|----------------|--------------|
| Wanjiku Muthoni | Power Shopper | Sports, Garden | 101 |
| Otieno Ochieng | Browser | Electronics, Office | 101 |
| Kipchoge Korir | Search Heavy | Home & Kitchen, Garden | 73 |
| Akinyi Adhiambo | Cart Abandoner | Electronics, Home | 36 |

---

## Technical Challenge: pgvector

### The Issue

We encountered a limitation where **pgvector extension is not installed** on the PostgreSQL instance. pgvector would have been ideal for:

- Native vector similarity search (`<=>` cosine distance operator)
- Index-accelerated nearest neighbor queries (IVFFlat, HNSW)
- Sub-millisecond similarity searches at scale

### Our Workaround

Without pgvector, we implemented an **optimized Python-based solution**:

1. **Embeddings stored as JSON** in PostgreSQL (instead of `vector` type)
2. **Candidate pre-filtering** - Fetch top 200 products by popularity first
3. **In-memory cosine similarity** - Compute similarity in Python
4. **Result caching** - Reduce redundant computations

**Performance Impact:**
- Current: ~1-2 seconds per recommendation request
- With pgvector: Would be ~50-100ms (10-20x faster)

### Recommendation

For production at scale, we strongly recommend:

```sql
-- Install pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Alter embedding column type
ALTER TABLE recommender.product_embeddings
ALTER COLUMN embedding TYPE vector(384)
USING embedding::text::vector(384);

-- Create HNSW index for fast similarity search
CREATE INDEX ON recommender.product_embeddings
USING hnsw (embedding vector_cosine_ops);
```

This requires PostgreSQL with pgvector extension (available on most cloud providers: AWS RDS, Supabase, Neon, Railway).

---

## Files Delivered

```
reemio-recommender-system/
├── src/recommendation_service/
│   ├── api/v1/                    # API endpoints
│   ├── services/
│   │   ├── recommendation_engine_v2.py  # Main engine
│   │   ├── embedding.py           # Embedding generation
│   │   ├── reranker.py            # Cross-encoder reranking
│   │   └── user_preference.py     # Preference aggregation
│   └── infrastructure/database/
│       └── migrations/            # Alembic migrations
├── frontend/                      # Demo UI
├── scripts/
│   ├── seed_dummy_data.py         # Data seeding
│   └── update_preferences.py      # Preference builder
├── README.md                      # Full documentation
└── SECURITY.md                    # Auth recommendations
```

---

## How to Run

```bash
# Install dependencies
uv sync

# Run migrations
uv run alembic upgrade head

# Start API (serves both frontend and API docs)
uv run uvicorn src.recommendation_service.main:app --reload --port 8000

# Open in browser
# Frontend: http://localhost:8000/
# API Docs: http://localhost:8000/docs

# Seed test data (optional)
uv run python scripts/seed_dummy_data.py
uv run python scripts/update_preferences.py
```

**Note:** No separate frontend server needed - the FastAPI app serves everything from a single host.

---

## Deployment on Render

The project includes a `render.yaml` for easy deployment:

1. Push code to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com/) → **New** → **Blueprint**
3. Connect your repository
4. Render prompts for database credentials (use your existing Reemio database)
5. Deploy

### Environment Variables

Render will prompt for these during deployment:

| Variable | Value |
|----------|-------|
| `POSTGRES_HOST` | Your existing database host |
| `POSTGRES_PORT` | Your existing database port |
| `POSTGRES_USER` | Your existing database user |
| `POSTGRES_PASSWORD` | Your existing database password |
| `POSTGRES_DB` | Your existing database name |

### After Deployment

The app serves everything from one URL:
- `/` → Frontend demo
- `/docs` → API documentation
- `/api/v1/*` → API endpoints

---

## Next Steps (Recommendations)

1. **Enable pgvector** - Install extension for 10-20x performance improvement
2. **Add authentication** - Current API uses user_id in URL (see SECURITY.md)
3. **Set up Redis** - Enable caching for high-traffic scenarios
4. **A/B testing** - Compare recommendation strategies
5. **Email integration** - Connect to your email service provider (replace MockEmailSender)

---

## Questions?

We're happy to walk through the codebase, discuss architectural decisions, or assist with deployment. Please reach out with any questions.

Best regards,
**Development Team**

---

*Repository: https://github.com/Rohianon/reemio-recommender-system*
