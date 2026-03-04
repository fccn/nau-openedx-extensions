# SSO Partner Enrollment Filter

## Overview

The `FilterSSOPartnerAccountLink` is an Open edX enrollment filter that validates whether users attempting to enroll in courses have:

1. **Completed SSO account linking** - User has a `SSOPartnerIntegration` record linking them to a partner account
2. **Partner has course access** - The partner's `base_security_scope` grants access to the course being enrolled in

This filter ensures that only users with valid partner account links can enroll in courses authorized for that partner.

## Implementation Details

**File:** [`nau_openedx_extensions/partner_integration/course_filters.py`](./course_filters.py)

**Hook:** `org.openedx.learning.course.enrollment.started.v1`

The filter integrates with the Open edX Filter Framework using the `PipelineStep` base class and prevents enrollment by raising `CourseEnrollmentStarted.PreventEnrollment` with Portuguese error messages.

## How It Works

### Validation Flow

```
User attempts enrollment
    ↓
Does user have SSOPartnerIntegration? 
    ├─ NO → Raise error: "Account link not completed"
    └─ YES → Continue
            ↓
            Does partner have base_security_scope?
                ├─ NO → Raise error: "Partner has no access configured"
                └─ YES → Continue
                        ↓
                        Is course allowed by partner's scope?
                            ├─ NO → Raise error: "Partner doesn't have permission for this course"
                            └─ YES → Enrollment allowed ✓
```

### Security Scope Matching

The filter uses Django ORM lookup syntax to match courses against the partner's `base_security_scope`:

```python
base_security_scope = {"org": "nau"}  # Allows all courses in "nau" org
base_security_scope = {"org__in": ["nau", "fccn"]}  # Allows multiple orgs
base_security_scope = {"id__in": ["course-v1:org+ABC+2024"]}  # Specific courses
base_security_scope = {"display_name__icontains": "python"}  # Name-based
```

The filter applies these filters to `CourseOverview` to determine access.

## Configuration

### Add to OPEN_EDX_FILTERS_CONFIG

In your Django settings file (`lms.env.yml` or equivalent), add the filter to the enrollment pipeline:

```yaml
OPEN_EDX_FILTERS_CONFIG:
  org.openedx.learning.course.enrollment.started.v1:
    fail_silently: false
    pipeline:
      - "nau_openedx_extensions.filters.pipeline.FilterEnrollmentByDomain"
      - "nau_openedx_extensions.filters.pipeline.FilterEnrollmentRequireNIF"
      - "nau_openedx_extensions.partner_integration.course_filters.FilterSSOPartnerAccountLink"
```

Or in JSON format:

```json
{
  "OPEN_EDX_FILTERS_CONFIG": {
    "org.openedx.learning.course.enrollment.started.v1": {
      "fail_silently": false,
      "pipeline": [
        "nau_openedx_extensions.filters.pipeline.FilterEnrollmentByDomain",
        "nau_openedx_extensions.filters.pipeline.FilterEnrollmentRequireNIF",
        "nau_openedx_extensions.partner_integration.course_filters.FilterSSOPartnerAccountLink"
      ]
    }
  }
}
```

### Set fail_silently

- **`fail_silently: false`** (Recommended) - Any error in the filter chain blocks enrollment
- **`fail_silently: true`** - Errors are logged but don't block enrollment

## Error Messages

The filter provides clear Portuguese (pt-PT) error messages:

### No SSO Integration
> "A ligação de conta com a plataforma do parceiro não foi concluída. Por favor, complete o processo de ligação de conta antes de se inscrever."

Translation: "The account link with the partner platform has not been completed. Please complete the account linking process before enrolling."

### No Security Scope Configured
> "O parceiro de integração não tem acesso configurado para nenhum curso. Por favor, contacte o suporte."

Translation: "The integration partner has no access configured for any course. Please contact support."

### Course Not Allowed
> "O parceiro de integração não tem permissão para inscrever utilizadores neste curso. Por favor, contacte o suporte."

