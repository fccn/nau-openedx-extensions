# Custom ACE Email Channel for Bulk Email Delivery

## Overview

This module provides a custom ACE (Advanced Communication Engine) email channel that allows Open edX to send emails through a separate SMTP relay dedicated to bulk email delivery.

This is particularly useful for organizations that:
- Need to comply with Portuguese public contracting requirements
- Use a separate email infrastructure for transactional vs. marketing emails
- Want to avoid third-party email delivery services (Sailthru, Braze, etc.)
- Require flexible SMTP relay configuration


## Key Features

✅ **Separate SMTP Relay** - Configure different host for bulk emails
✅ **Backward Compatible** - Defaults to standard EMAIL_* if not configured
✅ **Flexible Configuration** - Support for TLS, SSL, ports, timeouts, credentials
✅ **Robust Error Handling** - Connection errors logged and propagated
✅ **Plugin Architecture** - Follows edX platform patterns
✅ **Comprehensive Tests** - Full unit test suite included
✅ **No Dependencies** - Uses only Django built-in email backend

## Quick Start (5 minutes)

### 1. Install the Package
```bash
cd /path/to/nau-openedx-extensions
pip install -e .
```

**Important:** After installation, you must restart your edX services for the channel entry point to be registered. The package registers the channel via the `openedx.ace.channel` entry point in setup.py.

### 2. Configure Django Settings

Add these settings to your Open edX environment configuration:

```python
# Bulk email SMTP configuration
EMAIL_HOST_FOR_BULK = 'bulk-smtp.your-domain.com'
EMAIL_PORT_FOR_BULK = 587
EMAIL_HOST_USER_FOR_BULK = 'bulk@your-domain.com'
EMAIL_HOST_PASSWORD_FOR_BULK = 'your-password'
EMAIL_USE_TLS_FOR_BULK = True
EMAIL_USE_SSL_FOR_BULK = False
EMAIL_TIMEOUT_FOR_BULK = 10
```

### 3. Enable the Channel in ACE

```python
ACE_ENABLED_CHANNELS = [
    'django_email_bulk',  # Entry point name from setup.py
]
```

### 4. Restart edX Services
```bash
# For devstack
make dev.restart

# For production, restart your edX app and celery workers
```

### 5. Test Email Delivery

```bash
python manage.py shell
```

```python
from edx_ace import ace
from edx_ace.message import Message

message = Message(
    from_address='noreply@example.com',
    to_address='test@example.com',
    subject='Test Email',
    template_name='welcome',
    context={}
)
ace.send(message)
print("✓ Email sent!")
```

## Architecture

### Components

1. **DjangoEmailBulkChannel** (`django_email_bulk.py`)
   - Extends `edx_ace.channel.django_email.DjangoEmailChannel`
   - Overrides the `deliver()` method to use bulk email configuration
   - Creates custom Django email connections with separate SMTP settings

2. **Settings Configuration** (`settings/settings.py`)
   - Defines new bulk email settings with intelligent fallback to standard EMAIL_* settings
   - No additional dependencies beyond Django

3. **App Configuration** (`apps.py`)
   - Registers the email channel as a Django app
   - Integrates plugin settings with edX platform

### How It Works

```
User requests email delivery via ACE
    ↓
ACE routes to enabled channels
    ↓
DjangoEmailBulkChannel.deliver() is called
    ↓
_get_bulk_connection() creates custom email connection
  - Uses EMAIL_HOST_FOR_BULK settings (not default EMAIL_HOST)
  - Falls back to standard EMAIL_* if bulk settings not configured
    ↓
Connection sent to parent deliver() method
    ↓
Email sent via bulk SMTP relay
    ↓
Connection closed, success logged
```

## Configuration Reference

### Django Settings

All settings are optional and fall back to standard Django EMAIL_* settings if not specified:

