###############################################
#
# nau-openedx-extensions
#
###############################################

.DEFAULT_GOAL := help
.PHONY: help

# ==============================================================================
# VARIABLES
# ==============================================================================
# current directory relative to the Makefile file
ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

# By default use the sibling edx-platform folder
# but you can use other folder, you just have to change this environment variable like:
#   EDX_PLATFORM_PATH=/nau make test
#   make EDX_PLATFORM_PATH=/nau test
EDX_PLATFORM_PATH ?= $(shell dirname $(ROOT_DIR))/edx-platform

# Virtual environment
VENV_DIR := $(ROOT_DIR)/venv
VENV_BIN := $(VENV_DIR)/bin
PYTHON := $(VENV_BIN)/python
PIP := $(VENV_BIN)/pip
COVERAGE := $(VENV_BIN)/coverage
PYTEST := $(VENV_BIN)/pytest

# MongoDB variables for testing
MONGO_CONTAINER_NAME := nau-test-mongodb
MONGO_PORT := 27017
MONGO_IMAGE := mongo:7


help: ## display this help message
	@echo "Please use \`make <target>' where <target> is one of"
	@grep '^[a-zA-Z]' $(MAKEFILE_LIST) | sort | awk -F ':.*?## ' 'NF==2 {printf "\033[36m  %-25s\033[0m %s\n", $$1, $$2}'

_prerequire: ## Check that edx-platform directory exists
	@if [ ! -d "${EDX_PLATFORM_PATH}" ]; then { echo "edx-platform directory doesn't exist.\n  EDX_PLATFORM_PATH=${EDX_PLATFORM_PATH}\nPlease check if that directory exists or change the default value using:\n  EDX_PLATFORM_PATH=~/<different path>/edx-platform make <target>" ; exit 1; } fi
.PHONY: _prerequire

clean: ## delete most git-ignored files
	@find . -name '__pycache__' -exec rm -rf {} +
	@find . -name '*.pyc' -exec rm -f {} +
	@find . -name '*.pyo' -exec rm -f {} +
	@find . -name '*~' -exec rm -f {} +
	@-rm -rf .coverage .coverage.*
	@echo "✓ Cleaned"
# rm -rf venv +
.PHONY: clean

_check_python: ## Check Python version is 3.11
	@python_version=$$(python3 --version 2>&1 | grep -oP '3\.11\.\d+'); \
	if [ -z "$$python_version" ]; then \
		echo "Error: Python 3.11 is required but not found."; \
		echo "Current version: $$(python3 --version)"; \
		exit 1; \
	else \
		echo "✓ Using Python $$python_version"; \
	fi
.PHONY: _check_python

_venv: _check_python ## Create virtual environment if it doesn't exist
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "Creating virtual environment with Python 3.11..."; \
		python3 -m venv $(VENV_DIR); \
		echo "✓ Virtual environment created at $(VENV_DIR)"; \
	fi
	@venv_python_version=$$($(PYTHON) --version 2>&1 | grep -oP '3\.11\.\d+'); \
	if [ -z "$$venv_python_version" ]; then \
		echo "Error: Virtual environment is not using Python 3.11"; \
		echo "Virtual environment Python: $$($(PYTHON) --version)"; \
		echo "Please remove the venv directory and try again: rm -rf $(VENV_DIR)"; \
		exit 1; \
	fi
.PHONY: _venv

requirements: | _prerequire _venv pre-requirements ## Install requirements from both edx-platform and nau-openedx-extensions
	@echo "Installing edx-platform testing requirements..."
	$(PIP) install -r ${EDX_PLATFORM_PATH}/requirements/edx/testing.txt
	@echo "Installing edx-platform in editable mode..."
	$(PIP) install -e ${EDX_PLATFORM_PATH}
	@echo "Installing nau-openedx-extensions test requirements..."
	$(PIP) install -r $(ROOT_DIR)/requirements/test.in
	@echo "Installing nau-openedx-extensions in editable mode..."
	$(PIP) install -e $(ROOT_DIR)
	@echo "✓ All requirements installed successfully"
