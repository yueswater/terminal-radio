# Common tasks for the radio project. Run make help to list them.

.DEFAULT_GOAL := help
.PHONY: help install link unlink run api docs clean

help: ## Show every available target
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Sync the virtual environment from pyproject.toml
	uv sync

link: ## Install the radio command on PATH, editable so edits apply at once
	uv tool install --editable . --force

unlink: ## Remove the radio command from PATH
	uv tool uninstall radio

run: ## Start the terminal UI
	uv run radio ui

api: ## Start the HTTP API with autoreload
	uv run radio api --host $(HOST) --port $(PORT) --reload

docs: ## Open the interactive API documentation
	open http://$(HOST):$(PORT)/docs

clean: ## Remove bytecode caches and build artifacts
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .ruff_cache dist build

# Host and port of the API. Override on the command line, for example make api PORT=9000.
HOST ?= 127.0.0.1
PORT ?= 8000
