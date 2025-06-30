"""
**Use Case**

    Generate reports for multiple courses.

**Description**
    This script is intended to be used for generating reports for multiple courses on Open edX.
    It is designed to be run from the command line and takes several command line arguments.
    It should be executed by a user with course team permissions inside the course.
    This script reads a course ID or a file containing course IDs, then it will execute
    a call to the Open edX API to generate reports for each course.

**Warn**
    If you execute this script too much times, your Open edX LMS account could be locked for
    30 minutes.

**Help**
    To view the command line arguments:
    python3 generate_reports.py -h

**Example Request**
    To generate reports for multiple courses, fill in your email and password details,
    while making sure that you have the necessary permissions to access the courses as a data_researcher.
    You can specify a single course ID or a file containing multiple course IDs.

    python3 generate_reports.py --email <email> --password <password> \
        --lms_url https://lms.nau.edu.pt --course_id course-v1:FCT+TPag+2024_T3 \ 
        --course_ids_file courses.txt --report get_students_profile

**Courses File**
    The courses file should contain one line per course. For example:

    course-v1:FCT+TPag+2024_T3
    course-v1:FCT+Teste+2024_T3
    
    Or one line with the additional block to be used by 'get_problem_responses' report. Example:

    course-v1:FCT+TPag+2024_T3 block-v1:FCT+TPag+2024_T3+type@problem+block@ac87b7d6c48e343e94b7
    course-v1:FCT+Teste+2024_T3 block-v1:FCT+Teste+2024_T3+type@problem+block@1
"""
import argparse
import re
import sys

import requests


def login_to_lms(lms_url, auth_email, auth_password):
    """
    Log in to the LMS and return a session object.
    :param lms_url: The LMS URL (e.g. https://lms.example.com)
    :param auth_email: The email of the user with course team permissions
    :param auth_password: The password of the user with course team permissions
    :return: A requests.Session object with the logged in session and CSRF token
    :raises RuntimeError: If the login fails
    """
    session = requests.Session()
    login = session.get(f'{lms_url}/login')
    csrftoken = login.cookies.get("csrftoken")
    auth_r = session.post(
        f'{lms_url}/api/user/v1/account/login_session/',
        data={
            "email": auth_email,
            "password": auth_password,
        },
        headers={
            "X-CSRFToken": csrftoken,
            "referer": f'{lms_url}/login',
        },
    )
    if not auth_r.ok:
        response = str(auth_r)
        raise RuntimeError(
            f'Invalid login, check your user/pass arguments {response}')
    return session, csrftoken


def generate_report_url_data(course_id, lms_url, report, additional_info):
    """
    Generate the data for the report URL.
    :param course_id: The course ID to generate reports for
    :param lms_url: The LMS URL (e.g. https://lms.example.com)
    :param report: The report type to generate
    :param additional_info: Additional information, mainly IDs for problems
    :return: A dictionary with the data for the report URL
    """
    if report == "get_students_profile":
        return f"{lms_url}/courses/{course_id}/instructor/api/get_students_features/csv", {}
    elif report == "get_students_who_may_enroll":
        return f"{lms_url}/courses/{course_id}/instructor/api/get_students_who_may_enroll", {}
    elif report == "get_student_anonymized_ids":
        return f"{lms_url}/courses/{course_id}/instructor/api/get_anon_ids", {}
    elif report == "calculate_grades":
        return f"{lms_url}/courses/{course_id}/instructor/api/calculate_grades_csv", {}
    elif report == "problem_grade_report":
        return f"{lms_url}/courses/{course_id}/instructor/api/problem_grade_report", {}
    elif report == "ora_data_report":
        return f"{lms_url}/courses/{course_id}/instructor/api/export_ora2_data", {}
    elif report == "ora_summary_report":
        return f"{lms_url}/courses/{course_id}/instructor/api/export_ora2_summary", {}
    elif report == "get_problem_responses":
        if additional_info:
            data = {
                "problem_location": additional_info[0],
            }
        else:
            data = {}
        return f"{lms_url}/courses/{course_id}/instructor/api/get_problem_responses", data
    # NAU custom reports
    elif report == "export_course_certificates":
        return f"{lms_url}/nau-openedx-extensions/certificate-export/courses/{course_id}/csv", {}
    elif report == "export_course_certificates_pdfs":
        return f"{lms_url}/nau-openedx-extensions/certificate-export/courses/{course_id}/pdf", {}
    else:
        raise RuntimeError(
            f'Unsupported report {report} request')


