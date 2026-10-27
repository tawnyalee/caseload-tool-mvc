# Caseload Tool — Professor Guide

The Caseload Tool sends your routine student outreach for you: it emails students from your own Outlook, then writes the matching note in Salesforce. You decide who gets what with Actions and filters, and you review every send before anything goes out.

> This guide is also inside the app: click **❓ Help** at any time.

## Before you start

You need all of these on your computer:

- **Windows** with **Microsoft Edge** (already installed on WGU computers).
- **Outlook (classic)**, signed in to your WGU email. *Not* the "New Outlook" — see "Stay on Outlook (classic)" below.
- **Your email signature set up in Outlook (classic)** (File → Options → Mail → Signatures). The app uses it on every email.
- **Salesforce access** with **PingID on your phone**, since you'll log in each time you open the app.

## Installing

1. Unzip the **CaseloadTool** folder somewhere you'll keep it, such as **Documents**. Keep everything in the folder together — the app needs the **_internal** folder that sits next to it.
2. Open the folder and double-click **CaseloadTool.exe**.
3. The first time, Windows may say **"Windows protected your PC."** Click **More info**, then **Run anyway**.
4. Optional: right-click **CaseloadTool.exe** → **Send to** → **Desktop (create shortcut)**.

No other installation is needed. Your groups, Actions, and templates are stored separately (see "Your data and privacy"), so replacing the folder with a newer version never erases them.

## Starting the app and logging in

Each time you open the app, an **Edge window opens to the WGU sign-in**:

1. Log in as usual and approve the **PingID** request on your phone.
2. Wait. When your Salesforce Caseload page appears, the login window **closes by itself**.
3. The app then loads your caseload, which takes about 20 seconds, and opens.

Your login is **never saved**. When you close the app it's gone, and the next launch asks again.

**Just want to set things up?** Close the login window. The app still opens and everything works except actually sending. You'll see a note that the caseload couldn't be loaded — that's expected. When you're ready to send, click **↻ Refresh Caseload** to log in.

## Stay on Outlook (classic)

The app sends email through **Outlook (classic)**. The **New Outlook** cannot be controlled by other programs, so the app can't send through it.

Microsoft sometimes switches people to the New Outlook automatically. If the app says **"You have the New Outlook open, but this app needs Outlook (classic)"**:

- Turn off the **New Outlook** toggle at the top right of Outlook, **or**
- Close it and open **Outlook (classic)** from the Start menu.

Your account and signature will still be there. **Open Outlook (classic) before you run anything** — the app never opens Outlook for you.

## Setting up: groups and Actions

### Groups

A **group** is usually one course. Pick it from the **Scenario Groups** dropdown on the left. **An Action in a course group only ever reaches students in that course** — you don't need a course filter. A group that isn't a course (and **General**) reaches students in every course.

