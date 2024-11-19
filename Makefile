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

virtual_environment: ## create virtual environment
	test -d venv || virtualenv venv --python=python3
	. venv/bin/activate && python -m pip install -Ur requirements/base.txt
	. venv/bin/activate && python -m pip install -Ur requirements/translations.txt
	. venv/bin/activate && python -m pip install -Ur requirements/test.txt
	touch venv/touchfile
	@echo "Run on your shell to activate the new virtual environment:"
	@echo "  . venv/bin/activate"

requirements: ## install environment requirements
	pip install -r requirements/base.txt

test: clean ## Run all python tests
	$(TOX) pip install -r requirements/test.txt --exists-action w
	$(TOX) DJANGO_SETTINGS_MODULE=nau_openedx_extensions.settings.test coverage run --source="." -m pytest ./nau_openedx_extensions
	$(TOX) coverage report --fail-under=5

lint: ## Run linters to check code style
	$(TOX) pylint ./nau_openedx_extensions
	$(TOX) pycodestyle ./nau_openedx_extensions
	$(TOX) isort --check-only --diff ./nau_openedx_extensions

isort: ## Fix Python import sort
	$(TOX) isort ./nau_openedx_extensions


# Define PIP_COMPILE_OPTS=-v to get more information during make upgrade.
PIP_COMPILE = pip-compile --rebuild --upgrade $(PIP_COMPILE_OPTS)

upgrade: export CUSTOM_COMPILE_COMMAND=make upgrade
upgrade: ## update the requirements/*.txt files with the latest packages satisfying requirements/*.in
	pip install -qr requirements/pip-tools.txt
	# Make sure to compile files after any other files they include!
	$(PIP_COMPILE) -o requirements/pip-tools.txt requirements/pip-tools.in
	$(PIP_COMPILE) -o requirements/base.txt requirements/base.in
	$(PIP_COMPILE) -o requirements/test.txt requirements/test.in
	$(PIP_COMPILE) -o requirements/tox.txt requirements/tox.in
	# Let tox control the Django, and django-filter version for tests
	grep -e "^django==" -e "^celery==" -e "^edx-opaque-keys[django]==" requirements/test.txt > requirements/django.txt
	sed '/^[dD]jango==/d;/^celery==/d;/^edx-opaque-keys[django]==/d' requirements/test.txt > requirements/test.tmp
	mv requirements/test.tmp requirements/test.txt

requirements_translations:
	pip install Babel==2.9.0
	pip install mako==1.0.2

# TODO: define somewhere else
lang_targets = en pt_PT

create_translations_catalogs: | requirements_translations ## Create the initial configuration of .mo files for translation
	pybabel extract -F conf/locale/babel.cfg -o  conf/locale/django.pot --msgid-bugs-address=equipa@nau.edu.pt --copyright-holder=NAU nau_openedx_extensions
	for lang in $(lang_targets) ; do \
        pybabel init -i conf/locale/django.pot -D django -d conf/locale/ -l $$lang ; \
    done

extract_translations:
	pybabel extract -F conf/locale/babel.cfg -o conf/locale/django.pot nau_openedx_extensions

update_translations_po_files:
	pybabel update -N -D django -i conf/locale/django.pot -d conf/locale/

clean_translations_intermediate:
	rm conf/locale/django.pot

update_translations: | extract_translations update_translations_po_files clean_translations_intermediate compile_translations ## update strings to be translated

compile_translations:
	pybabel compile -f -D django -d conf/locale/

check_miss_run_update_translations: | extract_translations update_translations_po_files clean_translations_intermediate ## Check if `make update_translations` should be run
	git diff --numstat *.po | awk '{if ($$1>1 || $$2>1) { exit 1 } else { exit 0 }}'
	@echo "OK"
