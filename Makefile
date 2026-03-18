PYTHON ?= python
ENV ?= dev

.PHONY: generate test allure report open-allure serve-allure ci

generate:
	$(PYTHON) tools/task_runner.py generate --env $(ENV)

test:
	$(PYTHON) tools/task_runner.py test --env $(ENV)

allure:
	$(PYTHON) tools/task_runner.py allure --env $(ENV)

report:
	$(PYTHON) tools/task_runner.py report --env $(ENV)

open-allure:
	$(PYTHON) tools/task_runner.py open --env $(ENV)

serve-allure:
	$(PYTHON) tools/task_runner.py serve --env $(ENV)

ci:
	$(PYTHON) tools/task_runner.py ci --env $(ENV)
