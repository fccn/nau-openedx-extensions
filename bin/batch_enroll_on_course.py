"""
**Use Case**

    Enroll multiple users in one course.

**Description**
    This script is intended to be used for batch enrolling users in a course on Open edX.
    It is designed to be run from the command line and takes several command line arguments.
    It should be executed by a user with course team permissions inside the course.
    This script reads a course ID and other options from the input and also a file
    containing user emails, then it will execute a call to the Open edX API to enrolls/unenrolls
    each user in the specified course.
    In case of error the script can be run multiple times.
    The script will not (un)enroll the user if he/she is already enrolled in the course, so you
    can safely run the script multiple times with the same CSV file. Nevertheless, the script
    will notify the user multiple times if he/she have been enrolled / executed for the course.

**Warn**
    If you execute this script too much times, your Open edX LMS account could be locked for
    30 minutes.
    If the script raises an error at the middle of the execution, you should execute it again with
    only the users that were not enrolled, if not the already enrolled users will receive multiple
    emails.

**Help**
    To view the command line arguments:
    python3 batch_enroll_on_course.py -h

**Example Request**
    Each user will receive an email with the course information and a link to access it.
    The users will be enrolled in the course when they have finished creating its own account.
    If the user already has an account, the script is going to still send an email inform him
    that he/she was enrolled on the course by the course team.

    python3 batch_enroll_on_course.py --email <email> --password <password> \
        --lms_url https://lms.nau.edu.pt --auto_enroll --email_students \
        ---course_id course-v1:FCT+CODE+EDITION --emails_file=/tmp/emails.txt

**Email File**
    The email file should contain one email per line. For example:

    email@example.com
    other_email@example.com
    another_email@example.com
"""
import argparse
import json
import sys

import requests


def main():
    """
    Main function to enroll users in a course using the Open edX API.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", "--user",
                        required=True, help="The course team email that will enroll users")
    parser.add_argument("--password", "--pass",
                        required=True, help="The course team password that will enroll users")
    parser.add_argument("--lms_url", required=True, help="Your LMS domain")
    parser.add_argument("--course_id", required=True,
                        help="The course ID to enroll users in")
    parser.add_argument("--emails_file", required=True,
                        help="A file containing students emails to enroll",
                        type=argparse.FileType('r', encoding='UTF-8'))
    parser.add_argument("--action",
                        help="The action enroll or unenroll", default="enroll")
    parser.add_argument("--auto_enroll", action='store_true', default=False,
                        help="Whether the students will be enrolled as soon as they register,"
                        " or if they just be allowed to enroll (default)")
    parser.add_argument("--email_students", action='store_true',
                        help="Whether students will be notified by email, "
                        "by default they aren't notified", default=False)

    try:
        args = parser.parse_args()
    except SystemExit:
        print("Error: Invalid arguments")
        parser.print_help()
        sys.exit(0)
    auth_email = args.email
    auth_password = args.password
    lms_url = args.lms_url
    course_id = args.course_id
    emails_file = args.emails_file
    action = args.action
    auto_enroll = args.auto_enroll
    email_students = args.email_students

    # print(user_email)
    # print(user_password)
    # print(lms_url)

    # For each line in the file, get the email and add it to a list
    emails = []
    for line in emails_file:
        # Remove any whitespace characters like `\n` at the end of each line
        email = line.strip()
        emails.append(email)

    emails_len = len(emails)
    print(f"{action.capitalize()}ing {emails_len} users on {course_id}... "
          f"auto_enroll: {auto_enroll} email_students: {email_students}")

    session = requests.Session()
    login = session.get(f'{lms_url}/login')
    auth_r = session.post(
        f'{lms_url}/api/user/v1/account/login_session/',
        data={
            "email": auth_email,
            "password": auth_password,
        },
        headers={
            "X-CSRFToken": login.cookies.get("csrftoken"),
            "referer": f'{lms_url}/login',
        },
    )
    if not auth_r.ok:
        response = str(auth_r)
        raise RuntimeError(
            f'Invalid login, check your user/pass arguments {response}')

    # define counts for each call with before and after vales of each user
    b_user_count = 0
    b_enrollment_count = 0
    b_allowed_count = 0
    b_auto_enroll_count = 0
    a_user_count = 0
    a_enrollment_count = 0
    a_allowed_count = 0
    a_auto_enroll_count = 0

    # iterate each email received on the file
    for idx, email in enumerate(emails):
        print(f"{action.capitalize()}ing {idx+1} of {len(emails)} on {email}")
        # This method uses the `ensure_csrf_cookie` decorator to ensure that the CSRF
        # token is set in the cookies.
        # The CSRF token is required for making POST requests to the Open edX API.
        api_result = session.post(
            f"{lms_url}/courses/{course_id}/instructor/api/students_update_enrollment",
            data={
                "action": action,
                "identifiers": email,
                "course_id": course_id,
                "auto_enroll": auto_enroll,
                "email_students": email_students,
            },
            headers={
                "X-CSRFToken": login.cookies.get("csrftoken"),
                "referer": f'{lms_url}/login',
            },
            # add cookies to the request
            cookies={
                "csrftoken": login.cookies.get("csrftoken"),
            }
        )

        # The api_result is something like:
        # {
        #     "action": "enroll",
        #     "results": [
        #         {
        #             "identifier": "igobranco+fdsdsfdsfdsfs@gmail.com",
        #             "before": {
        #                 "user": false,
        #                 "enrollment": false,
        #                 "allowed": false,
        #                 "auto_enroll": false
        #             },
        #             "after": {
        #                 "user": false,
        #                 "enrollment": false,
        #                 "allowed": true,
        #                 "auto_enroll": true
        #             }
        #         }
        #     ],
        #     "auto_enroll": true
        # }

        # read api result has json
        if not api_result.ok:
            response = str(api_result)
            raise RuntimeError(
                f'Invalid API call, check your user/pass arguments {response}')

        # read response as json
        api_result_dict = json.loads(api_result.text)

        results = api_result_dict.get('results')

        # iterate each result received on the API call
        for result in results:
            if bool(result.get('before').get('user')):
                b_user_count += 1
            if bool(result.get('before').get('enrollment')):
                b_enrollment_count += 1
            if bool(result.get('before').get('allowed')):
                b_allowed_count += 1
            if bool(result.get('before').get('auto_enroll')):
                b_auto_enroll_count += 1
            if bool(result.get('after').get('user')):
                a_user_count += 1
            if bool(result.get('after').get('enrollment')):
                a_enrollment_count += 1
            if bool(result.get('after').get('allowed')):
                a_allowed_count += 1
            if bool(result.get('after').get('auto_enroll')):
                a_auto_enroll_count += 1

    # print the counts
    print(f"Before: {b_user_count} users, {b_enrollment_count} enrollments,"
          f" {b_allowed_count} allowed, {b_auto_enroll_count} auto_enroll")
    print(f"After: {a_user_count} users, {a_enrollment_count} enrollments, "
          f"{a_allowed_count} allowed, {a_auto_enroll_count} auto_enroll")


# call
main()
