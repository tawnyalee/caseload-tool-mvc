# Filter Engine — Requirements Summary

Status: **field-by-field disposition pass is complete** (see "Field-by-field
disposition" below) except `phone`, which is blocked on the developer
checking with colleagues about a possible Cadence-ID-based texting
integration. Requirements are gathered but **not yet designed/implemented**
as an actual filter engine — nothing here should be built without a
follow-up technical design pass and the developer's sign-off.

## Why this matters

`Action.filters` already exists on the model and is configurable in the UI,
but `ActionRunner.run()` never applies it — running any action currently
sends to the entire roster (confirmed by reading the code directly). Filters
are the actual blocker behind targeted actions, welcome emails, and the
generic-outreach-rotation idea all being practically correct rather than
"send to everyone."

The developer's underlying goal: professors handle a rolling-enrollment
caseload (students start/end courses continuously, no fixed cohorts) and
need to routinely find "who needs X" without relying entirely on Salesforce's
own (limited) filtering — some of what's needed (custom day thresholds,
day-of-week checks, free-text matching) Salesforce's UI can't do at all,
which is part of the motivation for building this into the app itself.

## Confirmed real-world filter examples

- Daily welcome-email check: `CourseFollowupNote` Is Empty (plus course
  identification — see "Equality" below)
- `CourseCode` = "D424" (single course)
- `CourseCode` = X **and** `CourseVersion` = Y (compound — same course code
  can have multiple versions)
- `Momentum` = one of: Low / Med Low / Med / Med High / High
- `DaysSinceLastCourseContact` > 10 (arbitrary day count — Salesforce only
  offers presets like "last 7 days," not a custom number)
- `Momentum` = Low **and** `DaysSinceLastCourseContact` > 10 (compound,
  AND)
- "Any student who submitted a task" — presence check across `Task1`...`Task15`
- Task-specific: e.g. "students who just passed Task 2" — see Task fields
  section below, this is more involved than a simple field check
- "Revisions Needed" (Salesforce's real status string; the professor's term
  for it is "failed but can resubmit") sitting unresolved for 14+ days
- Day-of-week: "did a task get marked Passed over the weekend" — Salesforce
  cannot express this at all; the app can (`date.weekday()`), so this is a
  clean value-add over what the developer has today

## Field-by-field disposition (complete, except `phone`)

Went through every `Student` field category by category with the developer
to decide: filterable (and how), stored-but-not-filterable, or removed
entirely. All categories are settled except `phone` (blocked on outside
research, see Identity/Contact below).

**Removed from `Student` entirely** (not needed by the app at all):
`affiliation`, `planned_graduation_date`, `student_graduation_goal`,
`weeks_in_course`, `contact_term`, `city`, `is_minor`, `affiliation_code`,
`mentor_name`, `course_mentor`, `enrolled_cu`, `term_completed_cu`,
`total_sap`, `term_otp_status`. (All of these have already been removed
from the code, not just flagged here.)

**Identity / Contact:**
| Field | Disposition |
|---|---|
| `salesforce_id` | Filterable — exact match against user-typed input |
| `first_name` | Filterable — exact match against user-typed input |
| `last_name` | Filterable — exact match against user-typed input |
| `email` | Stored, not filterable |
| `phone` | **Pending — blocked on outside research.** Removing it would break texting (`ActionRunner`/`TextSender` currently send to `student.phone` directly). Developer recalls other similar apps identify students to Cadence (the texting platform) via a stored "Mongoose Cadence ID" rather than a raw phone number, but isn't certain this is a real Salesforce field (it's not present in `Sample.csv`) or exactly how it works — checking with people who've built that integration before. If confirmed, this would change `TextSender`'s interface itself (send a Cadence ID instead of a phone number), not just `Student`. Don't build anything here until that's back. |
| `has_signed_up_for_text` | Stored, not filterable |
| `texting_preference` | Stored, not filterable |
| `timezone` | Stored, not filterable |
| `city` | Removed (see above) |
| `is_minor` | Removed (see above) |

**Program / course identity:**
| Field | Disposition |
|---|---|
| `program_code` | Filterable — Equals, dropdown of live distinct values (see below) |
| `program_name` | Filterable — Equals, dropdown of live distinct values |
| `program_version` | Filterable — Equals, dropdown of live distinct values |
| `course_code` | Filterable — Equals, dropdown of live distinct values |
| `course_version` | Filterable — Equals, dropdown of live distinct values |
| `course_status` | Filterable — Equals, dropdown of live distinct values |
| `affiliation_code` | Removed — not important, never really used |

