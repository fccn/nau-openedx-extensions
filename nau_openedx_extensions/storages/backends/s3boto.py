from storages.backends.s3boto import S3BotoStorage
from storages.utils import setting


class NAUS3BotoStorage(S3BotoStorage):
    """
    Custom NAU S3 boto implementation that allows generate presigned urls to a custom domain.
    It uses the `nau_custom_endpoint_url` key on storage initialization kwargs to replace the
    url protocol and domain.
    """

    nau_custom_endpoint_url = setting('NAU_CUSTOM_ENDPOINT_URL')

    def __init__(self, acl=None, bucket=None, **settings):
        super().__init__(acl, bucket, **settings)

    def url(self, name, headers=None, response_headers=None, expire=None):
        url = super().url(name, headers, response_headers, expire)

        if self.nau_custom_endpoint_url:
            # Remove the bucket name from the url
            url = url.replace("/" + self.bucket_name + "/", "/")

            import re
            url_path_and_attributes = re.search("/", url[9:]).start() +9
            url = self.nau_custom_endpoint_url + url[url_path_and_attributes:]

        return url