.PHONY: requirements

# ==============================================================================
# MONGODB TARGETS
# ==============================================================================

mongo-start: ## Start MongoDB container for testing (localhost only)
	@if docker ps -a --format '{{.Names}}' | grep -q "^$(MONGO_CONTAINER_NAME)$$"; then \
		if docker ps --format '{{.Names}}' | grep -q "^$(MONGO_CONTAINER_NAME)$$"; then \
			echo "MongoDB container '$(MONGO_CONTAINER_NAME)' is already running"; \
		else \
			echo "Starting existing MongoDB container '$(MONGO_CONTAINER_NAME)'..."; \
			docker start $(MONGO_CONTAINER_NAME); \
			$(MAKE) --no-print-directory mongo-ping; \
		fi \
	else \
		echo "Creating and starting MongoDB container '$(MONGO_CONTAINER_NAME)'..."; \
		docker run -d --name $(MONGO_CONTAINER_NAME) -p 127.0.0.1:$(MONGO_PORT):27017 $(MONGO_IMAGE); \
		$(MAKE) --no-print-directory mongo-ping; \
	fi
.PHONY: mongo-start

mongo-stop: ## Stop and remove MongoDB container
	@if docker ps --format '{{.Names}}' | grep -q "^$(MONGO_CONTAINER_NAME)$$"; then \
		echo "Stopping MongoDB container '$(MONGO_CONTAINER_NAME)'..."; \
		docker stop $(MONGO_CONTAINER_NAME); \
		docker rm $(MONGO_CONTAINER_NAME); \
		echo "MongoDB container stopped and removed"; \
	else \
		if docker ps -a --format '{{.Names}}' | grep -q "^$(MONGO_CONTAINER_NAME)$$"; then \
			echo "Removing stopped MongoDB container '$(MONGO_CONTAINER_NAME)'..."; \
			docker rm $(MONGO_CONTAINER_NAME); \
		else \
			echo "MongoDB container '$(MONGO_CONTAINER_NAME)' is not running"; \
		fi \
	fi
.PHONY: mongo-stop

mongo-status: ## Check MongoDB container status
	@if docker ps --format '{{.Names}}' | grep -q "^$(MONGO_CONTAINER_NAME)$$"; then \
		echo "✓ MongoDB container '$(MONGO_CONTAINER_NAME)' is running"; \
		docker ps --filter "name=$(MONGO_CONTAINER_NAME)" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"; \
	else \
		if docker ps -a --format '{{.Names}}' | grep -q "^$(MONGO_CONTAINER_NAME)$$"; then \
			echo "✗ MongoDB container '$(MONGO_CONTAINER_NAME)' exists but is not running"; \
		else \
			echo "✗ MongoDB container '$(MONGO_CONTAINER_NAME)' does not exist"; \
		fi; \
		exit 1; \
	fi
.PHONY: mongo-status

mongo-ping: ## Wait for MongoDB to be ready
	@echo "Waiting for MongoDB to be ready..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		if docker exec $(MONGO_CONTAINER_NAME) mongosh --quiet --eval "db.runCommand({ ping: 1 })" >/dev/null 2>&1; then \
			echo "✓ MongoDB is ready"; \
			exit 0; \
		fi; \
		echo "  Attempt $$i/10: MongoDB not ready yet, waiting..."; \
		sleep 1; \
	done; \
	echo "✗ MongoDB failed to start within 10 seconds"; \
	exit 1
.PHONY: mongo-ping

_mongo_ensure_running: ## Internal: ensure MongoDB is running
	@if ! docker ps --format '{{.Names}}' | grep -q "^$(MONGO_CONTAINER_NAME)$$"; then \
		echo "MongoDB is not running. Starting MongoDB container..."; \
		$(MAKE) --no-print-directory mongo-start; \
	fi
.PHONY: _mongo_ensure_running

