# NAU OpenedX Extensions - Course Certificate

This system enables automatic sending of course certificates to configurable external services via REST APIs.

## Description and Purpose

The certificate dispatch system provides:

- **Automatic sending**: Certificates are sent to external services when generated
- **Flexible configuration**: Multiple services with different endpoints and authentication
- **Data extraction**: Modular system for extracting student, course, and certificate information
- **Transformations**: Support for MD5 hash, base64 encoding
- **Filters**: Ability to filter certificates by organization and course ID.
- **Asynchronous processing**: Background execution using Celery tasks.
- **Test mode (Dry-Run)**: Simulation without actual HTTP request sending.

## Django Settings Configuration Structure

Configuration is defined through the Django setting `NAU_SEND_COURSE_CERTIFICATE_CONFIG`
NOTE: please set NAU_SEND_COURSE_CERTIFICATE_CONFIG setting before running any command.

```python
# Django setting / This is an example
NAU_SEND_COURSE_CERTIFICATE_CONFIG = [
    {
        "service_name": "portugal_digital",
        "endpoint_url": "https://academiaportugaldigital.pt/api/api/Course/FinishedIntegrationNau",
        "endpoint_timeout": 60,
        "auth_token": "XXXXXXXXXXXXXXXXXXXXX",
        "auth_type": "bearer",
        "auth_header": "Authorization",
        "page_size": 100,
        "days": 30,
        "fields": [
            {
                "name": "key",
                "func": "nau_openedx_extensions.coursecertificate.extractors.student_email",
                "trans": "md5"
            },
            {
                "name": "value",
                "func": "nau_openedx_extensions.coursecertificate.extractors.course_id"
            }
        ]
    },
    {
        "service_name": "ina_recap",
        "endpoint_url": "https://ina.gov.pt/api/v1/certificates/recap-integration",
        "endpoint_timeout": 60,
        "auth_token": "XXXXXXXXXXXXXXXXXXXXX",
        "auth_type": "bearer",
        "auth_header": "Authorization",
        "page_size": 500,
        "days": 50,
        "fields": [
            {
                "name": "email",
                "func": "nau_openedx_extensions.coursecertificate.extractors.student_email"
            },
            {
                "name": "username",
                "func": "nau_openedx_extensions.coursecertificate.extractors.student_username"
            },
            {
                "name": "course_id",
                "func": "nau_openedx_extensions.coursecertificate.extractors.course_id"
            },
            {
                "name": "nif",
                "func": "nau_openedx_extensions.coursecertificate.extractors.student_nau_user_extended_model_field",
                "args": "nif"
            }
        ],
        "filters": [
            {
                "func": "nau_openedx_extensions.coursecertificate.filters.certificate_by_course_id_regex",
                "args": "course-v1"
            },
            {
                "func": "nau_openedx_extensions.coursecertificate.filters.certificate_by_org",
                "args": "EduNext"
            }
        ]
    }
]
```


### Configuration Parameters

#### Required Parameters

- **`service_name`**: Service identifier name
- **`endpoint_url`**: External API endpoint URL
- **`fields`**: List of fields to extract and send

#### Optional Parameters

- **`endpoint_timeout`**: HTTP request timeout in seconds (default: `60`)
- **`auth_token`**: Authentication token (default: `none`)
- **`auth_type`**: Authentication type (default: `bearer`)
  - Supported values: `bearer`, `basic`, `api_key`
- **`auth_header`**: Authentication header name (default: `Authorization`)
- **`page_size`**: Page size for batch processing (default: `1000`)
- **`days`**: Days backward to process certificates (default: `7`)
- **`filters`**: List of filters to apply (default: `none`)

#### Field Configuration Parameters

Each field in the `fields` list supports:

**Required:**
- **`name`**: Field name in the payload
- **`func`**: Extractor function path

**Optional:**
- **`args`**: Function arguments (default: `none`)
- **`trans`**: Transformation to apply (default: `none`)
  - Supported values: `md5`, `base64`

#### Filter Configuration Parameters

Each filter in the `filters` list supports:

**Required:**
- **`func`**: Filter function path

**Optional:**
- **`args`**: Filter arguments

## Available Extractors

Extractors are located in [`extractors.py`](extractors.py).

