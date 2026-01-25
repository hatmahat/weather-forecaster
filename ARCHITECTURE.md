# Architecture Documentation

## Overview

This project follows a **layered architecture** pattern with clear separation of concerns, inspired by clean architecture principles and best practices from the FastAPI community.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                          │
│                    (HTTP Requests/Responses)                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      API Layer (Endpoints)                   │
│  - Route handling                                            │
│  - Request validation (Pydantic)                             │
│  - Response formatting                                       │
│  - HTTP status codes                                         │
│  Files: app/api/v1/endpoints/*.py                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                     Service Layer                            │
│  - Business logic                                            │
│  - Data orchestration                                        │
│  - Transaction management                                    │
│  - Domain rules enforcement                                  │
│  Files: app/services/*.py                                    │
└─────────┬────────────────┴────────────────┬─────────────────┘
          │                                 │
          │                  ┌──────────────▼──────────────┐
          │                  │   Machine Learning Layer    │
          │                  │  - Data preprocessing       │
          │                  │  - Feature engineering      │
          │                  │  - Model inference          │
          │                  │  Files: app/machine_learning│
          │                  └─────────────────────────────┘
          │
┌─────────▼─────────────────────────────────────────────────┐
│                   Repository Layer                         │
│  - Data access abstraction                                 │
│  - Query building                                          │
│  - CRUD operations                                         │
│  - Database-specific logic                                 │
│  Files: app/repositories/*.py                              │
└──────────────────────────┬────────────────────────────────┘
                           │
┌──────────────────────────▼────────────────────────────────┐
│                    Database Layer                          │
│  - SQLAlchemy ORM                                          │
│  - MySQL 8.0                                               │
│  Files: app/models/*.py                                    │
└───────────────────────────────────────────────────────────┘
```

## Layer Responsibilities

### 1. API Layer (`app/api/v1/endpoints/`)

**Purpose**: Handle HTTP communication

**Responsibilities**:
- Define route endpoints
- Parse and validate incoming requests
- Delegate business logic to services
- Format responses
- Handle HTTP errors and status codes
- Dependency injection setup

**Example**:
```python
@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(job_data: JobCreate, db: Session = Depends(get_db)):
    """Create a new job"""
    return job_service.create_job(db, job_data)
```

**Key Principles**:
- ✅ Keep endpoints thin - only handle HTTP concerns
- ✅ Use dependency injection for DB sessions
- ✅ Validate input with Pydantic schemas
- ❌ No business logic in endpoints
- ❌ No direct database queries

---

### 2. Service Layer (`app/services/`)

**Purpose**: Implement business logic and orchestration

**Responsibilities**:
- Execute business rules
- Coordinate between multiple repositories
- Handle complex operations
- Transform data between layers
- Manage transactions
- Error handling and validation

**Example**:
```python
class JobService:
    def __init__(self):
        self.repository = job_repository

    def create_job(self, db: Session, job_data: JobCreate) -> JobResponse:
        job_dict = job_data.model_dump()
        job_dict["run_id"] = str(uuid4())  # Business logic
        job_dict["status"] = JobStatus.PENDING

        job = self.repository.create(db, obj_in=job_dict)
        return JobResponse.model_validate(job)
```

**Key Principles**:
- ✅ Contain all business logic
- ✅ Use repositories for data access
- ✅ Return Pydantic schemas
- ✅ Can call multiple repositories
- ❌ No HTTP-specific code
- ❌ No direct SQLAlchemy queries

---

### 3. Repository Layer (`app/repositories/`)

**Purpose**: Abstract data access and persistence

**Responsibilities**:
- CRUD operations
- Query building
- Database filtering and pagination
- Data persistence
- Relationship handling

**Example**:
```python
class JobRepository(BaseRepository[Job]):
    def get_by_run_id(self, db: Session, run_id: str) -> Optional[Job]:
        return db.query(Job).filter(Job.run_id == run_id).first()

    def get_by_status(self, db: Session, status: JobStatus,
                      skip: int = 0, limit: int = 100) -> List[Job]:
        return (
            db.query(Job)
            .filter(Job.status == status)
            .offset(skip)
            .limit(limit)
            .all()
        )
```

**Key Principles**:
- ✅ Extend BaseRepository for common operations
- ✅ Add custom query methods as needed
- ✅ Return SQLAlchemy models
- ✅ Keep queries optimized
- ❌ No business logic
- ❌ No HTTP/response formatting

---

### 4. Model Layer (`app/models/`)

**Purpose**: Define database schema and relationships

**Responsibilities**:
- Define table structure
- Define relationships
- Set constraints and indexes
- Provide ORM mapping

**Example**:
```python
class Job(Base):
    __tablename__ = "jobs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(String(36), unique=True, nullable=False, index=True)
    status = Column(Enum(JobStatus), nullable=False, index=True)
    # ... other columns
```

**Key Principles**:
- ✅ Map to database tables exactly
- ✅ Define proper indexes
- ✅ Use appropriate data types
- ❌ No business logic
- ❌ No validation logic

---

### 5. Schema Layer (`app/schemas/`)

**Purpose**: Define API contracts and validation

**Responsibilities**:
- Request validation
- Response formatting
- Data type enforcement
- Documentation

**Example**:
```python
class JobCreate(BaseModel):
    trigger_type: str
    job_type: str
    trigger_user_id: Optional[int] = None
    job_metadata: Optional[dict] = None

class JobResponse(BaseModel):
    id: int
    run_id: str
    status: JobStatus
    created_at: datetime

    class Config:
        from_attributes = True
```

**Key Principles**:
- ✅ Use Pydantic models
- ✅ Separate Create/Update/Response schemas
- ✅ Add validation rules
- ✅ Enable ORM mode for responses

---

### 6. Machine Learning Layer (`app/machine_learning/`)

**Purpose**: Handle data preprocessing and ML model predictions

**Responsibilities**:
- Data aggregation and transformation
- Feature engineering
- Model loading and inference
- Prediction logic

**Example**:
```python
# app/machine_learning/preprocessing.py
def aggregate_daily_to_monthly(daily_records):
    """Aggregate daily weather data to monthly statistics"""
    # Aggregation logic
    return monthly_data

def prepare_features(monthly_data):
    """Prepare features for model input"""
    return feature_matrix

# app/machine_learning/prediction.py
import pickle

def load_model(model_path):
    """Load trained forecast model"""
    with open(model_path, 'rb') as f:
        return pickle.load(f)

def predict_forecast(features, model):
    """Generate weather forecast predictions"""
    return model.predict(features)
```

**Usage in Service Layer**:
```python
from app.machine_learning.preprocessing import aggregate_daily_to_monthly
from app.machine_learning.prediction import load_model, predict_forecast

class ForecastService:
    def generate_forecast(self, db, request):
        # Fetch data from repository
        daily_data = self.weather_daily_repository.get_by_filters(...)

        # Preprocess using ML layer
        monthly_data = aggregate_daily_to_monthly(daily_data)

        # Predict using ML layer
        model = load_model('app/machine_learning/models/forecast.pkl')
        predictions = predict_forecast(monthly_data, model)

        # Store results via repository
        self.forecast_repository.create(...)
```

**Key Principles**:
- ✅ Pure functions (no database access)
- ✅ Reusable ML logic
- ✅ Separate from business logic (services orchestrate)
- ✅ Store trained models in `models/` directory
- ❌ No direct API access
- ❌ No database queries

---

## Data Flow

### Request Flow (Create Operation)

```
1. Client sends POST request
   ↓
2. FastAPI endpoint receives request
   ↓
3. Pydantic validates request body (JobCreate schema)
   ↓
4. Endpoint calls service.create_job()
   ↓
5. Service adds business logic (generate run_id, set status)
   ↓
6. Service calls repository.create()
   ↓
7. Repository creates SQLAlchemy model instance
   ↓
8. Repository commits to database
   ↓
9. Repository returns SQLAlchemy model
   ↓
10. Service converts to Pydantic schema (JobResponse)
   ↓
11. Endpoint returns JobResponse
   ↓
12. FastAPI serializes to JSON
   ↓
13. Client receives response
```

### Query Flow (Read Operation)

```
1. Client sends GET request with filters
   ↓
2. FastAPI endpoint receives request
   ↓
3. Pydantic validates query parameters
   ↓
4. Endpoint calls service.get_records(filters)
   ↓
5. Service calls repository.get_by_filters()
   ↓
6. Repository builds SQLAlchemy query
   ↓
7. Repository executes query on database
   ↓
8. Repository returns list of SQLAlchemy models
   ↓
9. Service converts to list of Pydantic schemas
   ↓
10. Endpoint returns list of schemas
   ↓
11. FastAPI serializes to JSON
   ↓
12. Client receives response
```

---

## Design Patterns

### 1. Repository Pattern

**Purpose**: Separate data access logic from business logic

**Benefits**:
- Easy to test (mock repositories)
- Swappable data sources
- Centralized query logic
- Reduced code duplication

**Implementation**:
- `BaseRepository<T>` - Generic CRUD operations
- Specific repositories extend BaseRepository
- Custom query methods in specific repositories

### 2. Service Layer Pattern

**Purpose**: Encapsulate business logic

**Benefits**:
- Reusable business logic
- Testable without HTTP layer
- Can orchestrate multiple repositories
- Clear separation of concerns

**Implementation**:
- One service per domain entity
- Services use repositories via dependency injection
- Services return Pydantic schemas

### 3. Dependency Injection

**Purpose**: Manage dependencies and improve testability

**Benefits**:
- Loose coupling
- Easy to mock in tests
- Clear dependencies

**Implementation**:
```python
# Database session injection
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Usage in endpoints
@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    return job_service.get_job(db, job_id)
```

---

## Project Structure Details

```
weather-backend-v2/
├── app/
│   ├── __init__.py
│   ├── main.py                            # FastAPI app initialization
│   │
│   ├── core/                              # Core functionality
│   │   ├── __init__.py
│   │   ├── config.py                      # Settings management (Pydantic)
│   │   └── database.py                    # Database connection & session
│   │
│   ├── api/                               # API layer
│   │   ├── __init__.py
│   │   └── v1/                            # API version 1
│   │       ├── __init__.py
│   │       ├── router.py                  # Aggregate all v1 routes
│   │       └── endpoints/                 # Individual route modules
│   │           ├── __init__.py
│   │           └── forecast.py            # Forecast generation endpoint
│   │
│   ├── models/                            # SQLAlchemy models (Database layer)
│   │   ├── __init__.py
│   │   ├── job.py
│   │   ├── weather_daily_record.py
│   │   ├── weather_monthly_resutls.py
│   │   └── forecast_monthly_record.py
│   │
│   ├── schemas/                           # Pydantic schemas (Validation layer)
│   │   ├── __init__.py
│   │   ├── forecast.py                    # Forecast request/response schemas
│   │   ├── forecast_monthly.py
│   │   ├── job.py
│   │   ├── weather_daily.py
│   │   └── weather_monthly.py
│   │
│   ├── repositories/                      # Data access layer
│   │   ├── __init__.py
│   │   ├── base.py                        # BaseRepository with CRUD
│   │   ├── job.py
│   │   ├── weather_daily_record.py
│   │   ├── weather_monthly_record.py
│   │   └── forecast_monthly_result.py
│   │
│   ├── machine_learning/                  # Machine learning layer
│   │   ├── __init__.py
│   │   ├── preprocessing.py               # Data preprocessing functions
│   │   └── prediction.py                  # Model prediction functions
│   │
│   └── services/                          # Business logic layer
│       ├── __init__.py
│       └── forecast.py                    # Forecast generation service
│
├── tests/                                 # Test directory
├── alembic/                               # Database migrations
├── Makefile                               # Make commands (run, dev, etc.)
├── requirements.txt                       # Python dependencies
├── .env                                   # Environment variables (not in git)
├── .env.example                           # Environment template
├── .gitignore                             # Git ignore rules
├── README.md                              # Project documentation
└── ARCHITECTURE.md                        # This file
```

---

## Configuration Management

### Environment Variables (`.env`)

```bash
# Application
APP_NAME=Weather Backend API
APP_VERSION=1.0.0
DEBUG=False

# Database
DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/weather_db

# CORS
CORS_ORIGINS=http://localhost:3000
```

### Settings (`app/core/config.py`)

Uses `pydantic-settings` for type-safe configuration:

```python
class Settings(BaseSettings):
    APP_NAME: str = "Weather Backend API"
    DATABASE_URL: str
    CORS_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = ".env"
```

---

## Database Design

### Schema Relationships

```
jobs (1) ──────┬─────> (N) weather_monthly_records
               │              (via run_id)
               │
               └─────> (N) forecast_monthly_results
                              (via run_id)

weather_daily_records (independent table)
```

### Key Design Decisions

1. **`run_id` as UUID** - Globally unique job identifier
2. **Foreign Keys** - Maintain referential integrity
3. **Indexes** - Optimize common query patterns
4. **Enums** - Type-safe status values
5. **Timestamps** - Auto-managed created_at/updated_at

---

## API Design

### Versioning Strategy

- Base path: `/api/v1`
- Future versions: `/api/v2`, `/api/v3`
- Allows breaking changes without affecting existing clients

### Endpoint Patterns

```
Resource-based URLs:
GET    /api/v1/jobs              - List jobs
POST   /api/v1/jobs              - Create job
GET    /api/v1/jobs/{id}         - Get specific job
PATCH  /api/v1/jobs/{id}         - Update job
DELETE /api/v1/jobs/{id}         - Delete job (if needed)

Bulk operations:
POST   /api/v1/weather-daily/bulk - Bulk create

Custom queries:
GET    /api/v1/jobs/run/{run_id}  - Get by alternate key
```

### Response Standards

```json
// Success response
{
  "id": 1,
  "run_id": "uuid-here",
  "status": "SUCCESS",
  "created_at": "2025-01-23T10:00:00"
}

// Error response (FastAPI default)
{
  "detail": "Job not found"
}
```

---

## Testing Strategy

### Unit Tests

```python
# Test service layer
def test_create_job():
    mock_repo = Mock()
    service = JobService(repository=mock_repo)
    result = service.create_job(db, job_data)
    assert result.status == JobStatus.PENDING

# Test repository layer
def test_get_by_run_id():
    job = job_repository.get_by_run_id(db, "uuid")
    assert job.run_id == "uuid"
```

### Integration Tests

```python
# Test full API flow
def test_create_job_endpoint():
    response = client.post("/api/v1/jobs", json={...})
    assert response.status_code == 201
```

---

## Scalability Considerations

### Current Design Supports

1. **Horizontal Scaling** - Stateless API servers
2. **Database Connection Pooling** - Configured in `database.py`
3. **Async Support** - Can add async/await in future
4. **Caching Layer** - Easy to add Redis for services
5. **Load Balancing** - Multiple uvicorn instances

### Future Enhancements

- **Async/Await** - For better concurrency
- **Background Tasks** - Celery for long-running jobs
- **API Rate Limiting** - Protect against abuse
- **Monitoring** - Prometheus metrics
- **Logging** - Structured logging with correlation IDs
- **Authentication** - JWT tokens
- **Authorization** - Role-based access control

---

## Best Practices Applied

### Code Organization

✅ Separation of concerns
✅ Single responsibility principle
✅ Dependency injection
✅ Type hints throughout
✅ Consistent naming conventions

### Database

✅ Connection pooling
✅ Proper indexing
✅ Foreign key constraints
✅ Optimistic locking with updated_at

### API

✅ RESTful design
✅ Proper HTTP status codes
✅ Request/response validation
✅ API versioning
✅ Auto-generated documentation (Swagger)

### Error Handling

✅ HTTP exceptions in endpoints
✅ Database constraint errors
✅ Validation errors (Pydantic)
✅ Clear error messages

---

## References

This architecture is based on industry best practices:

1. [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)
2. [Repository Pattern in Python](https://medium.com/@kmuhsinn/the-repository-pattern-in-python-write-flexible-testable-code-with-fastapi-examples-aa0105e40776)
3. [Service Layer Pattern](https://mpuig.github.io/Notes/fastapi_basics/04.service_layer_pattern/)
4. [Clean Architecture Principles](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

---

## Maintenance & Development

### Adding a New Entity

1. Create model in `app/models/`
2. Create schemas in `app/schemas/`
3. Create repository in `app/repositories/`
4. Create service in `app/services/`
5. Create endpoints in `app/api/v1/endpoints/`
6. Register router in `app/api/v1/router.py`

### Modifying Existing Entity

1. Update model if schema changes
2. Update schemas for new fields
3. Update repository for new queries
4. Update service for new business logic
5. Update/add endpoints as needed

---

## Conclusion

This architecture provides:

- **Maintainability** - Clear structure, easy to navigate
- **Testability** - Each layer can be tested independently
- **Scalability** - Can handle growth in traffic and features
- **Flexibility** - Easy to swap implementations
- **Developer Experience** - Clear patterns, good documentation
