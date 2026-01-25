.PHONY: help install run dev test clean

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make run        - Run the application"
	@echo "  make dev        - Run with auto-reload (development)"
	@echo "  make clean      - Remove cache files"

install:
	pip install -r requirements.txt

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
