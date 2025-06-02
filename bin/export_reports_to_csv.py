"""
**Use Case**

    Download reports for multiple courses to your system.

**Description**
    This script is intended to be used for downloading reports for multiple courses on Open edX.
    It is designed to be run from the command line and takes several command line arguments.
    It should be executed by a user with course team permissions, mainly as a 
    data_researcher role inside the course.
    This script reads a course ID or a file containing course IDs, then it will execute
    a call to the Open edX API to download reports for each course.
    It downloads the latest reports from the system. Alternatively, you can specify the number of days ago
    to create a date range to download the reports from.

**Warn**
    If you execute this script too much times, your Open edX LMS account could be locked for
    30 minutes.

**Help**
    To view the command line arguments:
    python3 export_reports_to_csv.py -h

**Example Request**
    Download all student profiles from the course course-v1:FCT+TPag+2024_T3
    from the last 30 days.

    python3 export_reports_to_csv.py --email <email> --password <password> \
        --lms_url https://lms.nau.edu.pt --course_id course-v1:FCT+TPag+2024_T3 \
        --report get_students_profile --days_ago 30
    
    Download the most recent grade report from the all courses in the courses.txt file.
    In this case you can omit the days_ago argument.

    python3 export_reports_to_csv.py --email <email> --password <password> \
        --lms_url https://lms.nau.edu.pt --course_ids_file courses.txt \
        --report grade_report

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
import datetime
import requests
from pathlib import Path


REPORT_TO_DOCUMENT = {
    "get_students_profile": "student_profile_info",
    "get_students_who_may_enroll": "may_enroll_info",
    "get_student_anonymized_ids": "anonimized_ids",
    "grade_report": "grade_report",
    "problem_grade_report": "problem_grade_report",
    "ora_data_report": "ORA_data",
    "ora_summary_report": "ORA_summary",
    "get_problem_responses": "student_state_from",
}


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

def download_report(session, csrftoken, lms_url, course_id, report, additional_info, output_dir, days_ago):
    """
    Download a generated report from the LMS.
    :param session: The logged in session object
    :param csrftoken: The CSRF token
    :param lms_url: The LMS URL (e.g. https://lms.example.com)
    :param course_id: The course ID to extract the report files for
    :param report: The report name to extract
    :param additional_info: Additional information to be added to the report name
    :return: The report file
    """
    block_id = None

    downloads_list_url = f"{lms_url}/courses/{course_id}/instructor/api/list_report_downloads"

    if additional_info:
        block_id = additional_info[0].replace(":", "_").replace("@", "\\@").replace("+", "\\+")
    
    print(f"Downloading report '{report}' for course '{course_id}'")
    downloads_list_r = session.post(
        downloads_list_url,
        headers={
            "X-CSRFToken": csrftoken,
            "referer": f'{lms_url}/login',
        },
        # add cookies to the request
        cookies={
            "csrftoken": csrftoken,
        },
    )
    if not downloads_list_r.ok:
        response = str(downloads_list_r)
        raise RuntimeError(
            f"""Invalid download list request, check your course_id arguments {response}.
            Check if you have access to the Instructor Data Download tab inside the course {lms_url}/courses/{course_id}/instructor#view-data_download
            """)
        
    # Filter and download the report file to the current directory
    report_files = _filter_by_report(report, course_id, downloads_list_r.json(), days_ago, block_id)
    if not report_files:
        raise RuntimeError(
            f"Report '{report}' not found for course '{course_id}'")
    
    for file in report_files:
        print(f"Downloading file {file['name']} for course {course_id}")
        response = requests.get(file["url"], stream=True)
        response.raise_for_status()
        
        filename = file["name"]
        if output_dir:
            filepath = Path.cwd() / output_dir / course_id / filename
        else:
            filepath = Path.cwd() / course_id / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    

def main():
    """
    Main function to extract course csv reports from Open edX.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", "--user",
                        required=True, help="The email for the Open edX account")
    parser.add_argument("--password", "--pass",
                        required=True, help="The password for the Open edX account")
    parser.add_argument("--lms_url", required=True, help="Your LMS URL (e.g. https://lms.example.com)")
    parser.add_argument("--course_id",
                        help="The course ID to extract the report files for")
    parser.add_argument("--course_ids_file",
                        help="The course IDs file to extract the reports files for",
                        type=argparse.FileType('r', encoding='UTF-8'))
    parser.add_argument("--report",
                        help="Report name to extract", required=True, choices=[
                            "get_students_profile",
                            "get_students_who_may_enroll",
                            "get_student_anonymized_ids",
                            "grade_report",
                            "problem_grade_report",
                            "ora_data_report",
                            "ora_summary_report",
                            "get_problem_responses",
                        ])
    parser.add_argument("--output_dir",
                        help="The directory to save the report files to. Defaults to the current directory")
    parser.add_argument("--days_ago", type=int, default=1,
                        help="Number of days ago to extract the report files for")
    
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
    days_ago = args.days_ago
    output_dir = args.output_dir
    
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

    print(f"Using {len(course_ids_add_info)} courses from the command line arguments")
    print(f"course_ids_add_info {course_ids_add_info}")

    session, csrftoken = login_to_lms(lms_url, auth_email, auth_password)
    print(f"Logged in as {auth_email} to {lms_url}")
    
    for course_id, additional_info in course_ids_add_info:
        download_report(session, csrftoken, lms_url, course_id, report, additional_info, output_dir, days_ago)

def _normalize_course_id(course_id):
    return course_id.split(':')[1].replace('+', '_')

def _filter_by_report(report, course_id, files, days_ago, block_id=None):
    today = datetime.datetime.now()
    end_date = today - datetime.timedelta(days=days_ago)
    doc_course_id = _normalize_course_id(course_id)

    print("=" * 60)
    print(f"Downloading {report} reports from {end_date.strftime('%Y-%m-%d %H:%M')} to {today.strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    if block_id:
        regex_expression = fr'{doc_course_id}_{REPORT_TO_DOCUMENT[report]}_{block_id}_(\d{{4}}-\d{{2}}-\d{{2}}-\d{{4}})\.csv$'
    else:
        regex_expression = fr'{doc_course_id}_{REPORT_TO_DOCUMENT[report]}_(\d{{4}}-\d{{2}}-\d{{2}}-\d{{4}})\.csv$'

    doc_name_pattern = re.compile(regex_expression)
    
    return [f for f in files["downloads"]
            if (match := doc_name_pattern.match(f["name"])) and \
            datetime.datetime.strptime(match.group(1), "%Y-%m-%d-%H%M") >= end_date]

if __name__ == "__main__":
    main()