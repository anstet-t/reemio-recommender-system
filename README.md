# Reemio Recommender System

A production-ready recommendation system for the Reemio e-commerce platform, providing personalized product recommendations via API and email, with comprehensive analytics and feedback loops.

## Features

- **Personalized Recommendations**: Homepage, product page, cart-based, and frequently-bought-together recommendations
- **Email Campaigns**: Cart abandonment, new products, weekly digest, and back-in-stock notifications
- **Analytics Dashboard**: Track most viewed, recommended, and purchased products
- **Feedback Loop**: Continuous improvement through user interaction tracking
- **Vector Search**: Semantic product similarity using sentence embeddings
- **Production Ready**: Kubernetes deployment, comprehensive testing, monitoring

## Architecture

```
                              +------------------+
                              |   API Gateway    |
                              +--------+---------+
                                       |
         +-----------------------------+-----------------------------+
         |                             |                             |
         v                             v                             v
+--------+--------+          +---------+---------+          +--------+--------+
| E-Commerce API  |          | Recommendation    |          | Email Worker    |
| (External)      |          | Service (FastAPI) |          | (Celery)        |
+-----------------+          +-------------------+          +-----------------+
                                       |
                     +-----------------+----------------+
                     |                 |                |
                     v                 v                v
              +------+------+   +------+------+   +----+----+
              | PostgreSQL  |   |  pgvector   |   |  Redis  |
              +-------------+   +-------------+   +---------+
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| API Framework | FastAPI (Python 3.11+) |
| Vector Search | pgvector (PostgreSQL extension) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Reranking | cross-encoder (ms-marco-MiniLM-L-6-v2) |
| Relational DB | PostgreSQL 15 |
| Cache/Queue | Redis 7 |
| Task Queue | Celery |
| Package Manager | uv |

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- Redis 7+ (optional, for caching)
- uv (Python package manager)

### Installation

```bash
# Clone the repository
git clone https://github.com/reemio/reemio-recommender-system.git
cd reemio-recommender-system

# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate
uv sync
```

### Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit with your database credentials
# Required variables:
#   POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
```

### Database Setup

```bash
# Run database migrations
uv run alembic upgrade head

# Sync products from e-commerce API (generates embeddings)
uv run python -m scripts.sync_products
```

### Start the API Server

```bash
# Development mode with auto-reload
uv run uvicorn src.recommendation_service.main:app --reload --host 0.0.0.0 --port 8000

# Or use the Makefile
make run-api
```

### Start the Frontend

```bash
# Serve the frontend (in a separate terminal)
cd frontend
python3 -m http.server 8080

# Open in browser
open http://localhost:8080
```

## API Endpoints

### Recommendations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/recommendations/homepage` | GET | Popular/personalized homepage recommendations |
| `/api/v1/recommendations/product/{id}` | GET | Similar products |
| `/api/v1/recommendations/cart` | GET | Cart-based recommendations |
| `/api/v1/recommendations/frequently-bought-together/{id}` | GET | Co-purchase suggestions |

### Interactions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/interactions` | POST | Track single user interaction |
| `/api/v1/interactions/batch` | POST | Batch interaction tracking |

### Analytics

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/analytics/products/top-viewed` | GET | Most viewed products |
| `/api/v1/analytics/products/top-recommended` | GET | Most recommended products |
| `/api/v1/analytics/products/top-purchased` | GET | Best sellers |

### Example Requests

```bash
# Get homepage recommendations
curl "http://localhost:8000/api/v1/recommendations/homepage?limit=12"

# Get similar products
curl "http://localhost:8000/api/v1/recommendations/product/{product_id}?limit=8"

# Track a product view
curl -X POST "http://localhost:8000/api/v1/interactions" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "product_id": "prod456",
    "interaction_type": "view"
  }'
