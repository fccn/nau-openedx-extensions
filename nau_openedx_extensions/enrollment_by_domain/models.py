"""
Models for enrollment_by_domain app.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class EnrollmentAllowedList(models.Model):
    """
    Model to define lists of allowed domains for course enrollment.
    """

    code = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("Unique code to identify this allowed list"),
        verbose_name=_("Code"),
    )
    description = models.TextField(
        blank=True,
        help_text=_("Description of this allowed list"),
        verbose_name=_("Description"),
    )
    custom_exception_message = models.TextField(
        blank=True,
        help_text=_("Custom message to show when enrollment is blocked. If empty, uses default message."),
        verbose_name=_("Custom Exception Message"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Enrollment Allowed List")
        verbose_name_plural = _("Enrollment Allowed Lists")
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.description[:50]}"


class EnrollmentAllowedDomain(models.Model):
    """
    Model to store individual domains within an allowed list.
    """
    allowed_list = models.ForeignKey(
        EnrollmentAllowedList,
        on_delete=models.CASCADE,
        related_name='domains',
        verbose_name=_("Allowed List")
    )
    domain = models.CharField(
        max_length=255,
        help_text=_("Domain name (e.g., 'example.com')"),
        verbose_name=_("Domain"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Enrollment Allowed Domain")
        verbose_name_plural = _("Enrollment Allowed Domains")
        unique_together = ['allowed_list', 'domain']
        ordering = ['domain']

    def __str__(self):
        return f"{self.allowed_list.code}: {self.domain}"
