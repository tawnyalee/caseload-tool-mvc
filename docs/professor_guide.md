# Caseload Tool — Professor Guide

The Caseload Tool sends your routine student outreach for you: it emails students from your own Outlook, then writes the matching note in Salesforce. You decide who gets what with Actions and filters, and you review every send before anything goes out.

> This guide is also inside the app: click **❓ Help** at any time.

## Before you start

You need all of these on your computer:

- **Windows** with **Microsoft Edge** (already installed on WGU computers).
- **Outlook (classic)**, signed in to your WGU email. *Not* the "New Outlook" — see "Stay on Outlook (classic)" below.
- **Your email signature set up in Outlook (classic)** (File → Options → Mail → Signatures). The app uses it on every email.
- **Salesforce access** with **PingID on your phone**, at least for your first login.

## Installing

1. Unzip the **CaseloadTool** folder somewhere you'll keep it, such as **Documents**. Keep everything in the folder together — the app needs the **_internal** folder that sits next to it.
2. Open the folder and double-click **CaseloadTool.exe**.
3. The first time, Windows may say **"Windows protected your PC."** Click **More info**, then **Run anyway**.
4. Optional: right-click **CaseloadTool.exe** → **Send to** → **Desktop (create shortcut)**.

No other installation is needed. Your groups, Actions, and templates are stored separately (see "Your data and privacy"), so replacing the folder with a newer version never erases them.

## Starting the app and logging in

Each time you open the app, an **Edge window opens to the WGU sign-in**:

1. Log in as usual. The first time, you'll also approve a **PingID** request on your phone; after that, WGU should recognize this computer, the same way your everyday Edge does.
2. Wait. When your Salesforce Caseload page appears, the login window **closes by itself**.
3. The app window shows a loading screen the whole time. Once you're logged in, it says it's loading your caseload, which can take a minute or two, then the app opens.