Translation: "The integration partner does not have permission to enroll users in this course. Please contact support."

## Database Models

The filter uses these related models:

### SSOPartnerIntegration
Links a local user to a partner account:
```python
{
    "user": User,  # The local edX user
    "partner_client": PartnerAPIClient,  # The partner
    "external_user_id": "str"  # Partner's user identifier
}
```

### PartnerAPIClient
Represents a partner client with access control:
```python
{
    "name": "str",  # Partner name
    "client_id": "UUID",
    "query_security_scope": {
        "base_security_scope": {
            # Django ORM filters against CourseOverview
        },
        "base_certificates_scope": {
            # Django ORM filters against GeneratedCertificate
        }
    }
}
```

## Testing

Comprehensive tests are provided in [`tests/test_course_filters.py`](./tests/test_course_filters.py).

### Test Coverage

1. ✅ Valid SSO record with allowed course
2. ✅ User has no SSO record → error
3. ✅ Partner has no security scope → error
4. ✅ Course not in partner's scope → error
5. ✅ Multiple orgs in scope
6. ✅ Specific course IDs in scope
7. ✅ Error handling and logging

### Running Tests

```bash
# Run all filter tests
cd /openedx/nau-openedx-extensions
python -m pytest nau_openedx_extensions/partner_integration/tests/test_course_filters.py -v

# Run specific test
python -m pytest nau_openedx_extensions/partner_integration/tests/test_course_filters.py::FilterSSOPartnerAccountLinkTests::test_filter_passes_when_user_has_valid_sso_record_and_course_allowed -v
```

## Logging

The filter logs important events for observability:

```python
# Info: Successful validation
"User 123 (john.doe) validated for enrollment in course-v1:nau+ABC+2024 via partner NAU"

# Warning: No SSO record
"User 123 (john.doe) has no SSO partner integration record"

# Warning: No access
"Partner NAU does not have access to course course-v1:different+XYZ+2024"

# Error: Configuration/database issues
"Error validating course course-v1:nau+ABC+2024 against security scope: ..."
```

All logs use the logger: `nau_openedx_extensions.partner_integration.course_filters`

## Integration with SSO Flow

This filter works alongside the SSO integration module:

1. **SSO link creation** - `CustomAuthorizationView` creates `SSOPartnerIntegration` records
2. **Enrollment validation** - This filter validates those records during enrollment
3. **Access control** - Only allows enrollment if partner has been granted access to the course

## Performance Considerations

The filter runs Django ORM queries to:
1. Lookup `SSOPartnerIntegration` by user (indexed query)
2. Check course access using `base_security_scope` filters

Both operations are efficient and use database indexes on:
- `SSOPartnerIntegration.user` (OneToOne)
- `CourseOverview.org`, `CourseOverview.id` (indexed fields)

## Backwards Compatibility

The filter is **opt-in** and only affects enrollment when:
1. The filter is added to the `OPEN_EDX_FILTERS_CONFIG`
2. The user has an `SSOPartnerIntegration` record

Existing users without SSO integration records are not affected.

## Troubleshooting

### Filter Not Running

Check that:
1. Filter is in `OPEN_EDX_FILTERS_CONFIG` pipeline
2. `fail_silently` is set appropriately
3. Settings have been reloaded (restart LMS/CMS)

### All Users Blocked

Check:
1. User has `SSOPartnerIntegration` record (Django admin)
2. Partner's `base_security_scope` is configured
3. Course org/ID matches security scope

### Database Errors

Check:
1. `SSOPartnerIntegration` table exists (run migrations)
2. User and partner client records exist
3. Database connection is working

## See Also

- [Partner Integration Module README](./README.md)
- [SSOPartnerIntegration Model](./models.py)
- [PartnerAPIClient Configuration](./README.md#configuring-base_security_scope-and-base_certificates_scope)
- [Open edX Filters Documentation](https://github.com/openedx/openedx-filters)
