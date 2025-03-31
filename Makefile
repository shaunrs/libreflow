PROJECT_NAME=hookup


dev: venv pre-commit

venv:
	python3 -m venv venv
	venv/bin/pip install poetry
	venv/bin/poetry install

pre-commit:
	ln -sf ../../pre-commit .git/hooks/

format:
	venv/bin/poetry run isort $(PROJECT_NAME)/ tests/
	venv/bin/poetry run black $(PROJECT_NAME)/ tests/

lint:
	venv/bin/poetry run pflake8 $(PROJECT_NAME)/ tests/

test:
	venv/bin/poetry run pytest -vs

update:
	venv/bin/poetry update

