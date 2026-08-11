# Partner Integration Module

The `partner_integration` module provides secure, scalable REST APIs for partner clients to interact with LMS data. It leverages the **Facade pattern** to encapsulate data extraction logic while enforcing strict security and validation rules. It also includes the SSO implementation, where it has the possibility of linking partner's users's account.

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

## SSO integration

It classifies mainly in three states, in quick words:

- A user that comes from the partner platform and has no SSO register. It redirects to login page, and the register is created for the user that authenticates.
- A user that comes from the partner platform and has SSO register. It redicts to the `redirect_uri` in the url.
- A user that comes from the partner platform and has SSO register, but with a different `external_user_id`. The flow is refused with the `sso_link_conflict` error, and the existing register is left untouched. Changing the `external_user_id` of a register is done through the SSO management endpoint.

### Important
- All the flow respects our instance as the SSO authentication server.
- All the features applied were created respecting the current available resources from Open Edx upstream, that is, it does not install new packages, nor uses new resources, it only implements the platform resources in a way that meets the SSO requirements. 

## The key concepts

#### Partner JWT
- Issued by the partner
- Validated by ClientJWTAuthentication
- Identifies which partner client is calling us

#### external_user_id
- The user identifier on the partner system
- Stored locally in SSOPartnerIntegration
- Used as the primary lookup key during SSO

#### SSOPartnerIntegration
- This model represents “this local user is linked to this partner user”. In other words "User X in our system corresponds to external user Y from partner Z"

## How it works

### `Applications`

The Open Edx Applications model, the one that manages the SSO applications. In this model we creates an application for each partner who wants to use our SSO integration.

### `PartnerAPIClient`

The model that represents each partner client that consumes our partner integration solutions (SSO and webservice).

### URL format
```bash
http://lms.local.nau.fccn.pt/nau-openedx-extensions/partner-integration/sso/authorize/
?client_id=wFkgI0PDXXSYkrLwC4I3pe4t7lhwmWbjScJUULW3
&redirect_uri=https://example.com
&jwt_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiMiIsInVzZXJuYW1lIjoiZ3RyYWluaW5nIiwiZXhwIjoxNzY3MDM3NzM5LCJpYXQiOjE3NjcwMzA1MzksImlzcyI6Imh0dHA6Ly9sbXMubG9jYWwubmF1LmZjY24ucHQvb2F1dGgyIiwiYXVkIjoib3BlbmVkeCJ9.5uf1q78l9jdKJ9n-Wu94IYPgtCRQknTCacHtjeGI0m0
&external_user_id=123456789
```
#### client_id
Setup via `Applications` model, the client id of an application register. 

#### redirect_uri
Dynamically setup, the partner changes the `redirect_uri` in order to redirect the user to the corresponding course he must to go.

#### jwt_token
Obtained via webservice authentication, the `PartnerAPIClient` uses the authentication endpoint to obtain a valid jwt token.
`https://lms.nau.edu.pt/nau-openedx-extensions/partner-integration/auth-token/`

#### external_user_id
Dynamically setup, this is the information that identifies the user in the partner's platform, e.g. email, NIF, user_id or username. The user on our platform has no possibility to edit his register.

### `SSOPartnerIntegrations`

The model responsible for managing the SSO registers. Visible via Django admin.

## The entry point: `CustomAuthorizationView`

This view overrides the OAuth2 authorization process.

### Two important overridden methods
`dispatch()` → decision & authentication
`get()` → final redirect handling

### Methods descriptions:
`dispatch()`: decides who the user is and what to do
`get()`: decides where to send the user
`handle_sso_registration()`: creates the user SSO register, and refuses to reassign an existing one.
`handle_sso_link_conflict()`: redirects back to the partner with the `sso_link_conflict` error.


## Flow description
1. Partner calls the endpoint

The partner redirects the user’s browser to this endpoint with:
- client_id
- jwt_token
- external_user_id

2. Partner and application validation

Inside `dispatch()`:
- The JWT is validated
- If invalid → redirect to default partner URL: 
    - The OAuth Application is fetched using `client_id`
    - If it doesn’t exist → redirect to default partner URL settings (e.g. NAU home page) 

This ensures only known and active partners can use the flow.

## The three scenarios

### Scenario 1: User has no SSO registration
No `SSOPartnerIntegration` exists for the given `external_user_id`:

#### What we do:
- Redirect the user to the login page
- After login, `handle_sso_registration()` is called
- A new `SSOPartnerIntegration` is created
- links the local user
- stores the `external_user_id`
- User is redirected back to the partner callback

#### Outcome:
First-time SSO users get properly linked. From now on, future logins are seamless. This is first-time partner access.

### Scenario 2: User already has an SSO registration

#### A `SSOPartnerIntegration` exists for:
- this `partner_client`
- this `external_user_id`

#### What we do:
- Authenticate the request
- If the user is not logged in, login programmatically
- If a session of a **different** user is open in the browser, that session is dropped and the owner of the register is logged in instead
- Continue the OAuth flow and redirect

#### Outcome:
- User is transparently logged in
- No screens, no interaction
- Clean SSO experience

This is the success path.

### Scenario 3: User exists, but `external_user_id` has changed

The user already has an SSO record for this partner client, but the incoming `external_user_id` is different from the stored one.

#### This usually happens when:
- Partner migrates users
- Partner reissues accounts
- External IDs change over time
- **Or** a different person is driving the partner side while a previous user left their NAU session open on a shared computer

The authorization flow cannot tell these apart, because both look exactly the same to it: an authenticated NAU session and an unknown `external_user_id`. So it refuses all of them.

#### What we do:
- Leave the existing SSO record untouched
- Redirect back to the partner callback with `?error=sso_link_conflict`

#### Outcome:
- No account link is ever silently reassigned
- The partner receives an identifiable error and can inform the user

An `external_user_id` that legitimately changed is updated through the SSO management endpoint below, which is a server to server operation and therefore does not depend on any browser session.

## SSO management endpoint

`/nau-openedx-extensions/partner-integration/sso/manage/`

Authenticated with the partner JWT, and always scoped to the registers of the calling `PartnerAPIClient`. A register is addressed either by `external_user_id` or by the NAU `username`, so the operations remain possible when the partner no longer holds the identifier currently stored on the NAU side.

### `GET`

Retrieves a register.

```bash
?external_user_id=123456789
?username=nau_user_123
```

### `PATCH`

Updates the `external_user_id` of an existing register. This is the supported way of applying an identifier that intentionally changed on the partner side.

```json
{
    "external_user_id": "123456789",
    "new_external_user_id": "987654321"
}
```

The register can also be addressed by `username`. The NAU user of the register is never changed. Sending the identifier the register already holds succeeds and changes nothing. If the new identifier is already linked to another NAU user, the request is refused with `409`.

### `DELETE`

Removes a register, which is how a link is undone. Linking again goes through the authorization flow, where the user authenticates.

```json
{
    "external_user_id": "123456789"
}
```
