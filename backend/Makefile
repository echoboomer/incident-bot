VENV := venv

all: venv

$(VENV)/bin/activate: requirements.txt
	python3 -m venv $(VENV)
	./$(VENV)/bin/pip install -r requirements.txt

venv: $(VENV)/bin/activate

run: venv
	./$(VENV)/bin/python3 main.py

stage_migration: venv
ifndef DESCRIPTION
	@echo "DESCRIPTION is required, example: make DESCRIPTION=Do something stage_migration"
else
	./$(VENV)/bin/alembic revision -m "$(DESCRIPTION)"
endif

run_migrations: venv
	./$(VENV)/bin/alembic upgrade head

clean:
	rm -rf $(VENV)
	find . -type f -name '*.pyc' -delete

run-tests:
	pytest -vv tests/

.PHONY: all venv run clean render