def generate_report_for_course(session, csrftoken, lms_url, course_id, report, additional_info):
    """
    Generate reports for a course using the Open edX API.

    :param csrftoken: The CSRF token for the session
    :param lms_url: The LMS URL (e.g. https://lms.example.com)
    :param auth_email: The email of the user with course team permissions
    :param auth_password: The password of the user with course team permissions
    :param course_id: The course ID to generate reports for
    :param report: The report type to generate
    :param additional_info: Additional information to be used in the report
    :raises RuntimeError: If the report generation fails
    """
    # print(f"Generating report '{report}' for course '{course_id}' "
    #   "with additional info: {additional_info}")
    url, data = generate_report_url_data(course_id, lms_url, report, additional_info)
    print(f"Generating report '{report}' for course '{course_id}' at '{url}' with data {data}")
    report_r = session.post(
        url,
        headers={
            "X-CSRFToken": csrftoken,
            "referer": f'{lms_url}/login',
        },
        # add cookies to the request
        cookies={
            "csrftoken": csrftoken,
        },
        # HTTP POST payload
        data=data,
    )
    if not report_r.ok:
        raise RuntimeError(
            f"Invalid report '{report}' request, check if you have access to the "
            f"Instructor Data Download tab inside the course {lms_url}/courses/{course_id}/instructor#view-data_download \n"
            f"Response: {report_r.text}")
    print(f"Report {report} submitted successfully for course {course_id}")


def main():
    """
    Main function to enroll users in a course using the Open edX API.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", "--user",
                        required=True, help="The course team email with data_researcher permissions")
    parser.add_argument("--password", "--pass",
                        required=True, help="The course team password")
    parser.add_argument("--lms_url", required=True, help="Your LMS URL (e.g. https://lms.example.com)")
    parser.add_argument("--course_id",
                        help="The course ID to enroll users in")
    parser.add_argument("--course_ids_file",
                        help="The course ID files to generate reports for",
                        type=argparse.FileType('r', encoding='UTF-8'))
    parser.add_argument("--report",
                        help="Report type to be generated", required=True, choices=[
                            "get_students_profile",
                            "get_students_who_may_enroll",
                            "get_student_anonymized_ids",
                            "calculate_grades",
                            "problem_grade_report",
                            "ora_data_report",
                            "ora_summary_report",
                            "get_problem_responses",
                            # NAU custom reports
                            "export_course_certificates",
                            "export_course_certificates_pdfs",
                        ])

    try:
        args = parser.parse_args()
    except SystemExit:
        print("Error: Invalid arguments")
        # parser.print_help()
        sys.exit(0)
    auth_email = args.email
    auth_password = args.password
    lms_url = args.lms_url
    course_id = args.course_id
    course_ids_file = args.course_ids_file
    report = args.report

    if not course_id and not course_ids_file:
        print("Error: You must provide a course_id or a course_ids_file")
        sys.exit(1)
    if course_id and course_ids_file:
        print("Error: You must provide only one of course_id or course_ids_file")
        sys.exit(1)

    course_ids_add_info = []
    if course_ids_file:
        # read course ids from the file
        for line in course_ids_file:
            # Remove any whitespace characters like `\n` at the end of each line
            line_striped = line.strip()
            columns = re.split(',|;| ', line_striped)
            course_id = columns[0]  # assuming the first column is the course_id
            additional_info = columns[1:]
            course_ids_add_info.append((course_id, additional_info))

        if not course_ids_add_info:
            print("Error: The course_ids_file is empty")
            sys.exit(1)
        print(f"Using {len(course_ids_add_info)} courses from the file")
    else:
        # if course_id is provided, add it to the list
        course_ids_add_info.append((course_id, []))

    print(f"Using {len(course_ids_add_info)} courses")

    session, csrftoken = login_to_lms(lms_url, auth_email, auth_password)
    print(f"Logged in as {auth_email} to {lms_url}")

    # for each course_ids_add_info in the list, call the generate_report function
    for course_id, additional_info in course_ids_add_info:
        generate_report_for_course(
            session, csrftoken, lms_url, course_id, report, additional_info)


# call
main()
