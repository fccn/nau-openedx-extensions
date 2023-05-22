"""
NAU additional configuration of Overhangio scorm xblock for openedx.
https://github.com/overhangio/openedx-scorm-xblock

On NAU we store the static assets on a S3 bucket.
By default the Django storage is configured so the user connects and get the files from the
S3 server / domain.
But, to make the SCORM score work, we need that the SCORM files need to be delivered on the
same domain.
This fixes:
```
Error: Unable to aquire LMS API
```

JS console error:
```
Uncaught DOMException: Blocked a frame with origin "https://<bucket_domain>" from accessing a cross-origin frame
```
"""
from django.conf import settings
from django.utils.module_loading import import_string

from nau_openedx_extensions.edxapp_wrapper import site_configuration_helpers as configuration_helpers


def scorm_xblock_storage(xblock):  # pylint: disable=unused-argument
    """
    Custom SCORM storage configuration.
    So S3 storage to save the bucket
    """
    return get_scorm_storage() if hasattr(settings, 'NAU_SCORM_XBLOCK_STORAGE') else None


def get_scorm_storage():
    """
    Return the configured django storage backend for SCORM xblock.
    It requires the `NAU_SCORM_XBLOCK_STORAGE` setting and inside it uses additional settings:
    - `STORAGE_CLASS` - the class of the Django storage to use
    - `STORAGE_KWARGS` - the additional kwargs for the Django storage
    The location can be changed by directly changing the location inside the xblock.

    ```python
    XBLOCK_SETTINGS["ScormXBlock"] = {
        "LOCATION": "alternatevalue",
    }
    ```

    It automatically creates and adds the `custom_domain` on the kwargs of the storage.
    ```yaml
    NAU_SCORM_XBLOCK_STORAGE:
        STORAGE_CLASS: storages.backends.s3boto3.S3Boto3Storage
        STORAGE_KWARGS:
            default_acl: public-read
            querystring_expire: 86400
            access_key: XXXX
            secret_key: YYYY
            bucket: ZZZZ
    ```
    """
    if hasattr(settings, 'NAU_SCORM_XBLOCK_STORAGE'):
        storage_kwargs = get_storage_kwargs()
        return get_storage_class(
            settings.NAU_SCORM_XBLOCK_STORAGE.get('STORAGE_CLASS'),
        )(**storage_kwargs)

    # during edx-platform loading this method gets called but settings are not ready yet
    # so in that case we will return default(FileSystemStorage) storage class instance
    return get_storage_class()()


def get_storage_kwargs():
    """
    Build Django storage class additional kwargs with a dynamic `custom_domain` parameter
    that depends on the current in use LMS URL.
    """

    if settings.SERVICE_VARIANT == "lms":
        domain = configuration_helpers.get_value('LMS_BASE', settings.LMS_BASE)
    else:
        domain = configuration_helpers.get_value('CMS_BASE', settings.CMS_BASE)
    storage_kwargs_settings = settings.NAU_SCORM_XBLOCK_STORAGE.get('STORAGE_KWARGS', {})
    return {**storage_kwargs_settings, **{'custom_domain': domain}}


def get_storage_class(import_path=None):
    """
    Get the Django storage class to be used by custom SCORM storage.
    """
    return import_string(import_path or settings.DEFAULT_FILE_STORAGE)
