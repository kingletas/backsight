# backsight — a Terraform workbench that shows what a change will do while you write it
#
# Run `make` with no arguments for the list. `make check` is what a commit has
# to pass, and it is the same thing CI runs.

SHELL       := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

PREFIX ?= $(HOME)/bin

.PHONY: help
help: ## Show this help
	@echo
	@echo "  backsight — a Terraform workbench"
	@echo
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "    \033[36m%-12s\033[0m %s\n", $$1, $$2}'
	@echo

# --- run --------------------------------------------------------------------

.PHONY: venv
venv: ## Build the virtualenv with the system GTK bindings visible
	@test -d .venv || uv venv --python /usr/bin/python3 --system-site-packages
	@uv sync --quiet

WORKSPACE ?= fixtures/workspace

.PHONY: app
app: venv ## Open the window on WORKSPACE= (the example by default)
	@uv run python -m backsight "$(WORKSPACE)"

# --- checks -----------------------------------------------------------------

.PHONY: lint
lint: venv ## Static checks
	@uv run ruff check src tests spikes
	@uv run ruff format --check src tests spikes

.PHONY: format
format: venv ## Apply the formatter
	@uv run ruff format src tests spikes
	@uv run ruff check --fix src tests spikes

.PHONY: test
test: venv ## The unit and architecture suites
	@uv run pytest -q -m "not sandbox and not integration"

.PHONY: acceptance
acceptance: venv ## Drive the real window end to end, and the defects that must not come back
	@uv run pytest -q tests/acceptance tests/regression

.PHONY: test-sandbox
test-sandbox: venv ## The tests that drive a real emulator container
	@uv run pytest -q -m sandbox

.PHONY: integration
integration: venv ## Start the emulator, run every engine command against it, tear it down
	@infra-test/scripts/test

.PHONY: check
check: lint test acceptance ## Everything a commit has to pass
	@echo
	@echo "  lint, tests and acceptance pass"

.PHONY: smoke
smoke: venv ## Drive the real window and save a PNG of each view
	@uv run python scripts/gui-smoke.py

.PHONY: smoke-watch
smoke-watch: venv ## The same, on this screen, to watch it happen
	@BACKSIGHT_DISPLAY=$${DISPLAY} uv run python scripts/gui-smoke.py

.PHONY: ci
ci: ## The gate, plus the window drive CI cannot do reliably, before you push
	@echo "=== job: lint and tests ==="
	@$(MAKE) --no-print-directory check
	@echo
	@echo "=== job: drive the window ==="
	@command -v xvfb-run >/dev/null || { \
		echo "  xvfb-run is missing. CI has it and this machine does not:"; \
		echo "    sudo apt install xvfb"; exit 1; }
	@xvfb-run -a $(MAKE) --no-print-directory smoke
	@echo
	@echo "=== job: the emulator ==="
	@$(MAKE) --no-print-directory test-sandbox
