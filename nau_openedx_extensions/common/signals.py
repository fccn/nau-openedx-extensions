"""
NAU Custom code to skip Open edX ID Verification module.
"""
import logging

from django.db.models.signals import pre_save
from django.dispatch import receiver
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

log = logging.getLogger(__name__)


@receiver(pre_save, sender=CourseOverview)
def fix_course_overview_required_fields(sender, instance: CourseOverview, **kwargs):
    """
    Fix CourseOverview required fields before saving by
    ensuring the CourseOverview has a valid entrance_exam_minimum_score_pct field.
    The entrance_exam_minimum_score_pct field is required but has a default value of 0.65.
    """
    log.info(f"Pre-save signal triggered for CourseOverview: {instance.id}")
    # Ensure the course_overview has a valid entrance_exam_minimum_score_pct
    if instance.entrance_exam_minimum_score_pct is None:
        instance.entrance_exam_minimum_score_pct = 0.65
        log.info(f"Fix CourseOverview on pre_save: {instance.id}")
