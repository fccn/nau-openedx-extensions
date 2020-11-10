# -*- coding: utf-8 -*-
# Generated by Django 1.11.18 on 2020-09-09 17:19
from __future__ import absolute_import, unicode_literals

import django.db.models.deletion
import opaque_keys.edx.django.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("bulk_email", "0006_course_mode_targets"),
        ("nau_openedx_extensions", "0003_nauuserextendedmodel_cc_nic_check_digit"),
    ]

    operations = [
        migrations.CreateModel(
            name="NauCourseMessage",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "course_id",
                    opaque_keys.edx.django.models.CourseKeyField(
                        db_index=True, max_length=255
                    ),
                ),
                ("message", models.TextField(blank=True, null=True)),
                (
                    "sender",
                    models.ForeignKey(
                        blank=True,
                        default=1,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("targets", models.ManyToManyField(to="bulk_email.Target")),
            ],
        ),
    ]