**Dates / term timeline:**
| Field | Disposition |
|---|---|
| `course_start_date` | Filterable — date operators (see below) |
| `course_end_date` | Filterable — date operators |
| `term_start_date` | Filterable — date operators |
| `term_end_date` | Filterable — date operators |
| `term_break_end_date` | Filterable — date operators |
| `actual_start_date` | Filterable — date operators |
| `assignment_start_date` | Filterable — date operators |
| `term_days_left` | Filterable — **numeric**, not a date (values are plain day counts like "104", "13"). Operators: Equals, Greater Than, Greater Than or Equal To, Less Than, Less Than or Equal To — user enters the number. Same pattern as `DaysSinceLastCourseContact`. |

**Date operators** (applies to every genuine date field across all
categories — retroactively includes the ones settled earlier too):
`Equals`, `Before`, `On or Before`, `After`, `On or After`, `Between`
(range), plus two more confirmed useful given Salesforce's own date
filters only offer fixed presets (last 3/7 days, last month) and can't do
a custom day count:
- **Relative-to-today with a custom number** — e.g. "ends within the next
  N days" or "started more than N days ago." Directly addresses the same
  Salesforce limitation as the custom day-count need on
  `DaysSinceLastCourseContact`.
- **Is Empty / Is Not Empty** — several of these fields are commonly blank
  for a given student (e.g. `assignment_start_date`, `term_break_end_date`
  when a student isn't on break), same pattern as `CourseFollowupNote`.

**Numeric operators** (applies to every numeric-as-string field, e.g.
`days_since_last_course_contact`, `term_days_left`): `Equals`, `Greater
Than`, `Greater Than or Equal To`, `Less Than`, `Less Than or Equal To`,
plus `Is Empty` where relevant.

**Contact / outreach tracking:**
| Field | Disposition |
|---|---|
| `course_contact` | Filterable — date operators. Raw value is a full datetime (`2026-08-17T20:07:30.000Z`), not a plain date — comparisons need to work on the date portion, not require an exact time-of-day match. |
| `last_sm_contact` | Filterable — date operators. Same datetime-with-time-of-day format as `course_contact`. |
| `my_course_contact` | Filterable — date operators. Plain date, no time component. |
| `last_academic_activity_date` | Filterable — date operators. Plain date, no time component. |
| `days_since_last_course_contact` | Filterable — numeric operators (see above), including Is Empty |
| `course_followup_note` | Filterable — **Contains** (substring match, any position in the text, not a dropdown — real data has 30+ distinct values in just this 252-row sample, including one-off free text, so a live-values dropdown isn't practical here), plus Is Empty / Is Not Empty |
| `mentor_name` | Removed — not important to this app |
| `course_mentor` | Removed — not important to this app |
| `student_status` | Filterable — Equals, against a **small hand-maintained list of known codes** (not a live-data dropdown, since new codes are rare and the current data sample doesn't even contain all real values). Confirmed so far: `AS` = Active Student, `TB` = Term Break (a mentor might filter for this to email everyone currently on a term break). More codes can be added to this list later as they come up. |

**Momentum / credit / SAP:**
| Field | Disposition |
|---|---|
| `momentum` | Filterable — Equals, fixed known list: `Low`, `Med Low`, `Med`, `Med High`, `High` (exact casing confirmed against `Sample.csv`) |
| `term_remaining_cu` | Filterable — numeric operators (see above) |
| `term_sap` | Filterable — numeric operators |
| `enrolled_cu` | Removed — unlikely to ever be needed |
| `term_completed_cu` | Removed — unlikely to ever be needed |
| `total_sap` | Removed — unlikely to ever be needed |
| `term_otp_status` | Removed — unlikely to ever be needed |

**Tasks:**
| Field | Disposition |
|---|---|
| `task_1` ... `task_15` | Filterable — date operators + Is Empty/Is Not Empty. Values are the composite `"date (attempt)"` format, not a plain date — needs the date portion parsed out before comparing. |
| `latest_task` | Stored, not filterable — its pieces (`latest_task_date`, `latest_task_attempts`, `latest_task_status`) are already separately available, so the raw combined field has no filtering need of its own; app logic may still use it internally. |
| `latest_task_status` | Filterable — Equals against fixed known values: `Passed`, `Task Submitted`, `Revisions Needed`, `Evaluation Started`, plus Is Empty/Is Not Empty |
| `latest_task_date` | Filterable — date operators + Is Empty/Is Not Empty (plain date, no attempt suffix) |
| `latest_task_attempts` | Stored, not filterable — not needed for this app's scope (general batch outreach, not one-on-one case management); could be added in a future version if that changes |
| `latest_task_date_yesterday` | Filterable — boolean (`TRUE`/`FALSE`) equality. **Important**: this only means "latest task activity happened yesterday," not "passed yesterday" — "who passed a task yesterday" needs this ANDed with `latest_task_status = Passed`, not used alone. |
| `number_of_days_since_last_task_date` | Filterable — numeric operators, same pattern as `days_since_last_course_contact` (lets you find students who haven't resubmitted and may need a nudge) |
| `latest_task_number` (computed) | Filterable — Equals against a specific task number, e.g. to target "just passed Task 2" style actions |

**The "did they actually pass" logic** (why `latest_task_status` matters so
much): a `TaskN` field having a date only means the task was *submitted*,
not that it passed — Salesforce's own UI (the task turning green) is
unreliable and not always real-time. The correct way to know "student X
just passed task 2" is three conditions ANDed together: `task_2` has a
date in the target window, `task_3` is still empty (task_2 really is their
current task), and `latest_task_status` = `Passed` (confirms it wasn't
sent back for revisions). No special task-aware filter-engine feature is
needed for this — it's an ordinary multi-condition AND filter on regular
fields, which is exactly why AND/OR support matters so much for this app.

**Assessments (pre-assessment + objective assessment):**
| Field | Disposition |
|---|---|
| `last_pre_assessment_date` | Filterable — date operators + Is Empty/Is Not Empty |
| `last_pre_assessment_actual_date` | Filterable — date operators + Is Empty/Is Not Empty |
| `last_pre_assessment_status` | Filterable — Equals against fixed known values: `Passed`, `Not Passed` (confirmed binary, no other states), plus Is Empty/Is Not Empty |
| `last_objective_assessment_date` | Filterable — date operators + Is Empty/Is Not Empty |
| `last_objective_assessment_actual_date` | Filterable — date operators + Is Empty/Is Not Empty |
| `last_objective_assessment_status` | Filterable — Equals against fixed known values: `Passed`, `Not Passed` (confirmed binary, no other states believed to exist), plus Is Empty/Is Not Empty |

**Why `last_objective_assessment_status = Passed` is rare in real data**:
courses with only one OA (the vast majority of OA courses — there's never
more than one OA per course) automatically remove a student from the
roster as soon as they pass it. So `Passed` only persists in the data for
mixed OA+task courses, where the student stays on the roster until *both*
the OA and all tasks are passed. This isn't a data-quality issue or a
sampling gap — it's structural. Similarly, tasks (PAs) drop a student from
the roster once *all* of that course's tasks are passed (course task
counts range from 1 to 15). What actually matters for OA filtering is
surfacing *failures* (`Not Passed`) — a scheduled-but-not-yet-taken OA
isn't something this app needs to distinguish.

**New UI requirement surfaced by this category**: for "set value" fields
like these (as opposed to genuinely free-text fields), the Equals filter's
value picker must be a **dropdown populated from whatever distinct values
actually exist in the pulled data at the time**, not free-typed text and
not a hardcoded list — the developer's reasoning: these are fields with a
fixed set of real values, and free-typing invites a typo that silently
makes the filter match nothing, with no obvious error. This is a different
UI pattern than `Momentum`, where the ~5 possible values are already known
and fixed; here the actual set of course codes/names/versions/statuses can
change over time as new courses get added, so it must be computed live,
not hardcoded once.

## Field types identified and what they need

| Field type | Examples | Operators needed |
|---|---|---|
| Free text | `CourseFollowupNote` | Is Empty / Is Not Empty (developer specifically wants string-contains eventually — Salesforce can't do this, but no concrete "contains" example was given yet) |
| Picklist / fixed values | `Momentum` (Low/Med Low/Med/Med High/High), `CourseStatus`, `LatestTaskStatus` (Passed / Task Submitted / Revisions Needed / Evaluation Started / blank — **confirmed complete list**, though one malformed row had a raw date in this field instead of a status — defensive handling needed for bad real-world data) | Equals, one-of-several-values |
| Numeric-as-string | `DaysSinceLastCourseContact`, `EnrolledCU`, etc. (all `Student` fields are currently plain strings — see `src/models/student.py`) | Greater than / less than a custom value (not a Salesforce preset) |
| Date | `CourseStartDate`, `LatestTaskDate`, etc. | Custom "more than N days ago" (not a preset range), and **day-of-week** (e.g. "fell on a Saturday or Sunday") |
| Task fields (`Task1`...`Task15`) | Flat, not normalized — one field per task number, holds a `"date (attempt#)"` string if submitted, blank if not. No per-task status is retained — see below. | Is Empty / Is Not Empty per named task field; date comparisons same as any date field |

## Combining conditions

**AND/OR is required whenever a filter has more than one condition** — this
was explicit and unconditional, not a "nice to have." No confirmation yet on
whether arbitrary nested groups are needed or a flat AND/OR-joined list is
enough in practice; only flat, 2-3-condition examples have come up so far.

## Task fields — a real data-model limitation, not something to over-engineer around

- `Task1`...`Task15` are flat fields, filled with a date the moment a task is
  *submitted* (not necessarily passed). Blank = never submitted.
- Salesforce separately provides `LatestTask`, `LatestTaskStatus`,
  `LatestTaskDate`, `LatestTaskAttempts` — confirmed (by inspecting
  `Sample.csv`) that these already describe whichever `TaskN` is the
  highest-numbered non-blank one. The developer didn't know these fields
  already did this.
- **The real limitation**: these "Latest" fields only capture *one* current
  status/date, with no separate history per task number. If a student
  submits multiple tasks in one batch (happens sometimes, against the
  intended one-at-a-time flow), there is no field that reliably says
  "Task 3 specifically got Revisions Needed" versus "Task 4 did." This is a
  genuine Salesforce data-model gap, not something a filter can work around.
- **Agreed approach**: for the common case (tasks submitted one at a time),
  a heuristic can identify the task number — scan `Task1`...`Task15` for
  whichever field's date matches `LatestTaskDate` exactly. In the edge case
  (batched submissions), this heuristic can be wrong.
- **Decision**: the developer will do a quick visual check before sending
  anything task-specific, rather than trusting an automated task-number
  guess blindly. This matches how they already resolve this ambiguity
  manually today, so the app is only removing the "who might qualify" search
  step, not the final human confirmation step.
- Separately, when setting up an action for "just passed Task N," the
  professor already knows N when building that specific action (one action
  per task transition is the intended usage) — so most of the time, no
  automatic task-number detection is even needed; it's a plain filter on a
  specific, professor-chosen `TaskN` field. The heuristic above is only
  relevant for the "which task needs revisions" case, where the task number
  isn't known in advance.

## Data quality notes (`Sample.csv` only — resolved)

- One row (StudentID `000000154`) had every field from `LatestTask` onward
  holding wrong/garbled values (e.g. `LatestTaskStatus` held a raw date).
  Initially misdiagnosed as a CSV-quoting defect (an unescaped comma inside
  `LatestCourseNote` splitting one field into two) — that theory turned out
  to be wrong: the row had exactly the right number of CSV fields throughout
  (verified directly), so this wasn't a parsing artifact at all. The values
  were already wrong at the byte level in the source export, while
  remaining syntactically valid CSV — i.e. genuine corruption in that one
  record, not a systemic pattern. **Resolved** by deleting the one affected
  row (fake/masked test data, not a real record, so no data was lost) and
  regenerating `data/fake_students.json` (252 students now).
- Separately, `LatestCourseNote` (a free-text field, not needed by the app)
  was dropped from `Sample.csv` entirely and removed from `Student` /
  `Student.SALESFORCE_FIELD_MAP` — it no longer exists anywhere.
- Important scoping note from the developer: **this app is not expected to
  ever ingest downloaded Salesforce CSV exports in production** — `Sample.csv`
  exists purely to get realistic field names/shapes for building fake test
  data; the real integration is expected to go through the Salesforce API
  directly. So CSV-export data-quality issues like this one are a one-time
  test-fixture cleanup concern, not something the filter engine or a real
  adapter needs to defend against on an ongoing basis. If a real CSV-import
  path is ever added later, this would need revisiting.
- Course task counts vary from 2 to 15 across the developer's own courses
  (some other courses at the institution have just 1, though none of the
  developer's do) — any task-related logic needs to work across that whole
  range without per-course configuration, e.g. by scanning until an empty
  field is hit rather than assuming a fixed count.

## Explicitly out of scope for this pass

- Automatic task-number detection in ambiguous (batched-submission) cases —
  human visual check instead, by agreement.
- Arbitrarily nested AND/OR groups — only flat combinations have come up in
  examples so far; may not be needed.

## Not yet decided (next design pass)

- How a filter is actually represented/stored (schema for `Action.filters`)
- How the AND/OR UI works for the professor building an action
- Whether "day of week" and "N days ago" are separate operator types or one
  generalized date-comparison system
- Where the task-number heuristic actually lives in code, if built at all
