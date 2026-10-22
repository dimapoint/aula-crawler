.PHONY: install test lint

install:
	uv sync --extra dev && uv run playwright install chromium

test:
	uv run pytest -q

lint:
	uv run ruff check .
