""" Grades edxapp backend abstraction """
from __future__ import absolute_import, unicode_literals

from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory  # pylint: disable=import-error


def get_course_grades(user, course):
    """
    Gets course grades for a given student
    """
    grades = CourseGradeFactory().read(user, course)

    return grades