_mongo_cleanup: ## Internal: cleanup MongoDB after tests
	@trap '$(MAKE) --no-print-directory mongo-stop' EXIT; \
	$(MAKE) --no-print-directory _run_tests ARGS="$(ARGS)"
.PHONY: _mongo_cleanup

_run_tests: clean | _prerequire _venv ## Internal: run the actual tests
	@args="$(filter-out $@,$(MAKECMDGOALS))" && \
	arg_2="$${args:-${ARGS}}" && \
	arg_3="$${arg_2:=$(ROOT_DIR)/nau_openedx_extensions}" && \
	cd ${EDX_PLATFORM_PATH} && \
	PYTHONPATH=${EDX_PLATFORM_PATH}:$(ROOT_DIR) \
	EDXAPP_TEST_MONGO_HOST=localhost \
	EDXAPP_TEST_MONGO_PORT=$(MONGO_PORT) \
	$(COVERAGE) run --source="$(ROOT_DIR)/nau_openedx_extensions" -m pytest --ds=nau_openedx_extensions.settings.test --nomigrations --reuse-db -o django_find_project=false $${arg_3}
	@cd ${EDX_PLATFORM_PATH} && $(COVERAGE) combine || true
	@cd ${EDX_PLATFORM_PATH} && $(COVERAGE) report --include="$(ROOT_DIR)/nau_openedx_extensions/*" --fail-under=5
	@echo "✓ Tests passed"
.PHONY: _run_tests

test: _prerequire ## Run tests with auto-managed MongoDB (starts, runs tests, stops). Usage: make test `pwd`/[path/to/test_file.py::TestClass::test_method]
	@$(MAKE) --no-print-directory mongo-start
	@cleanup() { $(MAKE) --no-print-directory mongo-stop; }; \
	trap cleanup EXIT INT TERM; \
	args="$(filter-out $@,$(MAKECMDGOALS))"; \
	$(MAKE) --no-print-directory _run_tests ARGS="$$args"
.PHONY: test

test-keep-mongo: _prerequire ## Run tests with MongoDB (starts if needed, keeps running after). Usage: make test-keep-mongo `pwd`/[path/to/test_file.py::TestClass::test_method]
	@$(MAKE) --no-print-directory _mongo_ensure_running
	@args="$(filter-out $@,$(MAKECMDGOALS))" && \
	$(MAKE) --no-print-directory _run_tests ARGS="$$args"
.PHONY: test-keep-mongo

lint: | _prerequire _venv ## Run linters to check code style
	@cd ${EDX_PLATFORM_PATH} && PYTHONPATH=${EDX_PLATFORM_PATH}:$(ROOT_DIR) $(VENV_BIN)/pylint $(ROOT_DIR)/nau_openedx_extensions
	@cd ${EDX_PLATFORM_PATH} && PYTHONPATH=${EDX_PLATFORM_PATH}:$(ROOT_DIR) $(VENV_BIN)/pycodestyle $(ROOT_DIR)/nau_openedx_extensions
	@cd ${EDX_PLATFORM_PATH} && PYTHONPATH=${EDX_PLATFORM_PATH}:$(ROOT_DIR) $(VENV_BIN)/isort --check-only --diff $(ROOT_DIR)/nau_openedx_extensions
	@echo "✓ Linting passed"
.PHONY: lint