The app **never sees or saves your password**. The login window is Edge, using a separate Edge profile kept just for this app. If Edge offers to remember your password there, that's your choice, same as in your everyday Edge.

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
- **⚙ Settings → Courses** sets each group's details: whether it's a course, its **course code**, whether it **has tasks** and **how many**, and whether it **has an objective assessment** (a course can have tasks, an OA, or both). Click **💾 Save Settings** when done. You can set up one course at a time: finished courses save even if another is incomplete, and a popup lists any that weren't saved and why.
- **Default Outlook Signature** (top of **⚙ Settings**): optional. New Actions start with it, and you can still change it on any Action. **🎯 Send Task Emails** needs it.
- **Task emails** (in the same card, once a course has tasks): each row is the task a student **just passed**, so **Passed Task 1** is your email about Task 2. Choose a saved email, or use **➕ New** and **✏️ Edit** to write one, the same as on an Action. Then click **💾 Save Settings**. There's no row for a course's last task, and OAs aren't included yet.
- **❌ Delete** removes it **and all of its Actions** (you'll be asked to confirm).
- **General** is always there and can't be renamed or deleted.

### Actions

An **Action** is one kind of outreach, such as "Day 3 Follow Up". Click **+ Add Action**, or **Edit** next to an existing one:

1. **Action Name** — what you'll see in the list.
2. **Select Communication Method(s)** — check **Send Email**, **Send Text**, or both. (Texting is new; see "Texting" below.)
3. **Email Details** — the subject, your **Outlook signature**, and the email body (choose a template, or create one with **➕ New**).
4. **Select Filters for Roster** — **➕ Add Filter Rule** narrows who it goes to (course, task status, dates, momentum, and more). With no filters, it goes to everyone in the group's course (or your whole caseload, for an Action in General).
5. **Note Details** — what to record in Salesforce after the email is sent: the note subject and body, plus an optional **follow-up note** for the roster view. These fields are only available when Send Email is checked.
6. **Is Group Welcome Email** — check this on the one Action per group that **✉️ Send Welcome Emails** should run.
7. Click **💾 Save Action**.

### Suggested naming convention

When creating Actions and their emails, we suggest this pattern: `<CourseCode><ActionPurpose>` for the Action and `<CourseCode><ActionPurpose>Email` for its email. For example, **D424Welcome** for an Action and **D424WelcomeEmail** for its email.

### Task emails: email students who just passed a task

You don't need an Action for this. Set up each course in **⚙ Settings**, choose a **Default Outlook Signature**, then click **🎯 Send Task Emails** on the Dashboard.

- **Who it finds:** students who passed a task yesterday. After time off, enter a number in **Days to look back**: **3** on a Monday covers Friday through Sunday. Today's passes aren't included, so run it again tomorrow for those.
- **Before anything sends:** the review window has one section per email, showing the task, subject, the email's text, and the students getting it. Uncheck anyone who shouldn't get it, or click **Select None** to hold back a whole email.
- **What they get:** "Hello" and their first name (or preferred name), then your email for the task they passed. Write only the rest of the email in Settings.
- **Subject:** **Task <next task> Support**, for example **Task 3 Support** after passing Task 2.
- **In Salesforce:** a note with the same subject, holding the text of the email, and a follow-up note with the same words. The app doesn't leave anyone out, even a student you've already contacted, so check the list and untick anyone who shouldn't get this email. If you run it twice for the same days, the same students appear again.
- **Already submitted the next task?** They get a short congratulations instead of your email.

Anyone who can't get an email because none is set up for that task is listed in the results with the reason.

### Personalizing emails

Use **Insert Field** while writing an email subject or body to add details that fill in for each student. You can also type them (with the double braces, e.g. **{{last_passed_task}}**) into **Note Details** — the note subject, body, and follow-up note:

- **Student First Name** — `{{student_name}}` (their preferred name if Salesforce has one, otherwise their first name, never their full name)
- **Course Code** — `{{course_code}}`
- **Last Submitted Task** — `{{last_submitted_task}}`
- **Last Passed Task** — `{{last_passed_task}}` (blank unless the student's most recent submission passed)
- **Next Task** — `{{next_task}}`

## Sending

There are five ways to send. Every one shows you exactly who will be contacted first, and **nothing goes out until you click Send or Run**.

- **Run** (next to an Action) — sends that Action.
- **✉️ Send Welcome Emails** (Dashboard) — runs each group's welcome Action. The review window shows each course's message before anything sends.
- **🎯 Send Task Emails** (Dashboard) — emails students who just passed a task, using your course settings.
- **🗂️ Run Action Batch** (Dashboard) — runs several Actions in an order you choose. **💾 Save Batch** keeps a combination you use often; pick it later from **Saved Batches**.
- **📤 Send Email to All Students** (Dashboard) — a one-off email, such as a class cancellation, with an optional note.

### The review window

Before sending you'll see every matching student. Uncheck anyone to leave them out (**Select All** / **Select None** help). For a single Action or a one-off email you can also edit the subject and body — **for this send only**; your saved Action isn't changed.

### While it runs

A progress window shows who's being sent to and how far along it is. The app stays usable, and the **Live Application Log** shows each step as it happens.

- **⛔ Cancel after this student** (or **⛔ STOP Process**) finishes the current student, then cancels the rest.
- If you close the app mid-run it asks first, because the current student could be left half-done (emailed, but no note yet).

### Results

- **Everything worked:** a short summary.
- **Anything failed or was skipped:** a list of every student who needs follow-up and why. **📋 Copy List** copies it so you can work through it. Students left out by Stop show as **"Not started (run was stopped)."**

The day's log is a backup if you close that window by accident (see "Your data and privacy").

## Notes in Salesforce

- A note is written **only after a student's email was sent successfully.** If the email fails, the note is skipped and the student shows up in the results list.
- The note and the follow-up note are saved together. If saving fails, the student shows up in the results list so you can add it by hand.

## Texting

Texting is **new and still being tested**. When an Action has **Send Text** checked, the app schedules each text in **Mongoose**:

- A Mongoose window opens with the first text and stays open while the app is open, so you only log in when Mongoose asks. It closes with the app, or when you click **↻ Refresh Caseload**.
- Each text goes out from the **department matching the student's course** (for example D424), so it lands in the right shared inbox.
- Each one is **scheduled**, never sent instantly: for the next time between **10 AM and 8 PM in the student's own time zone**.
- **For now, you finish each text yourself.** Mongoose comes to the front and the progress window says "Waiting for you". The app fills it in (student, message, name, date and time) and waits. Check it, then click **Schedule** — or **Cancel** to skip that student.
- The **Text Subject** becomes the text's **Message Name** in Mongoose. Fields like **{{student_name}}** work in the text and its subject.
- A text can be at most **150 characters**. The Action shows a live count, and Save Action refuses a longer one. Fields like {{student_name}} count as written, so leave some room: if a filled-in text comes out over 150, that student is skipped and listed in the results.
- A student is **skipped and listed** in the results when the app can't place them safely: no texting ID (try **↻ Refresh Caseload**), no time zone, or not found in that course's Mongoose department (for example, they opted out). Text those students by hand if needed.
- Texts never write a Salesforce note — Mongoose notes them itself.
- The app finishes every student's email and note first, across a whole batch. Only then does it open Mongoose for the texts, one student at a time, grouped by course. A text problem can't stop an email or a note. If Mongoose can't be opened, those texts are listed as skipped.

**⬇ Sync Texting IDs** and **↻ Restart Browser** are placeholders and do nothing yet.

## Test mode

Test mode lets you try everything on your real caseload **without emailing or texting any student or writing to Salesforce**:

- Every email goes to **one address you choose**, with the student it was meant for shown at the top, so you can check names and personalization.
- Notes are **not** written to Salesforce.
- Texts are filled in inside Mongoose and then **thrown away** — nothing is scheduled, so no student gets a text.
- A **yellow TEST MODE bar** stays across the top of the app.

**To turn it on:** in the data folder (below), create a file named **test_mode.json** containing exactly this, with your own email address:

`{"redirect_email": "you@wgu.edu"}`

**To turn it off and send for real:** delete **test_mode.json**, then restart the app. The yellow bar disappears.

## Your data and privacy

Your groups, Actions, templates, saved batches, and logs are kept in your own Windows profile:

`%LOCALAPPDATA%\CaseloadTool`

(Paste that into File Explorer's address bar to open it.)

- **No student roster is ever saved.** It's loaded fresh each session and kept only in memory.
- **The app never saves your Salesforce password.** The login window keeps its own Edge profile (in the **edge-profile** folder) so WGU sign-in recognizes this computer. Pages it loads, including your Caseload page, are cleared from that profile right after you log in.
- **Logs are kept for today only** and are deleted the next time you start the app. They exist so you can follow up on anything that failed today. If a Salesforce note or a Mongoose text fails, the app saves a screenshot of the page for the same purpose. To see them, click **🖼 Open Screenshots Folder** at the bottom of **❓ Help**. Screenshots can show student information, so don't email them.
- **The diagnostics log has no student information** and is kept for **14 days**, in **logs\diagnostics**. It's for troubleshooting: what you clicked and chose (as counts), the app version, and the full details of every error, each marked **Outside problem** (something you can fix or retry, such as Outlook being closed) or **App error** (most likely a bug). Before anything is written there, student names, IDs, emails, phone numbers, and texting IDs are replaced with placeholders such as **[student]**.

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
Edit the Action and pick a signature from the list — the one it had may have been renamed or removed in Outlook. Save Action won't accept "No Outlook signatures found": choose a real signature, or set one up in Outlook first.

**"Microsoft Edge couldn't be started…"**
Make sure Microsoft Edge is installed and up to date.

**The login window says PingID failed, or nothing arrives on your phone**
That's a WGU sign-in issue, not the app. Contact the IT Service Desk. You can still use the app for setup in the meantime.

**"Something went wrong"** (or any problem you want help with)
Click **🛠 Open Diagnostics Log**, in the results window or at the bottom of **❓ Help**. It opens today's log, ready to copy and send to whoever supports the app. For an earlier day, the files are in **%LOCALAPPDATA%\CaseloadTool\logs\diagnostics**. It's safe to share: it contains no student information, and it's kept for 14 days, so it still helps a few days later. Today's regular log (in **logs**) has more detail but includes student names — don't email it.
