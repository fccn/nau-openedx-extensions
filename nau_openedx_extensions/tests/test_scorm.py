"""
Tests that check the extended settings for overhangio SCORM xblock.
"""
from django.test import TestCase
from django.test.utils import override_settings

from nau_openedx_extensions.scorm.storage import get_storage_kwargs, scorm_xblock_storage


class SCORMXblockTest(TestCase):
    """
    Tests that check the extended settings for overhangio SCORM xblock.
    """

    def test_scorm_storage_no_scorm_storage_setting(self):
        """
        Test if `NAU_SCORM_XBLOCK_STORAGE` is not defined then we shouldn't create a custom storage for the
        SCORM Xblock.
        """
        self.assertIsNone(scorm_xblock_storage(None))

    @override_settings(LMS_BASE='lms.example.com', SERVICE_VARIANT="lms", NAU_SCORM_XBLOCK_STORAGE={
        'STORAGE_CLASS': 'storages.backends.s3boto3.S3Boto3Storage',
        'STORAGE_KWARGS': {
            'default_acl': 'public-read',
            'querystring_expire': 86400
        }
    })
    def test_scorm_storage_custom_storage_with_kwargs_service_variant_lms(self):
        """
        Test if NAU_SCORM_XBLOCK_STORAGE setting is defined we should have a custom storage.
        """
        self.assertEqual(get_storage_kwargs().get('custom_domain'), 'lms.example.com')

    @override_settings(CMS_BASE='studio.example.com', SERVICE_VARIANT="cms", NAU_SCORM_XBLOCK_STORAGE={
        'STORAGE_CLASS': 'storages.backends.s3boto3.S3Boto3Storage',
    })
    def test_scorm_storage_custom_storage_with_kwargs_service_variant_studio(self):
        """
        Test if NAU_SCORM_XBLOCK_STORAGE setting is defined, and we are running the studio instead
        of lms, then we should return the studio domain on the custom domain.
        """
        self.assertEqual(get_storage_kwargs().get('custom_domain'), 'studio.example.com')
