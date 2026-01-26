.PHONY: help install run dev clean docker-build docker-run docker-stop

help:
	@echo "Available commands:"
	@echo "  make install       - Install dependencies"
	@echo "  make server        - Run the application"
	@echo "  make server-dev    - Run with auto-reload (development)"
	@echo "  make clean         - Remove cache files"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-run    - Run Docker container"
	@echo "  make docker-stop   - Stop Docker container"

install:
	pip install -r requirements.txt

server:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

server-dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

docker-build:
	docker build -t weather-forecaster .

docker-run:
	docker run -d -p 8000:8000 --name weather-forecaster --env-file .env weather-forecaster

docker-stop:
	docker stop weather-forecaster && docker rm weather-forecaster
