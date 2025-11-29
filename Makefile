PYTHON_VERSION := 3.13
CODE = services
TESTS = services

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install dependencies
	pipenv install --no-interaction --no-ansi --no-root --all-extras

.PHONY: run-server
run-server: ## Run fastapi app with uvicorn
	python -m $(CODE)

.PHONY: format
format: ## Run linters in format mode
	isort $(CODE) $(TESTS)
	ruff format $(CODE) $(TESTS)
	ruff check --fix $(CODE) $(TESTS)

.PHONY: lint
lint: ## Run linters in check mode
	black --check $(CODE)
	ruff check $(CODE)
	mypy $(CODE)

.PHONY: start
start: ## Run docker containers
	docker compose up -d --build && docker compose logs -f

.PHONY: stop
stop: ## Stop docker containers
	docker compose down

.PHONY: test
test: ## Runs pytest with coverage
	docker build -t app-testing:latest -f Dockerfile.test . && docker run app-testing:latest
