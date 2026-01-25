# Weather Backend API v2

A scalable FastAPI-based weather data management system with clean architecture.

## Features

- **RESTful API** with FastAPI
- **Clean Architecture** (Repository Pattern + Service Layer)
- **MySQL 8.0** database support
- **API Versioning** (/api/v1)
- **Pydantic** validation
- **SQLAlchemy** ORM

## Project Structure

```
weather-backend-v2/
├── app/
│   ├── main.py                 # FastAPI app entry point
│   ├── core/
│   │   ├── config.py          # Settings, env vars
│   │   └── database.py        # DB connection
│   ├── api/v1/
│   │   ├── router.py          # API router
│   │   └── endpoints/         # API endpoints
│   ├── models/                # SQLAlchemy models
│   ├── schemas/               # Pydantic schemas
│   ├── repositories/          # Data access layer
│   └── services/              # Business logic layer
├── requirements.txt
└── .env
```

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

3. **Run the application:**
   ```bash
   uvicorn app.main:app --reload
   ```

4. **Access API documentation:**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## API Endpoints

### Jobs
- `POST /api/v1/jobs` - Create job
- `GET /api/v1/jobs/{job_id}` - Get job by ID
- `GET /api/v1/jobs/run/{run_id}` - Get job by run_id
- `GET /api/v1/jobs` - List jobs (with status filter)
- `PATCH /api/v1/jobs/{job_id}` - Update job

### Weather Daily Records
- `POST /api/v1/weather-daily` - Create record
- `POST /api/v1/weather-daily/bulk` - Bulk create
- `GET /api/v1/weather-daily/{record_id}` - Get record
- `GET /api/v1/weather-daily` - List records (with filters)

### Weather Monthly Records
- `POST /api/v1/weather-monthly` - Create record
- `POST /api/v1/weather-monthly/bulk` - Bulk create
- `GET /api/v1/weather-monthly/{record_id}` - Get record
- `GET /api/v1/weather-monthly` - List records (with filters)

### Forecast Monthly Results
- `POST /api/v1/forecast-monthly` - Create result
- `POST /api/v1/forecast-monthly/bulk` - Bulk create
- `GET /api/v1/forecast-monthly/{result_id}` - Get result
- `GET /api/v1/forecast-monthly` - List results (with filters)

## Database Schema

The application uses the following tables:
- `jobs` - Job tracking and management
- `weather_daily_records` - Daily weather observations
- `weather_monthly_records` - Monthly weather aggregations
- `forecast_monthly_results` - Monthly forecast predictions

## Architecture

The project follows clean architecture principles:

1. **API Layer** (endpoints) - HTTP request/response handling
2. **Service Layer** - Business logic and orchestration
3. **Repository Layer** - Data access and persistence
4. **Model Layer** - Database entities (SQLAlchemy)
5. **Schema Layer** - Request/response validation (Pydantic)

## Development

Run with auto-reload:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
