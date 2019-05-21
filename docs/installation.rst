
============
Installation
============


To install the NAU Open edX extensions plugin in an Open edX instance you need to do the following steps:

* Use pip to install the plugin into the same virtualenv that has all the dependencies for edxapp (edx-platform).
* Run the database migrations if required.
* Configure the plugin as required.

We will go into detail on how to achieve this for the two more common ways of running Open edX.


Docker Devstack
===============

The `devstack <https://github.com/edx/devstack>`_ install based on docker is a very popular way of launching a development environment of the Open edX services. If you are running this environment then follow this steps.


#. First step is to get the code and install it.

    In the directory where you created your `devstack` you also have now a `src` directory. You can download the code there.

    .. code-block:: bash

        cd src
        sudo mkdir edxapp
        sudo chown $USER edxapp/
        cd edxapp
        git clone https://gitlab.fccn.pt/nau/nau-openedx-extensions.git

    Now we need to install it in the virtualenv.

    .. code-block:: bash

        cd ../../devstack
        docker-compose exec lms bash -c 'source /edx/app/edxapp/edxapp_env && cd /edx/src/edxapp/nau-openedx-extensions && pip install -e .'
        make lms-restart

    Or more interactively if you prefer

    .. note::
        If you already ran the previous instructions you can skip ahead to the next step.

    .. code-block:: bash

        cd ../../devstack
        make lms-shell
        cd /edx/src/edxapp/nau-openedx-extensions/
        pip install -e .
        exit
        make lms-restart

    .. note::
        We are running the installation in editable mode (-e). When developing or testing, if you make any changes to the code, the server should restart automatically. This will happen if you checkout different tags or branches of the code as well. To see the server restart in action you can see the logs using

    .. code-block:: bash

        docker logs edx.devstack.lms -f

    You can also restart the server manually with

    .. code-block:: bash

        make lms-restart


#. Run the database migrations

    To run the database migration in the devstack environment

    .. code-block:: bash

        make lms-update-db

    You should see this on your console.

    .. code-block:: bash

        Running migrations:
          Applying nau_openedx_extensions.0001_initial... OK

    .. note::
        The database is shared between lms and studio so you only need to migrate once for both applications.


#. Configure the plugin to work with edxapp(edx-platform) at ``lms.env.json``

    Let edx-platform work with a custom form:

    .. code-block:: json

        {
            ...
            "REGISTRATION_EXTENSION_FORM": "nau_openedx_extensions.custom_registration_form.forms.NauUserExtendedForm"
            ...
        }


#. For every course requiring extra certificate context, use the advanced studio settings ``Certificate Web/HTML View Overrides`` as follows:

    .. code-block:: json

        {
            "nau_certs_settings": {
                "update_with_grades_context": true,
                "interpolated_strings": {
                    "completion_statement": "This acknowledges that {cc_first_name} {cc_last_name} has succesfully completed the course"
                }
            }
        }

    .. image:: images/certs_config_example.png

    .. note::
        Since grades calculation could take a while, you could configure the plugin to avoid such process using ``"update_with_grades_context": false``.


Native Installation
===================

The native environment is regarded as a base ubuntu 16.04 server where the ansible playbooks from the `configuration <https://github.com/edx/configuration>`_ repository where run.

Using ansible
-------------

If you use ansible to create or update your instance of the Open edX project, then most likely you have a ``serve-vars.yml`` directory or you have some form of *secure data* repository.

To install the SEB Open edX plugin in there you need to change some ansible variables and re-run your installation playbooks.

    .. code-block:: yaml

        EDXAPP_PRIVATE_REQUIREMENTS:
          # NAU plugin
          - name: 'git+ssh://git@gitlab.fccn.pt/nau/nau-openedx-extensions.git@v1.0.3#egg=nau_openedx_extensions==1.0.3'

        EDXAPP_ENV_EXTRA:
          REGISTRATION_EXTENSION_FORM: "nau_openedx_extensions.custom_registration_form.forms.NauUserExtendedForm"


Some site operators prefer not to run database migration during the playbook runs. If this is you, then please run the migrations manually.

    .. code-block:: shell

        /edx/bin/edxapp-migrate-lms


Installing manually
-------------------

To run the installation without the help of any script you still need to run the same basic steps.

#. Install the code

    .. code-block:: shell

        sudo su edxapp -s /bin/bash
        /edx/bin/pip.edxapp install git+ssh://git@gitlab.fccn.pt/nau/nau-openedx-extensions.git@v1.0.3#egg=nau_openedx_extensions==1.0.3


#. Restart the services


    .. code-block:: shell

        /edx/bin/supervisorctl restart all

#. Run the database migrations

    .. code-block:: shell

        /edx/bin/edxapp-migrate-lms
