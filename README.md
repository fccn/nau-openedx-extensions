# nau openedx extensions

NAU Open edX extensions is a [django app plugin](https://github.com/edx/edx-platform/tree/master/openedx/core/djangoapps/plugins) to make easier change or extend [edx-platform](https://github.com/edx/edx-platform)

## Installation
[Documentation](docs/installation.rst) about the installation.

## Usage
[Usage details](docs/usage.rst).

## Development

## Tests

```
virtualenv venv --python=python3.8
. venv/bin/activate
make python-test
```

## Translations

Run the translations target on a virtual environment.

```
virtualenv --python=python3 venv
. venv/bin/activate
```

To extract strings to be translated from the source code.
`make update_translations`

Translate by changing the conf/locale/<lang>/LC_MESSAGES/django.po files, then compile them to po files by running:
`make compile_translations`