### Student Information Extractors

- **`student_email`**: Student's email address
  ```python
  {
      "name": "email",
      "func": "nau_openedx_extensions.coursecertificate.extractors.student_email"
  }
  # Example output: "john.doe@example.com"
  ```

- **`student_username`**: Student's unique username in the platform
  ```python
  {
      "name": "username",
      "func": "nau_openedx_extensions.coursecertificate.extractors.student_username"
  }
  # Example output: "johndoe123"
  ```

- **`student_name`**: Student's full name (first name + last name)
  ```python
  {
      "name": "full_name",
      "func": "nau_openedx_extensions.coursecertificate.extractors.student_name"
  }
  # Example output: "John Doe"
  ```

- **`student_nau_user_extended_model_field`**: Extract custom fields from NAU's extended user model
  ```python
  # Extract NIF
  {
      "name": "nif",
      "func": "nau_openedx_extensions.coursecertificate.extractors.student_nau_user_extended_model_field",
      "args": "nif"
  }
  # Example output: "123456789"

  # Extract birth date
  {
      "name": "birth_date",
      "func": "nau_openedx_extensions.coursecertificate.extractors.student_nau_user_extended_model_field",
      "args": "birth_date"
  }
  # Example output: "1990-05-15"
  ```

- **`student_enrolled_date`**: Date when the student enrolled in the course
  ```python
  {
      "name": "enrollment_date",
      "func": "nau_openedx_extensions.coursecertificate.extractors.student_enrolled_date"
  }
  # Example output: "2025-07-18T15:09:43.258818+00:00"
  ```

### Certificate Information Extractors

- **`certificate_date`**: Date when the certificate was generated/issued
  ```python
  {
      "name": "completion_date",
      "func": "nau_openedx_extensions.coursecertificate.extractors.certificate_date"
  }
  # Example output: "2025-07-18T15:09:43.258818+00:00"
  ```

- **`certificate_url`**: Direct URL to view or download the certificate
  ```python
  {
      "name": "certificate_link",
      "func": "nau_openedx_extensions.coursecertificate.extractors.certificate_url"
  }
  # Example output: "https://lms.nau.edu.pt/certificates/6bf280f261c54143a313a9d2ccfb1f47"
  ```

### Course Information Extractors

- **`course_id`**: Full course identifier in Open edX format
  ```python
  {
      "name": "course_key",
      "func": "nau_openedx_extensions.coursecertificate.extractors.course_id"
  }
  # Example output: "course-v1:MITx+6.00x+2024_T1"
  ```

- **`course_code`**: Short course code (extracted from the course_id)
  ```python
  {
      "name": "course_code",
      "func": "nau_openedx_extensions.coursecertificate.extractors.course_code"
  }
  # Example output: "6.00x"
  ```

- **`course_name`**: Human-readable course title/name
  ```python
  {
      "name": "course_title",
      "func": "nau_openedx_extensions.coursecertificate.extractors.course_name"
  }
  # Example output: "Introduction to Computer Science and Programming"
  ```

### Field Configuration

```python
"fields": [
    {
        "name": "email",                    # Field name in payload
        "func": "module.path.function",     # Extractor function
        "args": "argument",                 # Function arguments (optional)
        "trans": "md5"                      # Transformation to apply (optional)
    }
]
```

## Transformations

- **`md5`**: MD5 hash of the value
- **`base64`**: Base64 encoding of the value

## Available Filters

Filters are located in [`filters.py`](filters.py):

- **`certificate_by_course_id_regex`**: Filter by regular expression on course ID
- **`certificate_by_org`**: Filter by organization

### Filter Configuration Example

```python
"filters": [
    {
        "func": "nau_openedx_extensions.coursecertificate.filters.certificate_by_org",
        "args": "EduNext"
    }
]
```

## Management Command Usage

The main command is [`send_certificates_by_web_service`](management/commands/send_certificates_by_web_service.py):

### Command Parameters

- **`--service-name`**: Specific service name to process
- **`--certificate-id`**: Specific certificate ID to process
- **`--days`**: Number of days backward to process
- **`--page-size`**: Page size for batch processing
- **`--dry-run`**: Simulate without actual request sending
- **`--async`**: Execute in asynchronous mode using Celery

### Usage Examples

