""" Grades edxapp backend abstraction """
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory


def get_course_grades(user, course):
    """
    Gets course grades for a given student
    """
    grades = CourseGradeFactory().read(user, course)

    return grades
