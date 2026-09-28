.PHONY: help install install-dev run test coverage lint clean \
        build-core docs docker-build docker-up docker-down

PY ?= python3

help:
	@echo "Доступные команды:"
	@echo "  make install        
	@echo "  make install-dev    
	@echo "  make run            
	@echo "  make test          
	@echo "  make coverage       
	@echo "  make build-core    
	@echo "  make docs          
	@echo "  make docker-build  
	@echo "  make docker-up      
	@echo "  make docker-down   
	@echo "  make clean          

install:
	$(PY) -m pip install -r requirements.txt

install-dev:
	$(PY) -m pip install -r requirements-dev.txt

run:
	$(PY) -m app.main

test:
	$(PY) -m pytest

coverage:
	$(PY) -m pytest --cov=packages/core --cov=app --cov-report=html --cov-report=term-missing

build-core:
	cd packages/core && $(PY) -m build

docs:
	$(PY) -m pip install -r docs/requirements.txt
	mkdocs build -f docs/mkdocs.yml

docker-build:
	docker build -f infra/Dockerfile -t managermod:local .

docker-up:
	docker compose -f infra/compose.yaml up --build

docker-down:
	docker compose -f infra/compose.yaml down -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .coverage htmlcov build dist site