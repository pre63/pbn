.PHONY: dev test deploy install clean local

dev: fix
	@. .venv/bin/activate && DEV=True python -m src.app

fix:
	@. .venv/bin/activate && isort .
	@. .venv/bin/activate && black .
	#@nfmt .

test:
	@. .venv/bin/activate && python -m tests.telegram
	@. .venv/bin/activate && python -m tests.latex

install:
	@python3 -m venv .venv
	@. .venv/bin/activate && pip install -r requirements.txt
	@. .venv/bin/activate && pip install isort git+https://github.com/pre63/black.git openai

build: fix
	@docker build -t pbn-app .

local: build
	@docker run -p 8080:8080 --network host -e DEV=docker pbn-app

deploy: fix
	fly deploy

generate:
	@. .venv/bin/activate && . .env && python3 -m scripts.article

clean:
	@rm -rf .venv
	@rm -rf __pycache__
	@rm -rf .pytest_cache
	@rm -rf .mypy
