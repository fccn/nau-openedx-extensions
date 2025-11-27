# Partner Integration Module

The `partner_integration` module provides secure, scalable REST APIs for partner clients to interact with LMS data. It leverages the **Facade pattern** to encapsulate data extraction logic while enforcing strict security and validation rules.

## Features

### REST API Endpoints

1. **Authentication**
   - Endpoint: `/auth-token/`
   - Returns a JWT token for partner clients.
   - Validates credentials and client status.

2. **Certificates Export**
   - Endpoint: `/data-extractor/certificates/`
   - Fetches certificates filtered by:
     - Course IDs
     - User emails
     - NIFs (tax ID)
     - Certificate creation dates
   - Enforces **base security scope** to limit access to partner’s authorized courses.
   - Annotates results with course info and enrollment metadata.

3. **Enroll Users**
   - Endpoint: `/enroll-user/`
   - Enrolls users in courses by email or NIF.
   - Checks partner permissions and course ownership.
   - Returns detailed enrollment objects with related metadata.

4. **Student Progress Export**
   - Fetches student progress for specific courses.
   - Returns:
     - Completion summary
     - Course grades
     - Section-level scores
   - Enforces partner’s security scope on accessible courses.

## Business Logic

### Security and Validation

- **Base Security Scope**
  - Each partner is assigned a `base_security_scope` that defines authorized courses.
  - `CertificateExportFacade`, `EnrollmentFacade`, and `StudentProgressExportFacade` apply this filter to ensure restricted access.

- **Certificate and Enrollment Filtering**
  - Additional filters can be applied by clients:
    - Emails, NIFs, course IDs
    - Date ranges for enrollments or certificate creation
  - Invalid or unauthorized fields are removed before query execution.

- **Error Handling**
  - Custom exceptions:
    - `PartnerIntegrationInternalErrorException`
    - `PartnerIntegrationInvalidDataProvidedException`
    - `PartnerIntegrationCourseOwnerException`
  - All facade methods wrap database access in `try/except` to log errors and prevent sensitive data leaks.

## Configuring `base_security_scope` and `base_certificates_scope`

Partner clients can define **access boundaries** using two JSON-based scopes stored inside the `query_security_scope` field of `PartnerAPIClient`.

These scopes determine **what data a partner is allowed to request**, and are enforced transparently by the facades.

- `base_security_scope` → filters **courses** (`CourseOverview`)
- `base_certificates_scope` → filters **certificates** (`GeneratedCertificate`)

Both scopes use **Django ORM lookup syntax**, and both are validated upon saving the client.

### 1. `base_security_scope` — Course Access Rules

This scope defines the **base set of courses** that a partner is allowed to access anywhere in the API.

It maps directly to fields available on the `CourseOverview` model and supports standard Django lookups such as:

- `__exact`
- `__in`
- `__icontains`
- `__startswith`
- `__gte` / `__lte`
- Nested lookups for related objects (if present)

### Requirements

- The scope **must not be empty**.
- It must include **at least one field that starts with `"org"`**, because the organization is the minimum necessary boundary for security and scope definition.

### Common Fields (CourseOverview)

| Field | Description |
|-------|-------------|
| `org` | The course’s owning organization |
| `id` | course key `course-v1:org+course+run` or only `course` |
| `display_name` | Human-readable course title |
| `start` / `end` | Course date limits |
| `course` | Course code |
| `run` | Run identifier |

### Examples

#### Allow only one organization
```json
{
  "org__in": ["nau", "FCCN"]
}
```

### Allow multiple specific courses
```json
{
  "id__in": [
    "course-v1:nau+ABC101+2024",
    "course-v1:nau+DEF202+2024"
  ]
}
```

### Allow all courses with "analytics" in the title
```json
{
  "display_name__icontains": "analytics"
}
```

### How Security Scope Is Enforced
Every course-based operation includes:

```python
CourseOverview.objects.filter(**client.query_security_scope["base_security_scope"])
```

If a partner attempts to access a course outside this filter, the system raises:

```python
PartnerCourseOwnerException
```

### 2. `base_certificates_scope` — Certificate Access Rules

The `base_certificates_scope` defines which **certificates** a partner is allowed to access.

