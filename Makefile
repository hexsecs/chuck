PYTHON ?= python3 -I
# Where `make deploy` links the OpenCode profiles (default: XDG config dir).
OPENCODE_AGENTS ?=

.PHONY: help sync check test deploy

help: ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

sync: ## Copy model defaults from models.toml into the agent profiles
	$(PYTHON) scripts/sync-models.py

check: ## Fail if the agent profiles are out of date with models.toml
	$(PYTHON) scripts/sync-models.py --check

test: ## Run all tests
	$(PYTHON) tests/test_sync_models.py
	$(PYTHON) tests/test_deploy.py

deploy: ## Link the OpenCode profiles (override dir with OPENCODE_AGENTS=...)
	sh deploy-opencode.sh $(OPENCODE_AGENTS)
