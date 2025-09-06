.PHONY: setup venv install lint test render apply deploy rollback

PY=python3
PIP=pip

venv:
	$(PY) -m venv .venv

setup: venv
	. .venv/bin/activate && $(PIP) install -U pip && $(PIP) install -r requirements.txt

install:
	$(PY) -m pip install -U pip && $(PY) -m pip install -r requirements.txt

lint:
	@echo "Add your linter (ruff/flake8) here"

test:
	$(PY) -m pytest -q

render:
	cicd render --values .env.sample --outdir build/manifests

apply:
	cicd apply --manifests build/manifests

deploy:
	cicd deploy --values .env.sample

rollback:
	cicd rollback --namespace $${NAMESPACE:-demo}
