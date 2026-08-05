# CLAUDE.md — Action Manager App

## Project overview
Python/CustomTkinter desktop app, rewritten from a previous non-professional dev's spaghetti-code app into a clean MVC design. The app helps professors automate routine student communications (emails, texts, notes) and document them, organized into "Groups" (school courses).

The developer working on this is a C# developer who is newer to Python — favor clear, idiomatic Python and explain any non-obvious language features when they come up.

## Architecture
- `src/models/` — Action, Group, and enum definitions
- `src/services/` — ActionRepository, GroupRepository (JSON file storage)
- `src/views/` — AddActionView, ScenarioNavPanel, and other CustomTkinter views
- `src/controllers/app_controller.py` — main app controller

## Working rules (follow these strictly)
1. **One focused change at a time.** Propose a single change with reasoning and a specific test to verify it, then wait for the result before moving on to the next thing.
2. **Always ask for the actual current code** before proposing changes to a file that's had prior edits — don't assume you remember its state; read the file fresh.
3. **Ask about intent (what SHOULD happen) vs. observed behavior** before proposing a fix — don't assume the cause.
4. **Preserve existing variable/field names and structures** unless they're actively misleading. Ask before renaming anything.
5. **ID-based lookups only.** Never write new code that looks up records (groups, templates, actions, or any future entity) by name — names can be renamed mid-session. Always use the record's stable ID.
6. **Name secondary issues, don't fix them.** If you spot an unrelated bug or issue while investigating something else, mention it but don't fix it until the current task is finished.
7. **Git safety net.** The developer is still learning Git. Proactively remind them when it's a good time to commit or branch (e.g. before starting a risky change, after a working milestone) — don't assume they'll remember to do it themselves.

## Known open items (as of last session)
- Welcome-email conflict dialog didn't appear when marking a second existing action as welcome, possibly same group — unconfirmed if real bug; needs checking `groups.json` for which group each action id belongs to.
- Switching groups in the nav panel doesn't clear/reset the right-hand workspace (missing callback from `ScenarioNavPanel`'s group dropdown to the controller).
- Leftover debug print statements need cleanup, e.g. a `[DEBUG] target_group=...` line in `save_action()`.
- A dead commented-out line in `populate_fields()` needs deleting.
- **Email templates feature (urgent):** `src/models/email_template.py`, `src/services/template_repository.py`, and `src/views/template_editor_modal.py` exist as skeletons but are not wired up — `AppController` never instantiates `self.template_repo`, and the view calls methods like `save_template`/`get_template_by_name`/`delete_template` that don't exist yet on `TemplateRepository`.

### Template editor requirements
- Rich template editor: bold, italic, underline, highlight, font changes, insert links, plus a toggle to view/edit raw HTML directly (some professors at this IT college are HTML-literate and want that option).
- Template dropdown on `add_action_view.py` lists all templates for any group. User can use a template as-is, or modify and save as a new template (fork) — original is preserved. One template can be used by many actions.
- All template references (selection, editing, association with an action) must be ID-based, never name-based.
- When an existing template's content is edited, ask whether to update it in place or save as a new template.
- Delete button for templates should only be enabled when an existing (non-new) template is selected in the dropdown. Exact placement of delete UX still TBD.
- **Chosen approach:** embedded web view (pywebview) with Quill.js as the rich-text editor, bundled locally in the project (not loaded from a CDN, due to VPN/network friction). Ruled out: plain `tkinter.Text` (still exposes raw HTML to non-technical users), PyQt/wxPython (too disruptive to migrate mid-project).
- **Known blocker (unresolved):** `pywebview` requires `webview.start()` to run on the main thread, but CustomTkinter's `root.mainloop()` already occupies the main thread — so launching the template editor window from a background thread doesn't work. Two options under consideration: (1) run pywebview in a separate OS process, or (2) fall back to a plain `tkinter.Text`-based editor with a hand-built HTML parser instead of Quill.js.

## Recently fixed
- New action ID collision (placeholder `"ACT-AUTO-TEMP"` was overwriting actions; now sends `None` to generate a real UUID).
- `interaction_type` save crash: aligned `InteractionType` enum (EMAIL, TEXT, EMAIL_AND_TEXT) with the UI dropdown and convert string to enum before saving.
- "General" group is now a real persisted group auto-created on startup, instead of a UI-only placeholder.
- Group dropdown not re-selecting on edit (was checking a nonexistent `group_name` key).
- Welcome-email checkbox not reflecting saved state (now compares `Group.welcome_action_id` to the action's own id).
- `Group.id` not persisting across restarts in `GroupRepository` load/save.
- Migrated `Action.group_id` from name-based to id-based linkage throughout (`save_action` and `populate_fields` lookups).
- `interaction_type` crash on edit caused by incorrect indentation of `self.interaction_type_var.set(...)`.
