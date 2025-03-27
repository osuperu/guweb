#!/usr/bin/env make

shell:
	poetry shell

install:
	POETRY_VIRTUALENVS_IN_PROJECT=1 poetry install --no-root

uninstall:
	poetry env remove python

# To bump the version number run `make bump version=<major/minor/patch>`
# (DO NOT USE IF YOU DON'T KNOW WHAT YOU'RE DOING)
# https://python-poetry.org/docs/cli/#version
bump:
	poetry version $(version)