This scope is applied **after** the course security scope (`base_security_scope`) and maps directly to fields in the **`GeneratedCertificate`** model. It supports all standard **Django ORM lookups**, including nested lookups for related user data.

### Common Fields (GeneratedCertificate)

| Field | Description |
|-------|-------------|
| `course_id` | Course key associated with the certificate |
| `user__email` | User’s email |
| `user__profile__nif` | NIF (tax ID) from the user profile |
| `status` | Certificate status (generated, error, etc.) |
| `created_date` | Date the certificate was generated |

### Examples

#### Limit certificates to users with a `.gov` email
```json
{
  "user__email__icontains": ".gov"
}
``` 

#### Only certificates created after 1 Jan 2024
```json 
{
  "created_date__gte": "2024-01-01"
}
```

#### Restrict to specific course IDs
```json
{
  "course_id__in": [
    "course-v1:nau+ABC101+2024",
    "course-v1:nau+XYZ300+2024"
  ]
}
```

### Enforcement Logic

Internally:

```python
GeneratedCertificate.objects.filter(**base_certificates_scope)
```

### Validation Rules for Both Scopes

When a `PartnerAPIClient` is saved, both `base_security_scope` and `base_certificates_scope` undergo strict validation:

Fields must exist on the target model (`CourseOverview` or `GeneratedCertificate`)

- Invalid fields are silently removed
- Invalid lookup expressions (e.g., __abc) are removed
- Fields with None values are removed to avoid broken queries
- Unknown or unsupported fields are ignored safely
- All removals are logged for observability

This guarantees that scopes never break API execution, even if misconfigured.

Example — Invalid Rules Automatically Removed

Given:
```json
{
  "org__startswith": null,
  "unknown_field": "test",
  "created_date__abc": "invalid"
}
```

The system reduces it to:
```json
{}
```

And logs warnings indicating why each field was discarded.

### Complete Example: Combined Scopes

A partner with the following restrictions:

- Can only access courses from the NAU organization
- Can only see certificates created within the last 6 months
- Can only access certificates for users who have a NIF

Would have this configuration:

```json
{
  "base_security_scope": {
    "org__exact": "nau"
  },
  "base_certificates_scope": {
    "created_date__gte": "2024-06-01",
    "user_nauuserextendedmodel__nif__isnull": false,
    "user_nauuserextendedmodel__cc_nif__isnull": false
  }
}
```

This ensures the partner:

- Only queries allowed courses
- Only sees certificates meeting their allowed criteria
- Never receives data outside their authorized scope

### Facade Pattern Implementation

The module uses the **Facade design pattern** to simplify access to complex LMS subsystems.

#### DataExtractorFacade
- Base class for data extraction.
- Applies **base security scope** filtering.

#### CertificateExportFacade
- Retrieves certificates for partner clients.
- Annotates certificates with:
  - Course metadata
  - Enrollment data
- Applies filters for courses, emails, NIFs, and dates.

#### EnrollmentFacade
- Retrieves and manages user enrollments.
- Supports enrolling users by email/NIF.
- Annotates enrollments with related certificates.

#### StudentProgressExportFacade
- Retrieves student progress:
  - Grades
  - Completion summary
  - Section scores
- Validates course access according to the partner's security scope.

## Validations

1. **Partner Client Validation**
   - Only active clients can access APIs.
   - Clients cannot access courses outside their `base_security_scope` `org` paramater.

2. **Scope Field Validation**
   - Only valid fields allowed in `base_security_scope` and `base_certificates_scope`.
   - Invalid fields are removed automatically.
   - `None` values are removed from queries.

3. **Data Filtering**
   - Certificates and enrollments filtered by valid fields only.
   - Courses filtered by `org`, course ID, and optional fields.
   - Emails and NIFs validated before querying the database.

## Logging

- All facade operations log important actions and exceptions.
- Provides visibility into:
  - Query execution
  - Errors
  - Unauthorized access attempts

## Summary

The `partner_integration` module provides:

- **Secure REST APIs with JWT** for certificates, enrollments, and student progress.
- **Facade-based architecture** for clean, maintainable data extraction logic.
- **Strict validation and filtering** to enforce partner-specific access control.
- **Comprehensive logging and error handling** to ensure system reliability.
- **Test coverage** for all critical use cases.

This module lays the foundation for future partner integrations and ensures compliance with organizational security policies.
