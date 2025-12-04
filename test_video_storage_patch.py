#!/usr/bin/env python
"""
Test script to verify that storage_service_bucket has been successfully patched.

Usage:
    # From edx-platform directory with proper environment:
    python /path/to/this/script.py

    # Or via docker:
    docker-compose exec cms python /openedx/nau-openedx-extensions/test_video_storage_patch.py
"""
import sys


def test_patch():
    """Test if storage_service_bucket has been patched"""
    print("=" * 70)
    print("Testing NAU storage_service_bucket patch")
    print("=" * 70)
    
    # Step 1: Import both modules
    print("\n1. Importing modules...")
    try:
        from cms.djangoapps.contentstore import video_storage_handlers as edx_handlers
        print("   ✓ Imported edx video_storage_handlers")
    except ImportError as e:
        print(f"   ✗ Failed to import edx module: {e}")
        return False
    
    try:
        from nau_openedx_extensions.studio.contentstore import video_storage_handlers as nau_handlers
        print("   ✓ Imported NAU video_storage_handlers")
    except ImportError as e:
        print(f"   ✗ Failed to import NAU module: {e}")
        return False
    
    # Step 2: Trigger the middleware patch manually
    print("\n2. Triggering middleware patch...")
    try:
        from nau_openedx_extensions.studio.middleware import VideoStorageHandlerPatchMiddleware
        middleware = VideoStorageHandlerPatchMiddleware(lambda r: None)
        middleware._apply_patch()
        print("   ✓ Middleware patch triggered")
    except Exception as e:
        print(f"   ⚠ Could not trigger middleware (may already be patched): {e}")
    
    # Step 3: Check if functions are the same object
    print("\n3. Checking if patch was applied...")
    is_patched = edx_handlers.storage_service_bucket is nau_handlers.storage_service_bucket
    
    if is_patched:
        print("   ✓ PATCH SUCCESSFUL: Functions are identical")
    else:
        print("   ✗ PATCH FAILED: Functions are different")
    
    # Step 4: Show function details
    print("\n4. Function details:")
    print(f"   EDX function module: {edx_handlers.storage_service_bucket.__module__}")
    print(f"   NAU function module: {nau_handlers.storage_service_bucket.__module__}")
    print(f"   EDX function object: {id(edx_handlers.storage_service_bucket)}")
    print(f"   NAU function object: {id(nau_handlers.storage_service_bucket)}")
    
    # Step 5: Check function source
    print("\n5. Function implementation:")
    import inspect
    try:
        source = inspect.getsource(edx_handlers.storage_service_bucket)
        if 'import_string' in source and 'ImproperlyConfigured' in source:
            print("   ✓ Using NAU custom implementation (with import_string)")
        elif 'S3Connection' in source and 'AWS_ACCESS_KEY_ID' in source:
            print("   ✗ Using original edx implementation")
        else:
            print("   ? Unknown implementation")
        print(f"\n   First 5 lines of code:")
        for i, line in enumerate(source.split('\n')[:5], 1):
            print(f"     {i}: {line}")
    except Exception as e:
        print(f"   ⚠ Could not retrieve source: {e}")
    
    # Final result
    print("\n" + "=" * 70)
    if is_patched:
        print("✓ TEST PASSED: storage_service_bucket is successfully patched!")
        print("=" * 70)
        return True
    else:
        print("✗ TEST FAILED: storage_service_bucket is NOT patched")
        print("=" * 70)
        return False


if __name__ == "__main__":
    # Setup Django if not already done
    try:
        import django
        from django.conf import settings
        if not settings.configured:
            django.setup()
    except Exception as e:
        print(f"Warning: Django setup issue: {e}")
        print("Attempting to continue anyway...\n")
    
    success = test_patch()
    sys.exit(0 if success else 1)
