# src/models/student.py
from dataclasses import dataclass, field


@dataclass
class Student:
    """A student roster record.

    salesforce_id, first_name, last_name, email, phone, has_signed_up_for_text
    are the original core fields. Everything else was added to mirror the
    caseload export field-by-field (see SALESFORCE_FIELD_MAP) so filters can
    eventually be built against the same fields a professor sees in
    Salesforce. All of the added fields are kept as raw strings on purpose —
    type-aware filtering (dates, numbers, booleans) is a separate, not-yet-
    designed concern (see CLAUDE.md "Filters are NOT implemented yet").
    """

    salesforce_id: str
    first_name: str
    last_name: str
    email: str
    phone: str = ""
    has_signed_up_for_text: bool = False

    program_code: str = ""
    course_code: str = ""
    course_version: str = ""
    momentum: str = ""
    course_followup_note: str = ""
    course_start_date: str = ""
    course_end_date: str = ""
    course_contact: str = ""
    term_end_date: str = ""
    task_1: str = ""
    task_2: str = ""
    task_3: str = ""
    task_4: str = ""
    last_pre_assessment_date: str = ""
    last_objective_assessment_date: str = ""
    mentor_name: str = ""
    course_mentor: str = ""
    days_since_last_course_contact: str = ""
    contact_term: str = ""
    term_completed_cu: str = ""
    my_course_contact: str = ""
    actual_start_date: str = ""
    affiliation: str = ""
    affiliation_code: str = ""
    assignment_start_date: str = ""
    city: str = ""
    course_status: str = ""
    enrolled_cu: str = ""
    is_minor: str = ""
    latest_task_date_yesterday: str = ""
    last_academic_activity_date: str = ""
    last_objective_assessment_actual_date: str = ""
    last_pre_assessment_actual_date: str = ""
    last_pre_assessment_status: str = ""
    last_objective_assessment_status: str = ""
    last_sm_contact: str = ""
    latest_task: str = ""
    latest_task_attempts: str = ""
    latest_task_date: str = ""
    latest_task_status: str = ""
    number_of_days_since_last_task_date: str = ""
    program_name: str = ""
    program_version: str = ""
    planned_graduation_date: str = ""
    term_remaining_cu: str = ""
    student_graduation_goal: str = ""
    student_status: str = ""
    task_5: str = ""
    task_6: str = ""
    task_7: str = ""
    task_8: str = ""
    task_9: str = ""
    task_10: str = ""
    task_11: str = ""
    task_12: str = ""
    task_13: str = ""
    task_14: str = ""
    task_15: str = ""
    term_break_end_date: str = ""
    term_days_left: str = ""
    term_otp_status: str = ""
    term_sap: str = ""
    term_start_date: str = ""
    texting_preference: str = ""
    timezone: str = ""
    total_sap: str = ""
    weeks_in_course: str = ""

    # snake_case attribute name -> raw column name from the caseload export
    # (which mirrors the underlying Salesforce field/API names). Kept so a
    # real Salesforce read/write adapter, built later, knows exactly which
    # Salesforce field each attribute came from. salesforce_id, email, and
    # phone map from StudentID, StudentEmail, and MobilePhone respectively;
    # first_name/last_name are synthesized from the export's "stuprename"
    # (preferred name) and "Name" columns rather than a 1:1 field, so they
    # aren't listed here.
    SALESFORCE_FIELD_MAP = {
        "salesforce_id": "StudentID",
        "email": "StudentEmail",
        "phone": "MobilePhone",
        "program_code": "Programcode",
        "course_code": "CourseCode",
        "course_version": "CourseVersion",
        "momentum": "Momentum",
        "course_followup_note": "CourseFollowupNote",
        "course_start_date": "CourseStartDate",
        "course_end_date": "CourseEndDate",
        "course_contact": "CourseContact",
        "term_end_date": "TermEndDate",
        "task_1": "Task1",
        "task_2": "Task2",
        "task_3": "Task3",
        "task_4": "Task4",
        "last_pre_assessment_date": "LastPreAssessmentDate",
        "last_objective_assessment_date": "LastObjectiveAssessmentDate",
        "mentor_name": "MentorName",
        "course_mentor": "CourseMentor",
        "days_since_last_course_contact": "DaysSinceLastCourseContact",
        "contact_term": "contactterm",
        "term_completed_cu": "TermCompletedCU",
        "my_course_contact": "MyCourseContact",
        "actual_start_date": "ActualStartDate",
        "affiliation": "Affiliation",
        "affiliation_code": "AffiliationCode",
        "assignment_start_date": "caseload.AssignmentStartDate__c",
        "city": "City",
        "course_status": "CourseStatus",
        "enrolled_cu": "EnrolledCU",
        "is_minor": "IsMinor",
        "latest_task_date_yesterday": "LatestTaskDateYesterday",
        "last_academic_activity_date": "LastAcademicActivityDate",
        "last_objective_assessment_actual_date": "LastObjectiveAssessmentActualDate",
        "last_pre_assessment_actual_date": "LastPreAssessmentActualDate",
        "last_pre_assessment_status": "LastPreAssessmentStatus",
        "last_objective_assessment_status": "LastObjectiveAssessmentStatus",
        "last_sm_contact": "LastSMContact",
        "latest_task": "LatestTask",
        "latest_task_attempts": "LatestTaskAttempts",
        "latest_task_date": "LatestTaskDate",
        "latest_task_status": "LatestTaskStatus",
        "number_of_days_since_last_task_date": "NumberOfDaysSinceLastTaskDate",
        "program_name": "ProgramName",
        "program_version": "ProgramVersion",
        "planned_graduation_date": "PlannedGraduationDate",
        "term_remaining_cu": "TermRemainingCU",
        "student_graduation_goal": "StudentGraduationGoal",
        "student_status": "StudentStatus",
        "task_5": "Task5",
        "task_6": "Task6",
        "task_7": "Task7",
        "task_8": "Task8",
        "task_9": "Task9",
        "task_10": "Task10",
        "task_11": "Task11",
        "task_12": "Task12",
        "task_13": "Task13",
        "task_14": "Task14",
        "task_15": "Task15",
        "term_break_end_date": "TBenddate",
        "term_days_left": "TermDaysLeft",
        "term_otp_status": "TermOTPStatus",
        "term_sap": "TermSAP",
        "term_start_date": "TermStartDate",
        "texting_preference": "TextingPreference",
        "timezone": "Timezone",
        "total_sap": "TotalSAP",
        "weeks_in_course": "weeksincourse",
    }

    @property
    def full_name(self) -> str:
        """Returns the student's full name."""
        return f"{self.first_name} {self.last_name}"
