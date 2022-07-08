Usage and configuration
=======================

The NAU Open edX extensions plugin is a plugin to extend edx-platform features.

Plugin Settings
===============

This is the list of settings that you can alter globally:

- **NAU_CERTIFICATE_CONTEXT_EXTENSION**
    Default: ``'nau_openedx_extensions.certificates.context_extender.update_cert_context'``

    Defines the method's path to use when extending the context of certificates.

- **NAU_REGISTRATION_MODULE**
    Default: ``'nau_openedx_extensions.edxapp_wrapper.backends.registration_l_v1'``

    Defines the module's path to use as the backend for edx-platform registration module.    

- **NAU_GRADES_MODULE**
    Default: ``'nau_openedx_extensions.edxapp_wrapper.backends.grades_h_v1'``

    Defines the module's path to use as the backend for edx-platform grades module.
