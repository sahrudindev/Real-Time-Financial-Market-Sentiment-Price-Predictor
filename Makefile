.PHONY: help up down restart logs ps clean init validate

# Default target
help:
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║   Real-Time Financial Market Sentiment Predictor - Commands   ║"
	@echo "╠════════════════════════════════════════════════════════════════╣"
	@echo "║  make init       - Initialize environment (.env from template) ║"
	@echo "║  make up         - Start all services                          ║"
	@echo "║  make down       - Stop all services                           ║"
	@echo "║  make restart    - Restart all services                        ║"
	@echo "║  make logs       - View logs (all services)                    ║"
	@echo "║  make ps         - Show running services                       ║"
	@echo "║  make clean      - Stop services and remove volumes            ║"
	@echo "║  make validate   - Validate docker-compose configuration       ║"
	@echo "║  make test-infra - Run infrastructure connectivity tests       ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"

# Initialize environment
init:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✅ Created .env from .env.example"; \
		echo "⚠️  Please review and update .env with your settings"; \
	else \
		echo "⚠️  .env already exists, skipping..."; \
	fi

# Validate docker-compose configuration
validate:
	@echo "🔍 Validating docker-compose configuration..."
	@docker compose config --quiet && echo "✅ Configuration is valid"

# Start all services
up: validate
	@echo "🚀 Starting all services..."
	docker compose up -d
	@echo ""
	@echo "✅ Services started! Access points:"
	@echo "   📊 Redpanda Console: http://localhost:8080"
	@echo "   📦 MinIO Console:    http://localhost:9001"
	@echo "   🔬 MLflow UI:        http://localhost:5000"
	@echo "   ✈️  Airflow UI:       http://localhost:8081"
	@echo "   📈 Grafana:          http://localhost:3000"
	@echo "   🔥 Prometheus:       http://localhost:9095"

# Stop all services
down:
	@echo "🛑 Stopping all services..."
	docker compose down

# Restart all services
restart: down up

# View logs
logs:
	docker compose logs -f

# Show specific service logs
logs-%:
	docker compose logs -f $*

# Show running services
ps:
	docker compose ps

# Clean up everything (including volumes)
clean:
	@echo "🧹 Cleaning up all services and volumes..."
	docker compose down -v --remove-orphans
	@echo "✅ Cleanup complete"

# Run infrastructure tests
test-infra:
	@echo "🧪 Testing infrastructure connectivity..."
	@echo ""
	@echo "Testing Redpanda..."
	@docker compose exec -T redpanda rpk cluster health || echo "❌ Redpanda not healthy"
	@echo ""
	@echo "Testing PostgreSQL..."
	@docker compose exec -T postgres pg_isready -U mlops_user || echo "❌ PostgreSQL not ready"
	@echo ""
	@echo "Testing MinIO..."
	@curl -s http://localhost:9000/minio/health/live && echo "✅ MinIO is live" || echo "❌ MinIO not responding"
	@echo ""
	@echo "Testing MLflow..."
	@curl -s http://localhost:5000/health && echo "" || echo "❌ MLflow not responding"
