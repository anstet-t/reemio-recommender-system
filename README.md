# Reemio Recommender System

A production-ready recommendation system for the Reemio e-commerce platform, providing personalized product recommendations via API and email, with comprehensive analytics and feedback loops.

## Features

- **Personalized Recommendations**: Homepage, product page, cart-based, and frequently-bought-together recommendations
- **Email Campaigns**: Cart abandonment, new products, weekly digest, and back-in-stock notifications
- **Analytics Dashboard**: Track most viewed, recommended, and purchased products
- **Feedback Loop**: Continuous improvement through user interaction tracking
- **Vector Search**: Semantic product similarity using Pinecone
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
              | PostgreSQL  |   |   Pinecone  |   |  Redis  |
              +-------------+   +-------------+   +---------+
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| API Framework | FastAPI (Python 3.11+) |
| Vector Database | Pinecone (llama-text-embed-v2) |
| Relational DB | PostgreSQL 15 |
| Cache/Queue | Redis 7 |
| Task Queue | Celery |
| Containerization | Docker |
| Orchestration | Kubernetes |

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+
- Pinecone account

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/reemio/reemio-recommender-system.git
   cd reemio-recommender-system
   ```

2. **Set up Python environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Start infrastructure services**
   ```bash
   docker-compose up -d postgres redis
   ```

5. **Set up Pinecone indexes**
   ```bash
   # Install Pinecone CLI
   brew tap pinecone-io/tap && brew install pinecone-io/tap/pinecone

   # Authenticate
   pc auth configure --api-key $PINECONE_API_KEY

   # Create indexes
   ./scripts/setup_pinecone.sh
   ```

6. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

7. **Start the API server**
   ```bash
   make run-api
   # Or: uvicorn recommendation_service.main:app --reload
   ```

8. **Start workers (in separate terminals)**
   ```bash
   make run-email-worker
   make run-sync-worker
   ```

### Using Docker Compose (Full Stack)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

## API Endpoints

### Recommendations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/recommendations/homepage` | GET | Personalized homepage recommendations |
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
| `/api/v1/analytics/recommendations/performance` | GET | CTR and conversion metrics |
| `/api/v1/analytics/conversion-funnel` | GET | View→Cart→Purchase funnel |

### Example Requests

```bash
# Get homepage recommendations
curl -X GET "http://localhost:8000/api/v1/recommendations/homepage?user_id=user123&limit=12"

# Track a product view
curl -X POST "http://localhost:8000/api/v1/interactions" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "product_id": "prod456",
    "interaction_type": "view"
  }'

# Get top viewed products
curl -X GET "http://localhost:8000/api/v1/analytics/products/top-viewed?limit=20"
```

## Email Workflows

| Trigger | Conditions | Email Type |
|---------|------------|------------|
| Cart Abandonment | No activity 2hrs after cart add | Reminder with cart items |
| New Products | Daily batch, matching user interests | New arrivals digest |
| Weekly Digest | Sunday 10AM, active users | Personalized picks |
| Back in Stock | Inventory update, user showed interest | Stock notification |

## Development

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test categories
pytest tests/unit -v
pytest tests/integration -v
pytest tests/e2e -v
```

### Code Quality

```bash
# Format code
make format

# Run linter
make lint

# Type checking
make typecheck

# Run all checks
make check
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Deployment

### Kubernetes

```bash
# Deploy to development
kubectl apply -k k8s/overlays/development

# Deploy to production
kubectl apply -k k8s/overlays/production

# Check deployment status
kubectl get pods -n reemio-recommender
```

### Environment Variables

See `.env.example` for all configuration options. Key variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `POSTGRES_HOST` | PostgreSQL host | Yes |
| `PINECONE_API_KEY` | Pinecone API key | Yes |
| `REDIS_HOST` | Redis host | Yes |
| `ECOMMERCE_API_BASE_URL` | E-commerce API URL | Yes |

## Project Structure

```
reemio-recommender-system/
├── src/
│   ├── recommendation_service/    # FastAPI application
│   │   ├── api/v1/               # API endpoints
│   │   ├── services/             # Business logic
│   │   ├── repositories/         # Data access
│   │   └── infrastructure/       # DB, Pinecone, Redis
│   ├── email_worker/             # Celery email tasks
│   └── sync_worker/              # Data sync tasks
├── tests/                        # Test suites
├── k8s/                          # Kubernetes manifests
├── docker/                       # Docker configuration
├── scripts/                      # Utility scripts
└── docs/                         # Documentation
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
