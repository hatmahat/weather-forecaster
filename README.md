# Weather Forecaster API

A scalable FastAPI-based weather forecasting inference system with clean architecture.

## Features

- **RESTful API** with FastAPI
- **Clean Architecture** (Repository Pattern + Service Layer)
- **MySQL 8.0** database support
- **API Versioning** (/api/v1)
- **Pydantic** validation
- **SQLAlchemy** ORM

## Project Structure

```
weather-forecaster/
├── app/
│   ├── main.py                        # FastAPI app entry point
│   ├── core/
│   │   ├── config.py                  # Settings, env vars
│   │   └── database.py                # DB connection
│   ├── api/v1/
│   │   ├── router.py                  # API router
│   │   └── endpoints/
│   │       └── forecast.py            # Forecast endpoint
│   ├── models/                        # SQLAlchemy models
│   │   ├── job.py
│   │   ├── weather_daily_record.py
│   │   ├── weather_monthly_results.py
│   │   └── forecast_monthly_record.py
│   ├── schemas/                       # Pydantic schemas
│   │   ├── forecast.py
│   │   ├── forecast_monthly.py
│   │   ├── job.py
│   │   ├── weather_daily.py
│   │   └── weather_monthly.py
│   ├── repositories/                  # Data access layer
│   │   ├── base.py
│   │   ├── job.py
│   │   ├── weather_daily_record.py
│   │   ├── weather_monthly_record.py
│   │   └── forecast_monthly_result.py
│   ├── services/                      # Business logic layer
│   │   └── forecast.py
│   └── machine_learning/              # ML layer
│       ├── preprocessing/
│       │   ├── aggregation.py
│       │   └── cleaning.py
│       └── forecasting/
│           ├── model_manager.py
│           └── predictions_mapper.py
├── experimental/                      # Experimental scripts
│   ├── analysis.py
│   ├── cleanse_data.py
│   ├── config.py
│   ├── connection.py
│   ├── function_forecast.py
│   ├── function_main.py
│   ├── handle_outlier.py
│   ├── logger_config.py
│   ├── models.py
│   └── stats_test.py
├── archive/                           # Archived files
│   └── api_server.py
├── models/                            # Pre-trained ML models (.pkl files)
├── logs/                              # Application logs
├── Makefile
├── requirements.txt
├── LICENSE
└── ARCHITECTURE.md
```

## Setup

1. **Create and activate virtual environment:**
   ```bash
   # Create virtual environment
   python3 -m venv venv

   # Activate virtual environment
   # On macOS/Linux:
   source venv/bin/activate

   # On Windows:
   venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   make install
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

4. **Run the application:**
   ```bash
   # Production mode
   make server

   # Development mode (with auto-reload)
   make server-dev
   ```

5. **Open Swagger UI:**

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
      "models": [
         "ARIMA",
         "TCN",
         "TFT",
         "XGBoost"
      ]
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
make server-dev
```

## Available Make Commands

- `make help` - Show available commands
- `make install` - Install dependencies
- `make server` - Run the application (production mode)
- `make server-dev` - Run with auto-reload (development mode)
- `make clean` - Remove Python cache files
