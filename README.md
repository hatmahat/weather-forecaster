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

4. **Open Swagger UI:**

   Visit http://localhost:8000/docs in your browser to explore and test all API endpoints interactively.

   Alternative: http://localhost:8000/redoc for ReDoc documentation.

## API Endpoints

### Core Endpoints
- `GET /` - Root endpoint (API info)
- `GET /health` - Health check

### Forecast Generation
- `POST /api/v1/forecast` - Trigger forecast generation workflow
  - **Request Body:**
    ```json
    {
      "run_id": "uuid-string",
      "trigger_user_id": 123
    }
    ```
  - **Response:**
    ```json
    {
      "run_id": "uuid-string",
      "status": "SUCCESS",
      "message": "Forecast generation completed successfully"
    }
    ```

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
