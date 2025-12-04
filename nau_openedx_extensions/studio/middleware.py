"""
Middleware to apply monkey patches after Django is fully initialized.

This avoids circular import issues that can occur during app.ready().
"""
import logging

logger = logging.getLogger(__name__)


class VideoStorageHandlerPatchMiddleware:
    """
    Middleware that patches video_storage_handlers on first request.
    
    This is needed because importing cms.djangoapps.contentstore.video_storage_handlers
    during AppConfig.ready() causes circular import errors.
    """
    
    _patched = False
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Apply patch on first request only
        if not VideoStorageHandlerPatchMiddleware._patched:
            self._apply_patch()
            VideoStorageHandlerPatchMiddleware._patched = True
        
        return self.get_response(request)
    
    def _apply_patch(self):
        """Apply the storage_service_bucket override"""
        try:
            from nau_openedx_extensions.studio.contentstore.video_storage_handlers import storage_service_bucket
            from cms.djangoapps.contentstore import video_storage_handlers
            
            video_storage_handlers.storage_service_bucket = storage_service_bucket
            logger.info("NAU: Successfully patched storage_service_bucket via middleware")
            print("NAU: Successfully patched storage_service_bucket via middleware")  # Also print for visibility
        except ImportError as e:
            logger.warning("NAU: Could not patch storage_service_bucket: %s", e)
            print(f"NAU: Warning - could not patch storage_service_bucket: {e}")
        except Exception as e:
            logger.exception("NAU: Unexpected error patching storage_service_bucket")
            print(f"NAU: Error - unexpected issue patching storage_service_bucket: {e}")
