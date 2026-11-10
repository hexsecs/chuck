PYTHON ?= python3 -I
# Optional target directory for `make deploy-claude` / `make deploy-opencode`.
AGENTS_DIR ?=

.PHONY: help sync check test scan deploy-claude deploy-opencode

help: ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

sync: ## Copy model defaults from models.toml into the agent profiles
	$(PYTHON) scripts/sync-models.py

check: ## Fail if the agent profiles are out of date with models.toml
	$(PYTHON) scripts/sync-models.py --check

test: ## Run all tests
	$(PYTHON) tests/test_sync_models.py
	$(PYTHON) tests/test_scan_models.py
	$(PYTHON) tests/test_deploy.py

scan: ## List free ($0) models from the OpenCode catalog (ids only; use Code Mode for cost data)
	$(PYTHON) scripts/scan-models.py --names --providers opencode

deploy-claude: ## Link agents/claude into ~/.claude/agents (or AGENTS_DIR=...)
	sh deploy.sh claude $(AGENTS_DIR)

deploy-opencode: ## Link agents/opencode into the OpenCode config (or AGENTS_DIR=...)
	sh deploy.sh opencode $(AGENTS_DIR)
