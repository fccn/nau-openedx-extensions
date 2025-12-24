# Enrollment by Domain Filter

This OpenEdX extension allows restricting course enrollment based on user email domains. It integrates with the `openedx-filters` framework to automatically validate domains during the enrollment process.

##  Features

- **Automatic Domain Filtering**: Blocks enrollment for users whose email domains are not in the allowed list
- **Course-Level Configuration**: Enable/disable filtering per course via Advanced Settings
- **Simple Domain Management**: Import domains via command or manage through Django Admin
- **Custom Error Messages**: Configure personalized error messages at course or list level
- **Instructor Override**: Preserves compatibility with manual enrollment allowlists

##  Quick Start


### 1. Configure OpenEdX Filters
Add to your Tutor plugin configuration:

```python
from tutor import hooks

hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-lms-common-settings",
        """
OPEN_EDX_FILTERS_CONFIG = {
    "org.openedx.learning.course.enrollment.started.v1": {
        "fail_silently": False,
        "pipeline": [
            "nau_openedx_extensions.enrollment_by_domain.domain_filter.FilterEnrollmentByAllowedList"
        ]
    }
}
"""
    )
)
```


### 2. Create Domain List
```bash
# Basic import with minimal options
python manage.py lms import_enrollment_domains example_domains.txt university-partners
```
> [!NOTE] You must use the files relative or absolute path, example: ../extra/nau-openedx-extensions/nau_openedx_extensions/enrollment_by_domain/example_domains.txt


### 3. Configure Course
In **Studio** → **Advanced Settings** → **Other Course Settings**:
```json
{
    "filter_enrollment_allowed_list_code": "university-partners"
}
```

##  Domain Management

### Import Command Syntax
```bash
python manage.py lms import_enrollment_domains <file.txt> <list-code> [options]
```

### Command Options

| Option | Description |
|--------|-------------|
| `--description "text"` | List description |
| `--custom-message "text"` | Custom error message |

### Domain File Format
```txt
# University domains (comments start with #)
university.edu
student.university.edu
faculty.university.edu

# Partner institutions
partner.org
collaborator.ac.uk
alumni.university.edu

# Empty lines and comments are ignored
```

##  Usage Examples

### Basic Usage
```bash
# Simple domain import
python manage.py lms import_enrollment_domains domains.txt list-code

# With description
python manage.py lms import_enrollment_domains domains.txt list-code --description "Partner universities"

# With custom error message
python manage.py lms import_enrollment_domains domains.txt list-code --custom-message "Contact admissions@university.edu for access"

# Full configuration
python manage.py lms import_enrollment_domains domains.txt list-code --description "Partner universities" --custom-message "Only partner university students can enroll"
```

### Example 1: University Partners
```bash
# txt file
# Main universities
university.edu
partneruniv.edu
college.edu

# Student domains
students.university.edu
alumni.university.edu


# Import domains
python manage.py lms import_enrollment_domains university_domains.txt university-partners --description "Partner universities" --custom-message "Only students from partner universities can enroll. Contact admissions@university.edu for assistance."
```

**Course Configuration in Studio:**
```json
{
    "filter_enrollment_allowed_list_code": "university-partners"
}
```

### Example 2: Corporate Training Program
```bash
# Create corporate domains .txt file
# Primary companies
company.com
corporation.org
business.net

# Subsidiaries
subsidiary1.company.com
subsidiary2.company.com


# Import corporate domains
python manage.py lms import_enrollment_domains corporate_domains.txt corporate-training --description "Corporate training participants" --custom-message "This course is restricted to employees of partner companies."
```

### Example 3: Multiple Domain Lists
```bash
# University partners list
python manage.py lms import_enrollment_domains university_domains.txt uni-partners --description "University partners"

# Corporate partners list
python manage.py lms import_enrollment_domains corporate_domains.txt corp-partners --description "Corporate partners"

# Alumni program list
python manage.py lms import_enrollment_domains alumni_domains.txt alumni-program --description "Alumni program participants"
```

### Example 4: Adding More Domains
```bash
# Add new domains to existing list
python manage.py lms import_enrollment_domains additional_partners.txt university-partners

# Update existing list with new description and message
python manage.py lms import_enrollment_domains updated_domains.txt university-partners --description "Updated partner list" --custom-message "New enrollment policy applies"
```

**Note**: The command only adds new domains. Existing domains are preserved and duplicates are automatically skipped.

##  Course Configuration

### Enable Filter for a Course

1. Go to **Studio** → **Settings** → **Advanced Settings**
2. Find **"Other Course Settings"** or add new field
3. Add configuration:

```json
{
    "filter_enrollment_allowed_list_code": "your-list-code"
}
```

### Custom Error Messages

**Option 1: List-level message (affects all courses using this list)**
```bash
python manage.py lms import_enrollment_domains domains.txt my-list --custom-message "Contact support@example.com for enrollment assistance."
```

**Option 2: Course-level message (overrides list message for this course)**
```json
{
    "filter_enrollment_allowed_list_code": "my-list",
    "filter_enrollment_by_domain_custom_exception_message": "This course is restricted to university partners only."
}
```

If the custom exception message is not defined, it will use a default message

### Priority Order for Error Messages
1. **Course-level custom message** (from Advanced Settings)
2. **List-level custom message** (from import command or Django admin)
3. **Default message**: "You can't enroll on this course because your email domain is not allowed. If you think this is an error, contact the course support."


##  Command Output Examples

### New List Creation
```
============================================================
 IMPORT SUMMARY: university-partners
============================================================
 Created new allowed list

   Domain Statistics:
   Domains in file: 8
   Domains to add: 8
   Domains unchanged: 0
   Import completed successfully!
   Added: 8 domains
   Total domains in list: 8
============================================================
```

### Adding to Existing List
```
============================================================
 IMPORT SUMMARY: university-partners
============================================================
  Found existing allowed list

   Domain Statistics:
   Domains in file: 10
   Domains to add: 2
   Domains unchanged: 8

   Import completed successfully!
   Added: 2 domains
   Total domains in list: 10
============================================================
```

### No Changes Needed
```
============================================================
 IMPORT SUMMARY: university-partners
============================================================
  Found existing allowed list

   Domain Statistics:
   Domains in file: 8
   Domains to add: 0
   Domains unchanged: 8

   No changes needed
   All domains already in list
   Total domains in list: 8
============================================================
```

##  How It Works

### Filter Activation
1. **User attempts enrollment** in a course
2. **OpenEdX Event** `org.openedx.learning.course.enrollment.started.v1`
3. **Filter checks** if course has `filter_enrollment_allowed_list_code` configured
4. **If configured**, validates user's email domain against the allowed list
5. **Blocks enrollment** if domain is not allowed
6. **Shows custom message** to the user



##  Django Admin Management

Access domain management through Django Admin:

1. Go to `/admin/`
2. Navigate to **"Enrollment By Domain"** section
3. Manage **"Enrollment Allowed Lists"** and **"Enrollment Allowed Domains"**

##  Best Practices

1. **Use descriptive list codes** (`university-partners`, not `list1`)
2. **Set custom messages** for better user experience
3. **Test thoroughly** after configuration changes

