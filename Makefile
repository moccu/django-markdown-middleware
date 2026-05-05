.PHONY: clean correct coverage-html docs tests release
.ONESHELL: release

clean:
	rm -fr build/ dist/ htmlcov/ __pycache__ .coverage

correct:
	uv run ruff format markdown_middleware tests
	uv run ruff check --fix markdown_middleware tests

docs:
	uv run --group docs $(MAKE) -C docs html

tests:
	uv run tox

coverage-html:
	uv run python -m pytest --cov=markdown_middleware --cov-report=html

release:
	@VERSION=$$(uv run python -c "import importlib.metadata; print(importlib.metadata.version('django-markdown-middleware'))")
	@echo About to release $${VERSION}
	@echo [ENTER] to continue; read
	git tag -a "$${VERSION}" -m "Version $${VERSION}" && git push --follow-tags
