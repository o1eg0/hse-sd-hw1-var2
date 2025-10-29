PYTHON_VERSION := 3.13
CODE = services
TESTS = .

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

.PHONY: test
test: ## Runs pytest with coverage
	pytest $(TESTS) -n 3 --cov=$(CODE)
