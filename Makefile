###############################################
#
# nau-openedx-extensions
#
###############################################

.DEFAULT_GOAL := help
.PHONY: requirements

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

requirements: ## install environment requirements
	pip install -r requirements/base.txt

python-test: clean ## Run tests
	$(TOX) pip install -r requirements/test.txt --exists-action w
	$(TOX) DJANGO_SETTINGS_MODULE=nau_openedx_extensions.settings.test coverage run --source="." -m pytest ./nau_openedx_extensions
	$(TOX) coverage report --fail-under=5

quality:
	$(TOX) pylint ./nau_openedx_extensions
	$(TOX) pycodestyle ./nau_openedx_extensions
	$(TOX) isort --check-only --recursive --diff ./nau_openedx_extensions


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

update_translations: | requirements_translations ## update strings to be translated
	pybabel extract -F conf/locale/babel.cfg -o conf/locale/django.pot nau_openedx_extensions
	pybabel update -N -D django -i conf/locale/django.pot -d conf/locale/
	rm conf/locale/django.pot

compile_translations: | requirements_translations ## compile .mo files into .po files
	pybabel compile -f -D django -d conf/locale/