```bash
# Process all configured services
python manage.py lms send_certificates_by_web_service

# Test mode(dry-run) (no real sending)
python manage.py lms send_certificates_by_web_service --dry-run

# Process specific service
python manage.py lms send_certificates_by_web_service --service-name portugal_digital

# Certificates from last 30 days with pages of 50
python manage.py lms send_certificates_by_web_service --days 30 --page-size 50

# Process specific certificate
python manage.py lms send_certificates_by_web_service --certificate-id 12345

# Asynchronous mode using Celery
python manage.py lms send_certificates_by_web_service --async

# Asynchonous dry-run (no real sending)
python manage.py lms send_certificates_by_web_service --async --dry-run

# Parameter combination example
python manage.py lms send_certificates_by_web_service --service-name ina_recap --dry-run --days 7

```

## Dry-Run Mode

The `--dry-run` mode allows:

- Validating configuration without making real requests
- Viewing the payload that would be sent to each service
- Verifying authentication and configured headers
- Testing filters and transformations

Example dry-run output:

```
=== DRY RUN MODE - No actual requests will be sent ===
Loaded configuration from Django settings
Processing 2 service(s)

=== Processing service: portugal_digital ===
Processing certificates from the last 30 days
Page size: 100
Total certificates to process: 1
Processing 1 of 1 certificates (page 1)
[DRY RUN] Would send to https://academiaportugaldigital.pt/api/api/Course/FinishedIntegrationNau
[DRY RUN] Headers would include: bearer authentication
[DRY RUN] Auth header: Authorization
[DRY RUN] Auth token: Configured
[DRY RUN] Request timeout: 60 seconds
[DRY RUN] Payload:
[
  {
    "key": "61c08f07bb9c2c4e4529ee18909d8897",
    "value": "course-v1:test+101+2025"
  }
]
✓ Successfully processed service: portugal_digital.

=== Processing service: ina_recap ===
Processing certificates from the last 50 days
Page size: 500
Total certificates to process: 0
Processing 0 of 0 certificates (page 1)
✓ Successfully processed service: ina_recap.

=== All services processed ===
Successfully processed 2/2 services.
```

## Asynchronous Mode

The `--async` mode uses Celery to:

- Process each service in independent tasks
- Fault isolation between services
- Parallel processing for better performance
- Automatic retries (3 attempts, 60-second intervals)

Example async log:

```
2025-07-17 07:08:31,265 INFO 402 [celery.app.trace] [user None] [ip None] trace.py:128 - Task nau_openedx_extensions.coursecertificate.tasks.process_service_certificates[25e0bfc9-14dc-4cf0-a3bd-c26ee107ea28] succeeded in 0.04806552699301392s: {'task_id': '25e0bfc9-14dc-4cf0-a3bd-c26ee107ea28', 'service_name': 'ina_recap', 'status': 'success'}
[DISPATCH] Task dispatched for service 'portugal_digital'

[DISPATCH] Task Dispatch Summary:
[SUCCESS] Successfully dispatched: 2/2 tasks
   Active tasks:
     • portugal_digital: 89a6c82b-8619-49bc-97d9-660f7731351b
     • ina_recap: 25e0bfc9-14dc-4cf0-a3bd-c26ee107ea28

 Note: Tasks are now running in background. Check Celery logs for execution results.
 ```

### Automatic Event-Based Sending

The system includes a [`handler`](handlers.py) that automatically triggers when a new certificate is generated:

```python
@receiver(CERTIFICATE_CREATED)
def certificate_created_send_to_external_services_handler(...)
```

This ensures certificates are immediately sent to all configured services when created (async).

## Monitoring Failures and Logs

### System Logs

The system records detailed information in Django logs:

- Service processing start and completion
- Number of certificates processed
- Configuration or communication errors
- Retry details in asynchronous mode

### Common Error Logs

- **Configuration errors**: Issues with NAU_SEND_COURSE_CERTIFICATE_CONFIG django setting
- **Connection errors**: Network issues or unavailable endpoints
- **Authentication errors**: Invalid tokens or incorrect auth types
- **Data errors**: Issues extracting fields or applying transformations

The system is designed to be robust and continue processing other services/certificates even if one fails, logging all errors to facilitate debugging.