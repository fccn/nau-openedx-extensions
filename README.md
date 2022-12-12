# nau openedx extensions

NAU Open edX extensions is a [django app plugin](https://github.com/edx/edx-platform/tree/master/openedx/core/djangoapps/plugins) to make easier change or extend [edx-platform](https://github.com/edx/edx-platform)

## Installation
[Documentation](docs/installation.rst) about the installation.

## Usage
[Usage details](docs/usage.rst).

## Virtual environment
Create a python virtual environment.
```bash
make virtual_environment
```
And activate it.
Further steps should be run inside this virtual environment.

## Tests

To run the python tests execute, inside the previous create virtual environment.

```bash
make test
```

## Lint

To run the linters to check code quality, inside the previous create virtual environment.

```bash
make lint
```

## Translations

Run the translations target on a virtual environment.

```bash
virtualenv --python=python3 venv
. venv/bin/activate
```

To extract strings to be translated from the source code.
`make update_translations`

Then translate by changing the conf/locale/<lang>/LC_MESSAGES/django.po files.
Then recompile them executing the same makefile target.
`make update_translations`

