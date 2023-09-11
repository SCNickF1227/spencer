# Spencer is a basic Python script which is designed to run in conjunction with "multi_report" by Joe Schmuck
# https://github.com/JoeSchmuck/Multi-Report
# Spencer checks for additional errors which may appear in your logs that you otherwise may be unaware of.
# The initial version of this script is versioned v1.1 and was written by ChatGPT and NickF
# -----------------------------------------------
# Version 2.0 08/22/23
# Refactored alot of code.
# Dynamically determine whether run from MultiReport or if Spencer is called directly.
# Overall improvements to robustness of the script, the accuracy of it's findings, and an increase in scope.
# New search patterns and customizability.
# -----------------------------------------------
# Verion 1.3 08/13/23 - Contibution by JoeSchmuck merged
# Added a new feature for tracking and reporting previous errors differantly than new errors.
# -----------------------------------------------
# This updated script will run normally and will run with Multi-Report.
# To use with Multi-Report, call the script with parameter 'multi_report'.
# When using the 'multi_report' switch, the email will not be sent and a few files will be created in /tmp/ space
# that Multi-Report will use and delete during cleanup.
# This script must be names "spencer.py" by default.  Multi-Report would need to be updated if the script name changes.
# If Spencer finds no errors, Multi-Report will not issue a Spencer report.  You can tell Spencer ran by observing the Standard Output.
# -----------------------------------------------
# Recommendations:
# 1-Record all the errors in a file for later comparison.
# 2-When displaying the error data, include both pre and post non-error lines of data.  Sort of what you do now.
# 3-Do not include any line of data twice.  So a list of error messages would start with the message before the error
#   and end with the non-error message after the sting of errors.
# 4-When determining if a problem is new or old, conduct an exact match line by line to the file you saved in step 1.
#   Do not just count the number of errors becasue if 4 errors clear and 4 new errors are generated, the user will never know
#   about the new errors under the current setup.  I considered creating a file to solve this but my Python skills are limited.
# 5-Remove all my "# (Joe)" comments, they are there to make it clear to you what lines I changed.
# 6-I want to leave this script in your hands because I do not have a SAS or iSCSI interface so I'm not the correct person to maintain this.
# -----------------------------------------------
# Importing necessary modules
from importlib.resources import contents
import json
from mailbox import linesep
import subprocess
import datetime
import socket
import sys
import platform
import logging
import re
import os