lint-fix: | _prerequire _venv ## Fix Python import sort
	@cd ${EDX_PLATFORM_PATH} && PYTHONPATH=${EDX_PLATFORM_PATH}:$(ROOT_DIR) $(VENV_BIN)/isort $(ROOT_DIR)/nau_openedx_extensions
	@cd ${EDX_PLATFORM_PATH} && PYTHONPATH=${EDX_PLATFORM_PATH}:$(ROOT_DIR) $(VENV_BIN)/autopep8 --in-place --aggressive --aggressive $(ROOT_DIR)/nau_openedx_extensions/*.py
	@echo "✓ Linting fixes applied"
.PHONY: lint-fix

# Define PIP_COMPILE_OPTS=-v to get more information during make upgrade.
PIP_COMPILE = $(VENV_BIN)/pip-compile --rebuild --upgrade $(PIP_COMPILE_OPTS)

pre-requirements: _venv ## install Python requirements for running pip-tools
	$(PIP) install -r requirements/pip.txt
	$(PIP) install -r requirements/pip-tools.txt
.PHONY: pre-requirements

compile-requirements: export CUSTOM_COMPILE_COMMAND=make compile-requirements
compile-requirements: pre-requirements ## Re-compile *.in requirements to *.txt
	@# Bootstrapping: Rebuild pip and pip-tools first, and then install them
	@# so that if there are any failures we'll know now, rather than the next
	@# time someone tries to use the outputs.
	sed '/^django-simple-history==/d' requirements/common_constraints.txt > requirements/common_constraints.tmp
	mv requirements/common_constraints.tmp requirements/common_constraints.txt
	sed 's/Django<4.0//g' requirements/common_constraints.txt > requirements/common_constraints.tmp
	mv requirements/common_constraints.tmp requirements/common_constraints.txt
	$(VENV_BIN)/pip-compile -v --allow-unsafe ${COMPILE_OPTS} -o requirements/pip.txt requirements/pip.in
	$(PIP) install -r requirements/pip.txt

	$(VENV_BIN)/pip-compile -v ${COMPILE_OPTS} -o requirements/pip-tools.txt requirements/pip-tools.in
	$(PIP) install -r requirements/pip-tools.txt
	$(PIP_COMPILE) -o requirements/base.txt requirements/base.in
	$(PIP_COMPILE) -o requirements/test.txt requirements/test.in
	$(PIP_COMPILE) -o requirements/tox.txt requirements/tox.in
	# Let tox control the Django, and django-filter version for tests
	grep -e "^django==" -e "^celery==" -e "^edx-opaque-keys[django]==" requirements/test.txt > requirements/django.txt
	sed '/^[dD]jango==/d;/^celery==/d;/^edx-opaque-keys[django]==/d' requirements/test.txt > requirements/test.tmp
	mv requirements/test.tmp requirements/test.txt
.PHONY: compile-requirements

upgrade:  ## update the pip requirements files to use the latest releases satisfying our constraints
	$(MAKE) --no-print-directory compile-requirements COMPILE_OPTS="--upgrade"
.PHONY: upgrade

# TODO: define somewhere else
lang_targets = en pt_PT

create_translations_catalogs: ## Create the initial configuration of .mo files for translation
	pybabel extract -F conf/locale/babel.cfg -o  conf/locale/django.pot --msgid-bugs-address=equipa@nau.edu.pt --copyright-holder=NAU nau_openedx_extensions
	for lang in $(lang_targets) ; do \
        pybabel init -i conf/locale/django.pot -D django -d conf/locale/ -l $$lang ; \
    done
.PHONY: create_translations_catalogs

extract_translations:
	pybabel extract -F conf/locale/babel.cfg -o conf/locale/django.pot nau_openedx_extensions
.PHONY: extract_translations

update_translations_po_files:
	pybabel update -N -D django -i conf/locale/django.pot -d conf/locale/
.PHONY: update_translations_po_files

clean_translations_intermediate:
	rm conf/locale/django.pot
.PHONY: clean_translations_intermediate

translations: | extract_translations update_translations_po_files clean_translations_intermediate compile_translations ## extract, update and compile translations
.PHONY: translations

compile_translations:
	pybabel compile -f -D django -d conf/locale/
.PHONY: compile_translations

check_miss_run_update_translations: | extract_translations update_translations_po_files clean_translations_intermediate ## Check if `make update_translations` should be run
	@for lang in $(lang_targets) ; do \
		git diff --numstat */$$lang/*.po | awk '{if ($$1>1 || $$2>1) { exit 1 } else { exit 0 }}'; \
	done
	@echo "✓ No missing translations detected."
.PHONY: check_miss_run_update_translations