```

## Project Structure

```
reemio-recommender-system/
├── src/
│   ├── recommendation_service/    # FastAPI application
│   │   ├── api/v1/               # API endpoints
│   │   ├── services/             # Business logic (recommendation engine)
│   │   ├── infrastructure/       # DB, Redis connections
│   │   └── config.py             # Configuration management
│   ├── email_worker/             # Celery email tasks
│   └── sync_worker/              # Data sync tasks
├── frontend/                      # Demo frontend
├── tests/                         # Test suites
├── k8s/                           # Kubernetes manifests
├── docker/                        # Docker configuration
├── scripts/                       # Utility scripts
└── docs/                          # Documentation
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src

# Run specific test file
uv run pytest tests/unit/test_recommendation_engine.py -v
```

### Code Quality

```bash
# Format code
uv run ruff format src

# Lint code
uv run ruff check src

# Type checking
uv run mypy src
```

### Database Migrations

```bash
# Create new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback
uv run alembic downgrade -1
```

## How It Works

### Recommendation Pipeline

The recommendation engine uses a 4-stage hybrid pipeline:

1. **Candidate Generation**: Fast retrieval using:
   - Content-based: Semantic similarity via embeddings
   - Collaborative: User behavior patterns
   - Popularity: Fallback for cold-start

2. **Hybrid Scoring**: Blends multiple signals:
   ```
   score = 0.5 × content + 0.3 × collaborative + 0.2 × popularity
   ```

3. **Reranking**: Cross-encoder model for precise ordering

4. **Business Rules**: Diversity limits, stock filtering

### Embedding Model

Products are embedded using `sentence-transformers/all-MiniLM-L6-v2`:
- 384-dimensional vectors
- Cosine similarity for matching
- Stored in PostgreSQL with pgvector

### Personalization

When user interaction data exists:
- User preferences are computed from interaction history
- Collaborative filtering finds similar users
- Recommendations blend user preferences with content similarity

Without user data:
- Falls back to popularity-based recommendations
- Still provides relevant results based on product embeddings

## Data Model

### User Interactions

The recommendation engine tracks user interactions to build personalized preferences. Each interaction includes behavioral signals and engagement metrics.

#### Interaction Types

| Type | Weight | Description |
|------|--------|-------------|
| `PURCHASE` | 5.0 | User purchased the product |
| `CART_ADD` | 3.0 | Added to shopping cart |
| `WISHLIST_ADD` | 2.0 | Added to wishlist/saved |
| `RECOMMENDATION_CLICK` | 1.5 | Clicked on a recommendation |
| `VIEW` | 1.0 | Viewed product page |
| `RECOMMENDATION_VIEW` | 0.5 | Saw recommendation (impression) |
| `CART_REMOVE` | -1.0 | Removed from cart (negative signal) |
| `SEARCH` | - | Search query (used for intent analysis) |

#### Engagement Metrics

Each interaction captures time-based engagement data:

| Field | Type | Description |
|-------|------|-------------|
| `timeOnPageSeconds` | int | Time spent on the page (5-300s typical) |
| `sessionDurationSeconds` | int | Total session length (60-1800s) |
| `scrollDepthPercent` | int | How far user scrolled (10-100%) |
| `sessionId` | string | Groups interactions within a session |
| `device` | string | Device type: desktop, mobile, tablet |

#### Recommendation Attribution

For recommendation-driven interactions:

| Field | Description |
|-------|-------------|
| `recommendation_context` | Where shown: homepage, product_page, cart, email |
| `recommendation_position` | Position in the recommendation list (1-N) |
| `recommendation_request_id` | UUID linking impression → click → conversion |

#### Search Interactions

Search events include query and filter data:

```json
{
  "search_query": "wireless headphones",
  "extra_data": {
    "filters": {"category": "Electronics", "price_max": 5000},
    "resultsCount": 42,
    "timeOnPageSeconds": 25
  }
}
```

### Preference Computation

User preferences are aggregated from interactions using:

1. **Weighted Scoring**: Higher-value interactions (purchases) count more
2. **Recency Decay**: `weight × exp(-days / 30)` - recent interactions matter more
3. **Embedding Aggregation**: Product embeddings are averaged, weighted by interaction strength
4. **Category Analysis**: Top categories extracted for context-aware reranking

### Seeding Test Data

Generate realistic dummy data for testing:

```bash
# Seed user interactions and events
uv run python scripts/seed_dummy_data.py

