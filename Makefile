# Makefile for Bunsui development and release management

.PHONY: help install install-dev test lint format type-check build clean dist check-dist upload upload-test docs

# Default target
help:
	@echo "Available targets:"
	@echo "  install      - Install package in development mode"
	@echo "  install-dev  - Install package with development dependencies"
	@echo "  test         - Run tests with pytest"
	@echo "  lint         - Run linting with flake8"
	@echo "  format       - Format code with black"
	@echo "  type-check   - Run type checking with mypy"
	@echo "  check-code   - Run comprehensive code checks (format + lint + type-check + test)"
	@echo "  check-quick  - Run quick code checks (format + lint + type-check)"
	@echo "  build        - Build distribution packages"
	@echo "  clean        - Clean build artifacts"
	@echo "  dist         - Create distribution packages"
	@echo "  check-dist   - Check distribution packages"
	@echo "  upload-test  - Upload to Test PyPI"
	@echo "  upload       - Upload to PyPI"
	@echo "  docs         - Generate documentation"
	@echo "  bump-version - Bump version (requires VERSION=x.y.z)"

# Development setup
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pre-commit install

# Testing and quality
test:
	pytest

test-cov:
	pytest --cov=src/bunsui --cov-report=html --cov-report=term-missing

lint:
	flake8 src/bunsui tests

format:
	black src/bunsui tests
	isort src/bunsui tests

format-check:
	black --check src/bunsui tests
	isort --check-only src/bunsui tests

type-check:
	mypy src/bunsui

# Build and distribution
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build

dist: build

check-dist:
	python -m twine check dist/*

# PyPI upload
upload-test: check-dist
	python -m twine upload --repository testpypi dist/*

upload: check-dist
	python -m twine upload dist/*

# Documentation
docs:
	@echo "Documentation generation will be implemented"

# Version management
bump-version:
	@if [ -z "$(VERSION)" ]; then \
		echo "ERROR: VERSION is required. Usage: make bump-version VERSION=x.y.z"; \
		exit 1; \
	fi
	sed -i 's/version = ".*"/version = "$(VERSION)"/' pyproject.toml
	sed -i 's/## \[Unreleased\]/## [Unreleased]\n\n## [$(VERSION)] - $(shell date +%Y-%m-%d)/' CHANGELOG.md
	git add pyproject.toml CHANGELOG.md
	git commit -m "Bump version to $(VERSION)"
	git tag -a v$(VERSION) -m "Release v$(VERSION)"

# All quality checks
check-all: format-check lint type-check test

# Comprehensive code checks using the script
check-code:
	@echo "Running comprehensive code checks..."
	@./scripts/check-code.sh --all

# Quick code checks (without tests)
check-quick:
	@echo "Running quick code checks..."
	@./scripts/check-code.sh --quick

# Development workflow
dev-setup: install-dev
	@echo "Development environment setup complete!"

# CI workflow
ci: check-all build check-dist
	@echo "CI pipeline complete!"

# Release workflow
release: ci
	@echo "Ready for release!"
	@echo "To release to Test PyPI: make upload-test"
	@echo "To release to PyPI: make upload" 