- **+ Add Group** creates one. Leave **This group is a course** checked and name it by its course code (for example **D424**).
- **📝 Edit Group** renames it. Renaming never changes the course it's for.
- **⚙ Settings → Courses** sets each group's details: whether it's a course, its **course code**, whether it **has tasks** and **how many**, and whether it **has an objective assessment** (a course can have tasks, an OA, or both). Click **💾 Save Settings** when done.
- **Task emails** (in the same card, once a course has tasks): for each task, choose the template to send a student who **just passed** it, and its subject. There's no row for the last task of a tasks-only course (those students have finished), but a course that also has an OA gets a **Task N (OA prep)** row for the last task.
- **❌ Delete** removes it **and all of its Actions** (you'll be asked to confirm).
- **General** is always there and can't be renamed or deleted.

### Actions

An **Action** is one kind of outreach, such as "Day 3 Follow Up". Click **+ Add Action**, or **Edit** next to an existing one:

1. **Action Name** — what you'll see in the list.
2. **Select Communication Method(s)** — check **Send Email**. (Texting isn't available yet; see below.)
3. **Email Details** — the subject, your **Outlook signature**, and the email body (choose a template, or create one with **➕ New**).
4. **Select Filters for Roster** — **➕ Add Filter Rule** narrows who it goes to (course, task status, dates, momentum, and more). With no filters, it goes to everyone in the group's course (or your whole caseload, for an Action in General).
5. **Note Details** — what to record in Salesforce after the email is sent: the note subject and body, plus an optional **follow-up note** for the roster view. These fields are only available when Send Email is checked.
6. **Is Group Welcome Email** — check this on the one Action per group that **✉️ Send Welcome Emails** should run.
7. Click **💾 Save Action**.

### Recipe: email students who just passed a task

For a daily "next task" email that also catches weekend passes and never repeats:

1. Put the Action in the course's group (for example **D424**).
2. Add these filter rules:
   - **latest_task_status** → **IsOneOf** → **Passed**
   - **latest_task_date** → **WithinLastDays** → **3** (today and the 3 days before, so a Monday run catches Friday and the weekend)
   - **latest_task_number** → **Equals** → the task they just passed, e.g. **2**
   - **course_followup_note** → **DoesNotContain** → a phrase only this email uses, e.g. **Task 3 tips sent**
3. In **Note Details**, set the **follow-up note** to that same phrase (**Task 3 tips sent**), so tomorrow's run skips anyone who already got it.
4. Repeat for each task, then save them all as one **Saved Batch** and run it each morning.

### Personalizing emails

Use **Insert Field** while writing a subject or body to add details that fill in for each student:

- **Student Name**
- **Course Code**
- **Last Submitted Task**
- **Last Passed Task** — blank unless the student's most recent submission passed
- **Next Task**

## Sending

There are four ways to send. Every one shows you exactly who will be contacted first, and **nothing goes out until you click Send or Run**.

- **Run** (next to an Action) — sends that Action.
- **✉️ Send Welcome Emails** (Dashboard) — runs each group's welcome Action.
- **🗂️ Run Action Batch** (Dashboard) — runs several Actions in an order you choose. **💾 Save Batch** keeps a combination you use often; pick it later from **Saved Batches**.
- **📤 Send Email to All Students** (Dashboard) — a one-off email, such as a class cancellation, with an optional note.

### The review window

Before sending you'll see every matching student. Uncheck anyone to leave them out (**Select All** / **Select None** help). For a single Action or a one-off email you can also edit the subject and body — **for this send only**; your saved Action isn't changed.

### While it runs

A progress window shows who's being sent to and how far along it is. The app stays usable, and the **Live Application Log** shows each step as it happens.

- **⛔ Stop after this student** (or **⛔ STOP Process**) finishes the current student, then stops.
- If you close the app mid-run it asks first, because the current student could be left half-done (emailed, but no note yet).

### Results

- **Everything worked:** a short summary.
- **Anything failed or was skipped:** a list of every student who needs follow-up and why. **📋 Copy List** copies it so you can work through it. Students left out by Stop show as **"Not started (run was stopped)."**

The day's log is a backup if you close that window by accident (see "Your data and privacy").

## Notes in Salesforce

- A note is written **only after a student's email was sent successfully.** If the email fails, the note is skipped and the student shows up in the results list.
- The note and the follow-up note are saved together. If saving fails, the student shows up in the results list so you can add it by hand.

## Texting

Texting through Mongoose isn't available yet. If an Action has **Send Text** checked, each text shows as **failed** with "Texting isn't set up in this app yet — no text was sent." Nothing is texted. **⬇ Sync Texting IDs** and **↻ Restart Browser** are placeholders for upcoming features.

## Test mode

Test mode lets you try everything on your real caseload **without emailing any student or writing to Salesforce**:

- Every email goes to **one address you choose**, with the student it was meant for shown at the top, so you can check names and personalization.
- Notes are **not** written to Salesforce.
- A **yellow TEST MODE bar** stays across the top of the app.

**To turn it on:** in the data folder (below), create a file named **test_mode.json** containing exactly this, with your own email address:

`{"redirect_email": "you@wgu.edu"}`

**To turn it off and send for real:** delete **test_mode.json**, then restart the app. The yellow bar disappears.

## Your data and privacy

Your groups, Actions, templates, saved batches, and logs are kept in your own Windows profile:

`%LOCALAPPDATA%\CaseloadTool`

(Paste that into File Explorer's address bar to open it.)

- **No student roster is ever saved.** It's loaded fresh each session and kept only in memory.
- **Your Salesforce login is never saved.**
- **Logs are kept for today only** and are deleted the next time you start the app. They exist so you can follow up on anything that failed today. If a Salesforce note fails, a screenshot of the page is saved under **logs\screenshots** for the same purpose.

## Troubleshooting

**"Outlook isn't open. Open Outlook (classic)…"**
Open Outlook (classic), wait for your inbox to load, then try again.

**"You have the New Outlook open, but this app needs Outlook (classic)…"**
See "Stay on Outlook (classic)" above.

**"The caseload isn't loaded yet…"**
Click **↻ Refresh Caseload** and log in.

**"Your Salesforce login has expired…"**
Click **↻ Refresh Caseload** and log in again.

**"Outlook signature '…' wasn't found…"**
Edit the Action and pick a signature from the list — the one it had may have been renamed or removed in Outlook.

**"Microsoft Edge couldn't be started…"**
Make sure Microsoft Edge is installed and up to date.

**The login window says PingID failed, or nothing arrives on your phone**
That's a WGU sign-in issue, not the app. Contact the IT Service Desk. You can still use the app for setup in the meantime.

**"Something went wrong"**
The details were saved to today's log in **%LOCALAPPDATA%\CaseloadTool\logs**. Send that file to whoever supports the app.
