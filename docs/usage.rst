Usage and configuration
=======================

The NAU Open edX extensions plugin is a plugin to extend edx-platform features.

Plugin Settings
===============

This is the list of settings that you can alter globally:

- **NAU_REGISTRATION_MODULE**
    Default: ``'nau_openedx_extensions.edxapp_wrapper.backends.registration_l_v1'``

    Defines the module's path to use as the backend for edx-platform registration module.

- **NAU_GRADES_MODULE**
    Default: ``'nau_openedx_extensions.edxapp_wrapper.backends.grades_h_v1'``

    Defines the module's path to use as the backend for edx-platform grades module.

- **NAU_SESSION_TOUCH_ENABLED**
    Default: ``True``

    Enables the Studio session keep-alive middleware (fccn/nau-technical#1036). See
    ``docs/session_refresh.rst``.

- **NAU_SESSION_TOUCH_INTERVAL_SECONDS**
    Default: ``600``

    How often, at most, the Studio session keep-alive middleware touches an active session.
