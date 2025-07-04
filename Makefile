.PHONY: dev test deploy install clean local

dev: fix
	@. .venv/bin/activate && export PYTHONPATH=$$(pwd):$$PYTHONPATH && DEV=True python -m main

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
	@. .venv/bin/activate && pip install isort git+https://github.com/pre63/black.git xai_sdk kagglehub scikit-learn pandas pathlib numpy kagglehub pandas scikit-learn numpy requests nltk transformers torch Pillow python-dotenv

build: fix
	@docker build -t pbn-app .

local: build
	@docker run -p 8080:8080 --network host -e DEV=docker pbn-app

deploy: fix
	fly deploy

generate:
	@. .venv/bin/activate && export PYTHONPATH=$$(pwd):$$PYTHONPATH && . .env && python3 -m scripts.article

dates:
	@. .venv/bin/activate && export PYTHONPATH=$$(pwd):$$PYTHONPATH && . .env && python3 -m scripts.dates

cross_post:
	@. .venv/bin/activate && export PYTHONPATH=$$(pwd):$$PYTHONPATH && . .env && python3 -m scripts.cross_post

images:
	@. .venv/bin/activate && export PYTHONPATH=$$(pwd):$$PYTHONPATH && . .env && python3 -m scripts.images hilltopsnewspaper.com  & \
	. .venv/bin/activate && export PYTHONPATH=$$(pwd):$$PYTHONPATH && . .env && python3 -m scripts.images powersporta.com  & \
	. .venv/bin/activate && export PYTHONPATH=$$(pwd):$$PYTHONPATH && . .env && python3 -m scripts.images spotnews24.com  & \
	. .venv/bin/activate && export PYTHONPATH=$$(pwd):$$PYTHONPATH && . .env && python3 -m scripts.images terrafirmanews.com  & \
	. .venv/bin/activate && export PYTHONPATH=$$(pwd):$$PYTHONPATH && . .env && python3 -m scripts.images voltapowers.com 

clean:
	@rm -rf .venv
	@rm -rf __pycache__
	@rm -rf .pytest_cache
	@rm -rf .mypy