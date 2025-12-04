from django.conf import settings
from django.utils.module_loading import import_string
from django.core.exceptions import ImproperlyConfigured


def storage_service_bucket():
    """
    Override S3 Bucket settings for video storage service.

    Expects `VIDEO_UPLOAD_PIPELINE` in Django settings to be a dict. Example:

    VIDEO_UPLOAD_PIPELINE = {
        'CONNECTION_CLASS': 'boto.s3.connection.S3Connection',
        'CONNECTION_KWARGS': {
            'aws_access_key_id': 'your_access_key',
            'aws_secret_access_key': 'your_secret_key',
            'host': 's3.your-region.amazonaws.com',  # Change endpoint by setting 'host'
            # Examples of custom endpoints:
            # AWS S3: 'host': 's3.amazonaws.com' or 's3.eu-west-1.amazonaws.com'
            # MinIO: 'host': 'minio.example.com'
            # DigitalOcean Spaces: 'host': 'nyc3.digitaloceanspaces.com'
            # Wasabi: 'host': 's3.wasabisys.com' or 's3.eu-central-1.wasabisys.com'
            
            # Optional boto parameters:
            # 'port': 443,
            # 'is_secure': True,  # Use HTTPS (default: True)
            # 'calling_format': boto.s3.connection.OrdinaryCallingFormat(),
            #   ^ Only needed for S3-compatible services (MinIO, Wasabi, etc.) or 
            #     buckets with dots in the name. Uses path-style URLs instead of 
            #     virtual-hosted style (bucket.s3.com → s3.com/bucket)
        },
        'VEM_S3_BUCKET': 'your_bucket_name',
        'ROOT_PATH': 'upload-videos',
    }

    Note: This uses boto (legacy AWS SDK). The endpoint URL is set via 'host' parameter.
    Do not use boto3 parameters like 'endpoint_url', 'region_name', or 'service_name'.

    The function will:
    - resolve `CONNECTION_CLASS` (dotted path or callable)
    - instantiate it with `CONNECTION_KWARGS`
    - return a bucket-like object for `VEM_S3_BUCKET`
    """
    pipeline = getattr(settings, 'VIDEO_UPLOAD_PIPELINE', {}) or {}
    conn_class = pipeline.get('CONNECTION_CLASS', 'boto.s3.connection.S3Connection')
    conn_kwargs = pipeline.get('CONNECTION_KWARGS', {}) or {}

    # Resolve class if a dotted path was provided
    if isinstance(conn_class, str):
        try:
            cls = import_string(conn_class)
        except ImportError as exc:
            raise ImproperlyConfigured(
                "Could not import connection class '%s': %s" % (conn_class, exc)
            ) from exc
    elif callable(conn_class):
        cls = conn_class
    else:
        raise ImproperlyConfigured(
            "VIDEO_UPLOAD_PIPELINE['CONNECTION_CLASS'] must be a dotted path or a callable/class"
        )

    # Validate credentials for boto S3Connection
    if 'boto' in str(cls.__module__):
        required_keys = ['aws_access_key_id', 'aws_secret_access_key']
        missing = [k for k in required_keys if not conn_kwargs.get(k)]
        if missing:
            raise ImproperlyConfigured(
                "VIDEO_UPLOAD_PIPELINE['CONNECTION_KWARGS'] missing required keys for boto: %s. "
                "Check your settings." % missing
            )

    try:
        conn = cls(**conn_kwargs)
    except TypeError as exc:
        raise ImproperlyConfigured(
            "Failed to instantiate connection '%s': %s" % (cls, exc)
        ) from exc
    except Exception as exc:
        # Catch authentication errors and provide helpful message
        raise ImproperlyConfigured(
            "Failed to create connection with class '%s': %s. "
            "Verify your CONNECTION_KWARGS credentials are correct." % (cls.__name__, exc)
        ) from exc

    bucket_name = pipeline.get('VEM_S3_BUCKET')
    if not bucket_name:
        raise ImproperlyConfigured("VIDEO_UPLOAD_PIPELINE['VEM_S3_BUCKET'] is required")

    # Get bucket using boto's get_bucket method
    # validate=False avoids extra permissions check (matches edx-platform behavior)
    if hasattr(conn, 'get_bucket'):
        return conn.get_bucket(bucket_name, validate=False)
    
    # Fallback for non-standard connection objects
    raise ImproperlyConfigured(
        "Connection class '%s' does not have 'get_bucket' method. "
        "Expected boto.s3.connection.S3Connection or compatible class." % cls.__name__
    )
