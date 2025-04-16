# nau openedx extensions

NAU Open edX extensions is a [django app plugin](https://github.com/edx/edx-platform/tree/master/openedx/core/djangoapps/plugins) to make easier change or extend [edx-platform](https://github.com/edx/edx-platform)

## Installation
[Documentation](docs/installation.rst) about the installation.

## Usage
[Usage details](docs/usage.rst).

## Python

This package requires the same Python version of the edx-platform.
For redwood Python 3.11.

## Virtual environment

Create a python virtual environment.
```bash
python -m venv venv
```

And activate it.
Further steps should be run inside this virtual environment.

## Install requirements

```bash
make requirements
```

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

To extract, update translations files and to compile, simply run.

`make translations`

To translate, change the conf/locale/<lang>/LC_MESSAGES/django.po files.

Then to compile, just execute the same Makefile target.

`make translations`

## VSCode

To make VSCode detect the edx-platform code, add this to your project settings.

```json
{
    "python.autoComplete.extraPaths": ["${workspaceFolder}/../edx-platform"],
    "python.analysis.extraPaths": ["${workspaceFolder}/../edx-platform"],
}
```
