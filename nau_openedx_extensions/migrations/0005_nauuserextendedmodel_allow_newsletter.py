# -*- coding: utf-8 -*-
# Generated by Django 2.2.16 on 2021-02-12 15:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nau_openedx_extensions', '0004_naucoursemessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='nauuserextendedmodel',
            name='allow_newsletter',
            field=models.BooleanField(default=False, verbose_name='Allow newsletter'),
        ),
    ]