# Build user preference embeddings from interactions
uv run python scripts/update_preferences.py
```

This creates:
- 80+ events in `public.events`
- 200+ interactions in `recommender.user_interactions`
- User personas with realistic behavior patterns
- Time-based engagement metrics

### Demo User Profiles

The seeded data includes users with distinct shopping personas:

| Name | Persona | Top Categories | Price Range | Interactions |
|------|---------|----------------|-------------|--------------|
| **Wanjiku Muthoni** | Power Shopper | Sports, Garden, Electronics | $1.50 - $591 | 101 |
| **Otieno Ochieng** | Browser | Electronics, Office, Garden | $1.40 - $1,186 | 101 |
| **Kipchoge Korir** | Search Heavy | Home & Kitchen, Garden, Toys | $1.90 - $1,017 | 73 |
| **Chebet Jepkosgei** | Reco Responder | Sports, Garden, Fashion | $3.60 - $512 | 68 |
| **Nyambura Wangari** | Search Heavy | Fashion, Office, Electronics | $1.80 - $1,017 | 67 |
| **Mutua Kioko** | Light User | Sports, Home & Kitchen, Electronics | $1.90 - $1,017 | 66 |
| **Kimani Njoroge** | Light User | Office, Sports, Electronics | $1.90 - $708 | 54 |
| **Omondi Onyango** | Reco Responder | Grocery, Fashion, Home & Kitchen | $1.40 - $571 | 54 |
| **Nafula Wekesa** | Light User | Sports, Home & Kitchen, Beauty | $4.10 - $1,017 | 40 |
| **Akinyi Adhiambo** | Cart Abandoner | Electronics, Home & Kitchen, Office | $3.60 - $756 | 36 |

**Persona Behaviors:**
- **Power Shopper**: High purchase rate, frequent views, responds to recommendations
- **Browser**: Many page views, few cart adds, extensive browsing sessions
- **Cart Abandoner**: Adds to cart frequently but rarely completes purchase
- **Search Heavy**: Uses search extensively with filters, discovery-focused
- **Reco Responder**: High click-through on recommendations, trusts the system
- **Light User**: Minimal interactions, cold-start scenario for testing

## Email Workflows

| Trigger | Conditions | Email Type |
|---------|------------|------------|
| Cart Abandonment | No activity 2hrs after cart add | Reminder with cart items |
| New Products | Daily batch, matching user interests | New arrivals digest |
| Weekly Digest | Sunday 10AM, active users | Personalized picks |
| Back in Stock | Inventory update, user showed interest | Stock notification |

## Deployment

### Deploy to Render (Recommended)

The project includes a `render.yaml` for easy deployment:

1. Push code to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com/) → **New** → **Blueprint**
3. Connect your repository
4. Enter your existing database credentials when prompted
5. Deploy - app serves frontend + API from one URL

### Using Docker Compose (Local)

```bash
# Start all services
cd docker
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

### Build Docker Image Manually

```bash
# Build the image
docker build -t reemio-recommender .

# Run with environment variables
docker run -p 8000:8000 \
  -e POSTGRES_HOST=your-db-host \
  -e POSTGRES_USER=your-user \
  -e POSTGRES_PASSWORD=your-password \
  -e POSTGRES_DB=your-db \
  reemio-recommender
```

### Kubernetes

```bash
# Deploy to development
kubectl apply -k k8s/overlays/development

# Deploy to production
kubectl apply -k k8s/overlays/production

# Check deployment status
kubectl get pods -n reemio-recommender
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_HOST` | PostgreSQL host | localhost |
| `POSTGRES_PORT` | PostgreSQL port | 5432 |
| `POSTGRES_USER` | Database user | - |
| `POSTGRES_PASSWORD` | Database password | - |
| `POSTGRES_DB` | Database name | - |
| `REDIS_HOST` | Redis host | localhost |
| `REDIS_PORT` | Redis port | 6379 |
| `APP_ENV` | Environment (development/production) | development |
| `DEBUG` | Enable debug mode | false |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
