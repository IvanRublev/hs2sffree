.PHONY: venv deps deps-upgrade deps-add deps-add-dev lint format test watch watch-one run build build-clean

venv:
	uv venv --no-managed-python

deps:
	uv sync --dev --locked

deps-upgrade:
	uv lock --upgrade

deps-add:
	uv add "$(NAME)"

deps-add-dev:
	uv add --dev "$(NAME)" 

lint:
	uv run ruff check . && uv run pyrefly check src

format:
	ruff format .

test:
	uv run pytest

watch:
	ptw -s -vv

watch-one:
	ptw -s -vv "$(NAME)" "$(NAME)"

run:
	python main.py

build:
	mkdir -p dist
	uv run nuitka --onefile --output-dir=dist --output-filename=hs2sffree main.py

build-clean:
	rm -rf dist build *.spec
