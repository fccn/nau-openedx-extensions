###############################################
#
# nau-openedx-extensions
#
###############################################

.DEFAULT_GOAL := help
.PHONY: help

ifdef TOXENV
TOX := tox -- #to isolate each tox environment if TOXENV is defined
endif


help: ## display this help message
	@echo "Please use \`make <target>' where <target> is one of"
	@grep '^[a-zA-Z]' $(MAKEFILE_LIST) | sort | awk -F ':.*?## ' 'NF==2 {printf "\033[36m  %-25s\033[0m %s\n", $$1, $$2}'

clean: ## delete most git-ignored files
	find . -name '__pycache__' -exec rm -rf {} +
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	echo "cleaned"
# rm -rf venv +
.PHONY: clean

requirements: ## Install requirements
	python -m pip install -r requirements/base.txt
	python -m pip install -r requirements/translations.txt
	python -m pip install -r requirements/test.txt
.PHONY: requirements

test: clean ## Run all python tests
	$(TOX) pip install -r requirements/test.txt --exists-action w
	$(TOX) DJANGO_SETTINGS_MODULE=nau_openedx_extensions.settings.test coverage run --source="." -m pytest ./nau_openedx_extensions
	$(TOX) coverage report --fail-under=5
.PHONY: test

lint: ## Run linters to check code style
	$(TOX) pylint ./nau_openedx_extensions
	$(TOX) pycodestyle ./nau_openedx_extensions
	$(TOX) isort --check-only --diff ./nau_openedx_extensions
.PHONY: lint

lint-fix: ## Fix Python import sort
	$(TOX) isort ./nau_openedx_extensions
	$(TOX) autopep8 --in-place --aggressive --aggressive ./nau_openedx_extensions/*.py
.PHONY: lint-fix

# Define PIP_COMPILE_OPTS=-v to get more information during make upgrade.
PIP_COMPILE = pip-compile --rebuild --upgrade $(PIP_COMPILE_OPTS)

pre-requirements: ## install Python requirements for running pip-tools
	pip install -r requirements/pip.txt
	pip install -r requirements/pip-tools.txt
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
	pip-compile -v --allow-unsafe ${COMPILE_OPTS} -o requirements/pip.txt requirements/pip.in
	pip install -r requirements/pip.txt

	pip-compile -v ${COMPILE_OPTS} -o requirements/pip-tools.txt requirements/pip-tools.in
	pip install -r requirements/pip-tools.txt
	$(PIP_COMPILE) -o requirements/base.txt requirements/base.in
	$(PIP_COMPILE) -o requirements/test.txt requirements/test.in
	$(PIP_COMPILE) -o requirements/tox.txt requirements/tox.in
	# Let tox control the Django, and django-filter version for tests
	grep -e "^django==" -e "^celery==" -e "^edx-opaque-keys[django]==" requirements/test.txt > requirements/django.txt
	sed '/^[dD]jango==/d;/^celery==/d;/^edx-opaque-keys[django]==/d' requirements/test.txt > requirements/test.tmp
	mv requirements/test.tmp requirements/test.txt
.PHONY: compile-requirements

upgrade:  ## update the pip requirements files to use the latest releases satisfying our constraints
	$(MAKE) compile-requirements COMPILE_OPTS="--upgrade"
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
	git diff --numstat *.po | awk '{if ($$1>1 || $$2>1) { exit 1 } else { exit 0 }}'
	@echo "OK"
.PHONY: check_miss_run_update_translations
