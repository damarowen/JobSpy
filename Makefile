.PHONY: help setup install test test-jobstreet lint format clean

PYTHON := python3
VENV := venv
VENV_BIN := $(VENV)/bin
PIP := $(VENV_BIN)/pip
PYTHON_VENV := $(VENV_BIN)/python

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Create virtual env and install dependencies
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e .
	@echo "✅ Setup complete. Run 'source venv/bin/activate' to activate."

install: ## Install/update dependencies in existing venv
	$(PIP) install -e .

test: ## Run basic import test
	$(PYTHON_VENV) -c "from jobspy import scrape_jobs; print('✅ JobSpy imported successfully')"

test-jobstreet: ## Quick test JobStreet scraper (10 results)
	$(PYTHON_VENV) -c "\
from jobspy import scrape_jobs; \
jobs = scrape_jobs(site_name='jobstreet', search_term='software engineer', location='Jakarta', results_wanted=10, verbose=2); \
print(f'Found {len(jobs)} jobs'); \
print(jobs[['title','company_name','location']].head())"

shell: ## Open Python shell with JobSpy loaded
	$(PYTHON_VENV) -c "from jobspy import scrape_jobs; import pandas as pd; print('JobSpy loaded. Use scrape_jobs(...)'); import code; code.interact(local=locals())"

lint: ## Run ruff linter (install ruff first: pip install ruff)
	$(PYTHON_VENV) -m ruff check jobspy/

format: ## Run ruff formatter (install ruff first: pip install ruff)
	$(PYTHON_VENV) -m ruff format jobspy/

clean: ## Remove build artifacts and venv
	rm -rf $(VENV) build/ dist/ *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete

venv-activate: ## Print activate command
	@echo "Run: source $(VENV)/bin/activate"
