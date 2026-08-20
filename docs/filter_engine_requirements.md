# Filter Engine — Requirements Summary

Status: **requirements gathered, not yet designed/implemented.** This document
captures what was learned from the developer about real-world filter needs,
so the filter engine (the biggest item in CLAUDE.md's Known open items) can
be designed against reality instead of guesses. Nothing here should be built
without a follow-up technical design pass and the developer's sign-off.

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
- Free-text "contains a string" matching — mentioned as a real limitation of
  Salesforce's own filters and a good candidate for this app to solve, but
  no concrete example was gathered yet.
- Arbitrarily nested AND/OR groups — only flat combinations have come up in
  examples so far; may not be needed.

## Not yet decided (next design pass)

- How a filter is actually represented/stored (schema for `Action.filters`)
- How the AND/OR UI works for the professor building an action
- Whether "day of week" and "N days ago" are separate operator types or one
  generalized date-comparison system
- Where the task-number heuristic actually lives in code, if built at all