# Setup logging
logging.basicConfig(filename='spencer.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info('Spencer script started')

hostname = socket.gethostname()
# Get the hostname of the current machine and store it in the variable 'hostname'
# Configuration
use_multireport = True  # set this to True for multireport (writing to a file), otherwise False for email

USE_WITH_MULTI_REPORT = sys.argv[1] if len(sys.argv) > 1 else "False"
# Check if a command line argument is provided, if yes, assign its value to 'USE_WITH_MULTI_REPORT',
# otherwise assign "False" to 'USE_WITH_MULTI_REPORT'

DEFAULT_RECIPIENT = "YourEmail Address.com"
# Set the default email recipient address to "YourEmail Address.com"
to_address = DEFAULT_RECIPIENT

ERROR_SUBJECT = f"[SPENCER] [ERROR] Error Found in Log for {hostname}"
# Create a string for the error email subject, including the hostname

SUCCESS_SUBJECT = f"[SPENCER] [SUCCESS] All is Good! for {hostname}"
# Create a string for the success email subject, including the hostname

PREV_ERROR_SUBJECT = f"[SPENCER] [PREVIOUS ERROR] No new Errors Found, Previous Errors Exist in Log for {hostname}"
# Create a string for the previous error email subject, including the hostname

ERRORS_FILE = "previous_errors.json"
# Set the filename for the previous errors file to "previous_errors.json"

CONTENT_FILE = "/tmp/spencer_report.txt"
# Set the filename for the content file to "/tmp/spencer_report.txt"
print(f"{datetime.datetime.now()} - Spencer V2.0 - BETA - 8/22/23.")
print(f"{datetime.datetime.now()} - Writen by NickF with Contributions from JoeSchmuck")
print(f"{datetime.datetime.now()} - Spencer is checking log files for errors{' and pushing output to Multi-Report' if USE_WITH_MULTI_REPORT == 'multi_report' else ''}.")
# -----------------------------------------------
# Error Patterns List
# -----------------------------------------------

# Linux (TrueNAS SCALE)
# -----------------------------------------------
# iSCSI related patterns
# High Severity:
ERROR_PATTERN_ISCSI_TIMEOUT = ("iscsi", ["timeout", "timed out"], [], "iscsi_timeout")
ERROR_PATTERN_ISCSI_SESSION_ISSUES = ("iSCSI Initiator: session", ["login rejected", "recovery timed out"], [], "iscsi_session_issues")

# Moderate Severity:
ERROR_PATTERN_ISCSI_CONNECT_ERROR = ("iSCSI Initiator: connect to", ["failed"], [], "iscsi_connect_error")
ERROR_PATTERN_ISCSI_KERNEL_ISSUE = ("iSCSI Initiator: kernel reported", ["error"], [], "iscsi_kernel_issue")

# Low Severity:
ERROR_PATTERN_ISCSI_LOGOUT_ISSUE = ("iSCSI Initiator: received iferror", ["-"], [], "iscsi_logout_issue")

# NFS-related error patterns
# High Severity:
ERROR_PATTERN_NFS_SERVER_NOT_RESPONDING = ("nfs: server", ["not responding"], [], "nfs_server_not_responding")
ERROR_PATTERN_NFS_STALE = ("nfs:", ["Stale file handle"], [], "nfs_stale")
ERROR_PATTERN_NFS_TIMED_OUT = ("nfs:", ["timed out"], [], "nfs_timed_out")

# Moderate Severity:
ERROR_PATTERN_NFS_SERVER_OK = ("nfs: server", ["OK"], [], "nfs_server_ok")
ERROR_PATTERN_NFS_PORTMAP = ("portmap:", ["is not running"], [], "nfs_portmap_issue")
ERROR_PATTERN_NFS_RETRYING = ("nfs:", ["retrying"], [], "nfs_retrying")
ERROR_PATTERN_NFS_MOUNT_ISSUE = ("nfs: mount", ["failure", "failed", "unable", "error"], [], "nfs_mount_issue")
ERROR_PATTERN_NFS_ACCESS_DENIED = ("nfs:", ["access denied", "permission denied"], [], "nfs_access_denied")

# SCSI related patterns
# High Severity:
ERROR_PATTERN_CDB_ERRORS = ("cdb:", ["read", "write", "verify", "inquiry", "mode sense"], ["inquiry"], "cdb_errors")

# FreeBSD (TrueNAS CORE)
# -----------------------------------------------
# NFS-related patterns
# High Severity:
ERROR_PATTERN_FREEBSD_NFS_TIMED_OUT = ("NFS server", ["operation timed out"], [], "freebsd_nfs_timed_out")

# iSCSI-related patterns
# High Severity:
ERROR_PATTERN_CAM_STATUS_ISCSI_ISSUES = ("CAM status:", ["iSCSI Initiator Connection Reset", "iSCSI Target Suspended", "iSCSI Connection Lost"], [], "cam_status_iscsi_issues")

# Moderate Severity:
ERROR_PATTERN_CTL_DATAMOVE = ("ctl_datamove", ["aborted"], [], "ctl_datamove")
ERROR_PATTERN_ISCSI_GENERAL_ERRORS = ("iSCSI:", ["connection is dropped", "connection is now full feature phase", "task command timed out for connection", "connection is logged out", "received an illegal iSCSI PDU"], [], "iscsi_general_errors")

# Other SCSI patterns (not specific to iSCSI)
# High Severity:
ERROR_PATTERN_CAM_STATUS_ERROR = ("cam status:", ["scsi status error", "ata status error", "command timeout", "command aborted"], ["command retry", "command complete"], "cam_status_error")

# General error patterns (could be from both or either OS)
# -----------------------------------------------
# High Severity:
ERROR_PATTERN_SCSI_ERROR = ("scsi error", [], [], "scsi_error")
ERROR_PATTERN_HARD_RESETTING_LINK = ("hard resetting link", [], [], "hard_resetting_link")
ERROR_PATTERN_ATA_BUS_ERROR = ("ata bus error", [], [], "ata_bus_error")

# Moderate Severity:
ERROR_PATTERN_FAILED_COMMAND_READ = ("failed command: read FPDMA queued", [], [], "failed_command_read")
ERROR_PATTERN_FAILED_COMMAND_WRITE = ("failed command: write FPDMA queued", [], [], "failed_command_write")
ERROR_PATTERN_EXCEPTION_EMASK = ("exception Emask", [], [], "exception_emask")

# Low Severity:
ERROR_PATTERN_ACPI_ERROR = ("ACPI Error", [], [], "acpi_error")
ERROR_PATTERN_ACPI_EXCEPTION = ("ACPI Exception", [], [], "acpi_exception")
ERROR_PATTERN_ACPI_WARNING = ("ACPI Warning", [], [], "acpi_warning")
# -----------------------------------------------
# END Error Patterns List
# -----------------------------------------------
# Start Severities List
# -----------------------------------------------
SEVERITIES = {
    "high": "High Severity",
    "moderate": "Moderate Severity",
    "low": "Low Severity"
}

ERROR_DESCRIPTIONS = {
    'hard_resetting_link': ('Hard Resetting Link', 'Indicates that a storage communication link on the TrueNAS system was forcibly reset, which may affect data transfer or access.'),
    'failed_command_read': ('Failed Command Read', 'TrueNAS encountered a failure when trying to read data, suggesting potential disk or communication issues.'),
    'failed_command_write': ('Failed Command Write', 'TrueNAS encountered a failure during a write operation, which might signal disk problems or connection disruptions.'),
    'ata_bus_error': ('ATA Bus Error', 'Detected on the ATA interface of TrueNAS, suggesting possible issues with the attached storage devices.'),
    'exception_emask': ('Exception Emask', 'For TrueNAS SCALE users, this points to exceptions in the system, potentially related to disk operations or kernel disruptions.'),
    'acpi_error': ('ACPI Error', 'For TrueNAS SCALE, indicates hardware or power management issues, which might impact system performance.'),
    'acpi_exception': ('ACPI Exception', 'For TrueNAS SCALE, highlights unexpected hardware or power configurations that should be checked.'),
    'acpi_warning': ('ACPI Warning', 'For TrueNAS SCALE, points to minor power or hardware concerns, although not critical, they should be reviewed.'),
    'ctl_datamove': ('CTL Datamove', 'For TrueNAS CORE, signifies issues related to moving data in the Common Transport Layer, which might affect iSCSI operations.'),
    'cam_status_error': ('CAM Status Error', 'For TrueNAS CORE, this suggests disruptions in accessing storage devices at the CAM layer.'),
    'scsi_error': ('SCSI Error', 'General SCSI issues on TrueNAS, pointing to problems with connected SCSI devices or the communication bus.'),
    'cdb_errors': ('CDB Errors', 'Errors tied to Command Descriptor Blocks in TrueNAS, hinting at potential SCSI command sequence disruptions.'),
    'iscsi_timeout': ('iSCSI Timeout', 'A lapse in iSCSI communication on TrueNAS, potentially because of target unresponsiveness or network issues.'),
    'iscsi_connect_error': ('iSCSI Connect Error', 'TrueNAS faced problems establishing an iSCSI session or connection, suggesting network or target issues.'),
    'iscsi_session_issues': ('iSCSI Session Issues', 'Challenges related to managing iSCSI sessions on TrueNAS.'),
    'iscsi_kernel_issue': ('iSCSI Kernel Issue', 'For TrueNAS SCALE, signifies disruptions in iSCSI operations at the Linux kernel level.'),
    'iscsi_logout_issue': ('iSCSI Logout Issue', 'TrueNAS encountered errors when logging out of an iSCSI session, hinting at session or target problems.'),
    'cam_status_iscsi_issues': ('CAM Status iSCSI Issues', 'For TrueNAS CORE, this indicates iSCSI issues at the CAM layer, affecting iSCSI operations.'),
    'iscsi_general_errors': ('iSCSI General Errors', 'Broad category for other iSCSI disruptions on TrueNAS.'),
    'nfs_server_not_responding': ('NFS Server Not Responding', 'The NFS service on TrueNAS isnt responding, hinting at service downtimes or network issues.'),
    'nfs_server_ok': ('NFS Server OK', 'The NFS service on TrueNAS, previously unresponsive, has resumed normal operations.'),
    'nfs_stale': ('NFS Stale', 'Points to outdated NFS file handles on TrueNAS, possibly affecting file or directory access.'),
    'nfs_portmap_issue': ('NFS Portmap Issue', 'For TrueNAS CORE, suggests issues with the NFS port mapper service, potentially affecting client connections.'),
    'nfs_timed_out': ('NFS Timed Out', 'NFS operations on TrueNAS exceeded the allowed time, hinting at server-side or client-side issues.'),
    'nfs_retrying': ('NFS Retrying', 'TrueNAS is retrying a previously failed NFS operation, suggesting transient errors.'),
    'nfs_mount_issue': ('NFS Mount Issue', 'Problems encountered when mounting NFS shares on TrueNAS, pointing to configuration or network issues.'),
    'freebsd_nfs_timed_out': ('FreeBSD NFS Timed Out', 'For TrueNAS CORE, an NFS operation took longer than expected, suggesting performance or connection concerns.')
}

ERROR_SEVERITIES = {
    'hard_resetting_link': 'high',
    'failed_command_read': 'high',
    'failed_command_write': 'high',
    'ata_bus_error': 'moderate',
    'exception_emask': 'high',
    'acpi_error': 'moderate',
    'acpi_exception': 'moderate',
    'acpi_warning': 'low',
    'ctl_datamove': 'moderate',
    'cam_status_error': 'high',
    'scsi_error': 'high',
    'cdb_errors': 'moderate',
    'iscsi_timeout': 'moderate',
    'iscsi_connect_error': 'high',
    'iscsi_session_issues': 'moderate',
    'iscsi_kernel_issue': 'high',
    'iscsi_logout_issue': 'moderate',
    'cam_status_iscsi_issues': 'high',
    'iscsi_general_errors': 'moderate',
    'nfs_server_not_responding': 'high',
    'nfs_server_ok': 'low',
    'nfs_stale': 'moderate',
    'nfs_portmap_issue': 'moderate',
    'nfs_timed_out': 'high',
    'nfs_retrying': 'low',
    'nfs_mount_issue': 'moderate',
    'freebsd_nfs_timed_out': 'high'
}
for key, value in ERROR_DESCRIPTIONS.items():
    title, description = value
    severity_key = ERROR_SEVERITIES.get(key, 'high')  # defaulting to high if not specified
    new_description = f"{SEVERITIES[severity_key]} - {description}"
    ERROR_DESCRIPTIONS[key] = (title, new_description)

# -----------------------------------------------
# End Severities List
# -----------------------------------------------
def write_content_status(content):
    with open('report.txt', 'w') as file:  # Appending to report.txt, if you don't want to overwrite, change 'w' to 'a'
        file.write(content + '\n\n')  # Writing content followed by two newlines

# Email Validation Function
def validate_email(email):
    # Regex for a simple email validation
    email_regex = r"[^@]+@[^@]+\.[^@]+"
    return bool(re.match(email_regex, email))

def safe_read_previous_errors():
    try:
        # Call the function read_previous_errors() to retrieve previous errors
        return read_previous_errors()
    except Exception as e:
        # If an exception occurs, log the error message and return an empty dictionary
        logging.error(f"Error reading previous errors: {e}")
        return {}
def read_previous_errors():
    if os.path.isfile(ERRORS_FILE):
        with open(ERRORS_FILE, "r") as file:
            return json.load(file)
    return {}

def get_os_version():
    try:
        # Execute the command "cat /etc/os-release" and capture the output
        os_version_output = subprocess.check_output(["cat", "/etc/os-release"], text=True).strip()

        # Extract the PRETTY_NAME
        pretty_name = None
        for line in os_version_output.split('\n'):
            if "PRETTY_NAME" in line:
                pretty_name = line.split('=')[1].replace('"', '').strip()

        # Initialize os_version as None
        os_version = None

        # Read the version number from /etc/version file
        try:
            with open("/etc/version", "r") as version_file:
                os_version = version_file.read().strip()
        except FileNotFoundError:
            logging.warning("Version file '/etc/version' not found.")

        # Add the appropriate suffix
        if pretty_name:
            if "Debian GNU/Linux" in pretty_name:
                pretty_name += " (TrueNAS SCALE)"
            elif "FreeBSD" in pretty_name:
                pretty_name += " (TrueNAS CORE)"

            output_str = f"TrueNAS SCALE, Version: {os_version} - {pretty_name}"
            return output_str
        else:
            logging.error("Failed to extract PRETTY_NAME from os-release file.")
            return "Unknown OS"

    except subprocess.CalledProcessError as cpe:
        # If there is an error executing the command, log the error message
        logging.error(f"Error executing command: {cpe}")
    except Exception as e:
        # If there is any other unexpected error, log the error message
        logging.error(f"Unexpected error when getting OS version: {e}")
    
    # If any error occurs, return "Unknown OS"
    return "Unknown OS"

def extract_pretty_name(os_version):
    # Extracting the PRETTY_NAME value from os_version
    for line in os_version.split('\n'):
        if "PRETTY_NAME" in line:
            pretty_name = line.split('=')[1].replace('"', '').strip()
            return pretty_name
    return None

def search_log_file(os_version):
    matches = []
    repeat_errors = []
    previous_errors = safe_read_previous_errors()  # Initializing previous_errors
    match_counts = {k: 0 for k in [
        "cdb_errors",
        "iscsi_timeout",
        "iscsi_connect_error",
        "iscsi_session_issues",
        "iscsi_kernel_issue",
        "iscsi_logout_issue",
        "ctl_datamove",
        "cam_status_error",
        "cam_status_iscsi_issues",
        "iscsi_general_errors",
        "scsi_error",
        "hard_resetting_link",
        "failed_command_read",
        "failed_command_write",
        "ata_bus_error",
        "exception_emask",
        "acpi_error",
        "acpi_exception",
        "acpi_warning",
        "nfs_server_not_responding",
        "nfs_server_ok",
        "nfs_stale",
        "nfs_portmap_issue",
        "nfs_timed_out",
        "nfs_retrying",
        "nfs_mount_issue",
        "freebsd_nfs_timed_out"
]}
    error_patterns = [
        ERROR_PATTERN_CDB_ERRORS,
        ERROR_PATTERN_ISCSI_TIMEOUT,
        ERROR_PATTERN_ISCSI_CONNECT_ERROR,
        ERROR_PATTERN_ISCSI_SESSION_ISSUES,
        ERROR_PATTERN_ISCSI_KERNEL_ISSUE,
        ERROR_PATTERN_ISCSI_LOGOUT_ISSUE,
        ERROR_PATTERN_CTL_DATAMOVE,
        ERROR_PATTERN_CAM_STATUS_ERROR,
        ERROR_PATTERN_CAM_STATUS_ISCSI_ISSUES,
        ERROR_PATTERN_ISCSI_GENERAL_ERRORS,
        ERROR_PATTERN_SCSI_ERROR,
        ERROR_PATTERN_HARD_RESETTING_LINK,
        ERROR_PATTERN_FAILED_COMMAND_READ,
        ERROR_PATTERN_FAILED_COMMAND_WRITE,
        ERROR_PATTERN_ATA_BUS_ERROR,
        ERROR_PATTERN_EXCEPTION_EMASK,
        ERROR_PATTERN_ACPI_ERROR,
        ERROR_PATTERN_ACPI_EXCEPTION,
        ERROR_PATTERN_ACPI_WARNING,
        ERROR_PATTERN_NFS_SERVER_NOT_RESPONDING,
        ERROR_PATTERN_NFS_SERVER_OK,
        ERROR_PATTERN_NFS_STALE,
        ERROR_PATTERN_NFS_PORTMAP,
        ERROR_PATTERN_NFS_TIMED_OUT,
        ERROR_PATTERN_FREEBSD_NFS_TIMED_OUT,
        ERROR_PATTERN_NFS_RETRYING,
        ERROR_PATTERN_NFS_MOUNT_ISSUE,
        ERROR_PATTERN_NFS_ACCESS_DENIED
    ]
    with open('/var/log/messages', 'r', errors='ignore') as file:
        for i, line in enumerate(file):
            line_lower = line.lower()  # Convert the line to lowercase for case-insensitive matching
            for pattern_tuple in error_patterns:
                pattern, errors, ignored, count_key = pattern_tuple

                if pattern in line_lower and any(error in line_lower for error in errors) and not any(ignore in line_lower for ignore in ignored):
                    # Get the surrounding lines
                    match = "".join([file.readline() for _ in range(3)]).strip()
                    matches.append(match)
                    # Increment the respective counter in the match_counts dictionary
                    match_counts[count_key] += 1

    for match in matches:
        # Assuming the timestamp is at the beginning of each log entry
        timestamp = match.split()[0]
        if match in previous_errors and previous_errors[match] == timestamp:
            repeat_errors.append(match)
        else:
            previous_errors[match] = timestamp  # Update or add the new error with its timestamp

    save_errors(previous_errors)

    return matches, match_counts, repeat_errors
def save_errors(errors):
    with open(ERRORS_FILE, 'w') as file:
        json.dump(errors, file)
    # Return the 'matches' list and the 'match_counts' dictionary as the result

def get_error_info(error_key):
    # Fetching the error title and combined description (which includes severity)
    error_title, combined_description = ERROR_DESCRIPTIONS.get(error_key, ("Unknown Error", "No description available"))
    
    # Separating severity from description. We assume the format is "Severity - Description"
    parts = combined_description.split(' - ', 1)
    if len(parts) == 2:
        severity, description = parts
    else:
        # Handle edge case where the split didn't work (maybe the description doesn't include severity)
        severity = "Unknown Severity"
        description = combined_description

    return error_title, description, severity

def generate_table(match_counts, os_version, log_entries):
    previous_errors = safe_read_previous_errors()

    separator = "#" * 50
    section_separator = "=" * 50

    table = f"Spencer Results\n{separator}\nVersion: {os_version}\n\n{separator}\n\n"

    # Distinguishing between new errors and previous errors based on the JSON file.
    prev_errors_from_logs = {k: v for k, v in match_counts.items() if k in previous_errors and previous_errors[k] >= v}
    missing_prev_errors = {k: v for k, v in previous_errors.items() if k not in match_counts}

    # If no new errors but there are previous errors in the log, indicate that.
    if not match_counts and (prev_errors_from_logs or missing_prev_errors):
        table += f"{PREV_ERROR_SUBJECT}\n\n{separator}\n\n"
    elif not match_counts and not (prev_errors_from_logs or missing_prev_errors):
        table += f"{SUCCESS_SUBJECT}\n\n{separator}\n\n"
        return table  # We can return early as no further information is needed for the success case.
    elif match_counts:
        table += f"{ERROR_SUBJECT}\n\n{separator}\n\n"

    def generate_error_section(errors_data, section_title):
        section_output = f"{section_title}\n{section_separator}\n\n"
        for error_key in errors_data.keys():  # Loop over the keys of the errors_data dictionary
            error_count = errors_data.get(error_key, 0)  # Use the error count or default to 0
            error_name, error_description, severity = get_error_info(error_key)
            section_output += f"{error_name} {'-'*(40-len(error_name))} [{error_count}] ----- [{severity}]\n"
            section_output += f"{error_description}\n\n"
        section_output += f"\n{section_separator}\n\n"
        return section_output

    table += generate_error_section(match_counts, "=====NEWLY FOUND ERRORS===========================")
    table += generate_error_section({**prev_errors_from_logs, **missing_prev_errors}, "=====Previously Found Errors=================")

    table += f"\n{separator}\nCorresponding Log Entries with Timestamps:\n{separator}\n"
    for entry in log_entries:
        table += entry + "\n"

    save_errors(match_counts)

    return table

def safe_send_email(content, to_address, subject):
    # Check if the email address is valid
    if not validate_email(to_address):
        print(f"{datetime.datetime.now()} - Failed to send email: Invalid email address '{to_address}'")
        logging.error(f"Invalid email address: {to_address}")
        return
    try:
        # Attempt to send the email
        send_email(content, to_address, subject)
    except Exception as e:
        print(f"{datetime.datetime.now()} - Failed to send email due to an exception: {e}")
        logging.error(f"Error sending email: {e}")

def send_email(content, to_address, subject):
    email_message = f"From: {DEFAULT_RECIPIENT}\nTo: {to_address}\nSubject: {subject}\n\n{content}"
    sendmail_command = ["sendmail", "-t", "-oi"]
    with subprocess.Popen(sendmail_command, stdin=subprocess.PIPE) as process:
        process.communicate(email_message.encode())
        print(f"{datetime.datetime.now()} - Email was sent successfully!")


def write_to_file(file, content):
    # Writing the content to a file
    with open(file, "w") as f:
        f.write(content)

# Read previously found errors from a fil       
def read_previous_errors():
    # Loading previous errors from a JSON file if it exists, otherwise returning an empty dictionary
    if os.path.isfile(ERRORS_FILE):
        with open(ERRORS_FILE, 'r') as f:
            return json.load(f)
    else:
        return {}

def write_to_file(file, content):
    # Writing the content to a file
    with open(file, "w") as f:
        f.write(content)

os_version = get_os_version()
print(f"{datetime.datetime.now()} - Operating System version determined: {os_version}")

matches, match_counts, repeat_errors = search_log_file(os_version)
print(f"{datetime.datetime.now()} - Found {len(matches)} new matching errors in the logs")

previous_errors = read_previous_errors()
print(f"{datetime.datetime.now()} - Loaded {len(previous_errors)} previous errors from the error file")

write_to_file(ERRORS_FILE, json.dumps(match_counts))
print(f"{datetime.datetime.now()} - Wrote the current error counts to the error file")

table_content = generate_table(match_counts, os_version, matches)
print(f"{datetime.datetime.now()} - Generated the error table for the email content")

# We have removed the error_message portion since that has now been incorporated into generate_table.
content = table_content

new_errors_exist = matches and any(count > previous_errors.get(error, 0) for error, count in match_counts.items())

# Determine the subject of the email based on the presence of new errors or previous errors
if new_errors_exist:
    subject = ERROR_SUBJECT
elif any(previous_errors.values()):
    subject = PREV_ERROR_SUBJECT
else:
    subject = SUCCESS_SUBJECT
print(f"{datetime.datetime.now()} - Selected email subject: {subject}")

# Print informational messages
if not matches:
    print(f"{datetime.datetime.now()} - No matching errors found in the logs.")
if not any(previous_errors.values()):
    print(f"{datetime.datetime.now()} - No previous errors exist.")

# Handle email sending or file writing based on USE_WITH_MULTI_REPORT
if USE_WITH_MULTI_REPORT == "multi_report":
    print(f"{datetime.datetime.now()} - Email sending is skipped due to USE_WITH_MULTI_REPORT setting.")
    with open(CONTENT_FILE, 'w') as f:
        selected_message = 'New Error Messages\n' if new_errors_exist else 'Previous Errors\n' if any(previous_errors.values()) else 'No Errors\n'
        f.write(f"{selected_message}{content}")
else:
    safe_send_email(content, to_address, subject)