| Setting | Type | Default | Purpose |
|---------|------|---------|---------|
| `EMAIL_HOST_FOR_BULK` | str | EMAIL_HOST | SMTP hostname for bulk emails |
| `EMAIL_PORT_FOR_BULK` | int | EMAIL_PORT | SMTP port (usually 25, 587, or 465) |
| `EMAIL_HOST_USER_FOR_BULK` | str | EMAIL_HOST_USER | SMTP username |
| `EMAIL_HOST_PASSWORD_FOR_BULK` | str | EMAIL_HOST_PASSWORD | SMTP password |
| `EMAIL_USE_TLS_FOR_BULK` | bool | EMAIL_USE_TLS | Use TLS encryption |
| `EMAIL_USE_SSL_FOR_BULK` | bool | EMAIL_USE_SSL | Use SSL encryption (don't combine with TLS) |
| `EMAIL_TIMEOUT_FOR_BULK` | int | EMAIL_TIMEOUT or 10 | Connection timeout in seconds |

### ACE Configuration

Configure the ACE enabled channels to use the new bulk channel:

```python
ACE_ENABLED_CHANNELS = [
    'django_email_bulk',  # Note: use the entry point name, not the full module path
]
```

**Important Notes:** 
- Use the **entry point name** `django_email_bulk` (registered in setup.py), NOT the full module path
- Only include the bulk channel if you want all ACE emails to use the bulk SMTP relay
- If you need other ACE channels (Sailthru, Braze, etc.), add them to the list
- The channel is registered via the `openedx.ace.channel` entry point in setup.py

## Usage Examples

### Sending a Single Email

```python
from edx_ace import ace
from edx_ace.message import Message

message = Message(
    from_address='noreply@example.com',
    to_address='student@example.com',
    subject='Welcome!',
    template_name='welcome',
    context={'name': 'John Doe'}
)

# Automatically uses DjangoEmailBulkChannel
ace.send(message)
```

### Sending Bulk Emails

```python
from edx_ace import ace
from edx_ace.message import Message

users = [user1, user2, user3, ...]

for user in users:
    message = Message(
        from_address='noreply@example.com',
        to_address=user.email,
        subject='Course Announcement',
        template_name='announcement',
        context={'user': user}
    )
    ace.send(message)  # Uses bulk SMTP relay
```

## Testing

### Running Tests

```bash
# Run all email channel tests
python manage.py test nau_openedx_extensions.email_channel

# Run with verbose output
python manage.py test nau_openedx_extensions.email_channel -v 2

# Run specific test class
python manage.py test nau_openedx_extensions.email_channel.tests.test_django_email_bulk.DjangoEmailBulkChannelTestCase
```

### Test Coverage

The test suite validates:
- Channel type validation
- Custom settings override
- Fallback to default settings
- Connection parameter passing
- Error handling and logging
- Parent method invocation

## Debugging

### Test Connection

```bash
python manage.py shell
```

```python
from nau_openedx_extensions.email_channel.django_email_bulk import DjangoEmailBulkChannel

try:
    connection = DjangoEmailBulkChannel._get_bulk_connection()
    print("✓ Connection successful!")
except Exception as e:
    print(f"✗ Connection failed: {e}")
```

## Troubleshooting

### Issue: "Connection refused"

- Verify `EMAIL_HOST_FOR_BULK` is accessible: `telnet EMAIL_HOST_FOR_BULK EMAIL_PORT_FOR_BULK`
- Check firewall allows outbound connections
- Confirm SMTP server is running

### Issue: "Authentication failed"

- Verify `EMAIL_HOST_USER_FOR_BULK` and `EMAIL_HOST_PASSWORD_FOR_BULK`
- Check bulk SMTP account has send permissions
- Ensure special characters in password are properly escaped

### Issue: "Emails not sent"

- Verify `ACE_ENABLED_CHANNELS` includes the bulk channel
- Check Django logs for errors
- Ensure edX services restarted after config changes
- Verify the bulk SMTP relay is operational

## Integration with edX Platform

### Multi-Channel Setup

If you need multiple ACE channels:

```python
ACE_ENABLED_CHANNELS = [
    'django_email_bulk',  # NAU bulk email channel (entry point name)
    'sailthru',           # Optional: Sailthru
    'braze',              # Optional: Braze
]
```

### Performance Considerations

- **Connection Overhead**: New connection created per email delivery
- **Bulk Limits**: Check your SMTP provider's rate limits and adjust `EMAIL_TIMEOUT_FOR_BULK` based on network latency
- **Batch Sending**: ACE handles message batching; this channel processes one message at a time

## References

- [edX ACE Documentation](https://github.com/openedx/edx-ace)
- [Django Email Backend Documentation](https://docs.djangoproject.com/en/stable/topics/email/)
- [edX Platform Plugin Guide](https://github.com/edx/edx-platform/blob/master/openedx/core/djangoapps/plugins/README.rst)
