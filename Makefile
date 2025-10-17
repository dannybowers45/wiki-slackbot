.PHONY: dev test install clean docker-build docker-up

# Development
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Testing
test:
	pytest app/tests/ -v

# Install dependencies
install:
	pip install -r requirements.txt

# Clean up
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -f wikipedia_bot.db

# Docker
docker-build:
	docker-compose build

docker-up:
	docker-compose up

# Setup
setup: install
	cp env.example .env
	@echo "Please edit .env with your Slack app credentials"
