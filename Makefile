.PHONY: help install test lint dev

help:  ## Show targets
	@echo "nursing-station make targets:"
	@echo "  install   install backend + frontend deps"
	@echo "  test      run backend + frontend tests"
	@echo "  lint      ruff + eslint"
	@echo "  dev       start dev servers (see README)"
