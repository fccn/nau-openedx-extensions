# Generated migration for NauCourseFilter model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nau_openedx_extensions', '0011_alter_ssopartnerintegration_unique_together'),
    ]

    operations = [
        migrations.CreateModel(
            name='NauCourseFilter',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('course_id', models.CharField(
                    db_index=True,
                    help_text='Course key string (e.g. course-v1:ORG+ID+Run)',
                    max_length=255,
                    verbose_name='Course ID',
                )),
                ('filter_type', models.CharField(
                    help_text=(
                        'Filter key name as stored in other_course_settings '
                        '(e.g. filter_enrollment_by_domain_list, filter_enrollment_require_nif, '
                        'certificate_require_portuguese_citizen_card)'
                    ),
                    max_length=255,
                    verbose_name='Filter Type',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'NAU Course Filter',
                'verbose_name_plural': 'NAU Course Filters',
                'ordering': ['course_id', 'filter_type'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='naucoursefilter',
            unique_together={('course_id', 'filter_type')},
        ),
    ]
