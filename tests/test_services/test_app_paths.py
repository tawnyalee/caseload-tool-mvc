from src.services import app_paths


def test_data_folder_follows_the_override_and_is_created(tmp_path, monkeypatch):
    folder = tmp_path / "somewhere"
    monkeypatch.setenv(app_paths.DATA_DIR_ENV_VAR, str(folder))
    assert app_paths.data_dir() == folder
    assert folder.is_dir()
    assert app_paths.groups_file() == folder / "groups.json"
    assert app_paths.screenshots_dir() == folder / "logs" / "screenshots"


def test_default_is_localappdata_caseloadtool(tmp_path, monkeypatch):
    monkeypatch.delenv(app_paths.DATA_DIR_ENV_VAR, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert app_paths.data_dir() == tmp_path / "CaseloadTool"


def _old_layout(root):
    (root / "src" / "data").mkdir(parents=True)
    (root / "data").mkdir()
    (root / "src" / "data" / "groups.json").write_text('[{"name": "D424"}]', encoding="utf-8")
    (root / "data" / "test_mode.json").write_text('{"redirect_email": "me@example.test"}', encoding="utf-8")


def test_migration_copies_old_files_once_and_leaves_the_originals(tmp_path):
    old_root = tmp_path / "repo"
    _old_layout(old_root)

    copied = app_paths.migrate_legacy_data(legacy_root=old_root)

    assert sorted(copied) == ["groups.json", "test_mode.json"]
    assert app_paths.groups_file().read_text(encoding="utf-8") == '[{"name": "D424"}]'
    assert (old_root / "src" / "data" / "groups.json").exists()  # copied, not moved
    assert app_paths.migrate_legacy_data(legacy_root=old_root) == []  # second launch: nothing to do


def test_migration_never_overwrites_newer_data(tmp_path):
    old_root = tmp_path / "repo"
    _old_layout(old_root)
    app_paths.groups_file().write_text('[{"name": "Newer"}]', encoding="utf-8")

    copied = app_paths.migrate_legacy_data(legacy_root=old_root)

    assert "groups.json" not in copied
    assert app_paths.groups_file().read_text(encoding="utf-8") == '[{"name": "Newer"}]'


def test_migration_does_nothing_in_a_packaged_build(tmp_path, monkeypatch):
    old_root = tmp_path / "repo"
    _old_layout(old_root)
    monkeypatch.setattr(app_paths.sys, "frozen", True, raising=False)
    assert app_paths.migrate_legacy_data(legacy_root=old_root) == []


def test_bundled_template_editor_is_found():
    assert app_paths.resource_path("src/assets/quill/editor.html").is_file()


def test_bundled_resources_come_from_the_build_folder_when_packaged(tmp_path, monkeypatch):
    monkeypatch.setattr(app_paths.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert app_paths.resource_path("src/assets/quill/editor.html") == tmp_path / "src/assets/quill/editor.html"


def test_warns_when_store_python_would_hide_a_new_data_folder(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(app_paths.DATA_DIR_ENV_VAR, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(app_paths.sys, "executable", r"C:\Program Files\WindowsApps\Python.3.12\python.exe")
    monkeypatch.setattr(app_paths, "_warned", False)

    app_paths.data_dir()

    assert "Microsoft Store Python will hide" in capsys.readouterr().err


def test_no_warning_once_the_real_folder_exists(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(app_paths.DATA_DIR_ENV_VAR, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    (tmp_path / "CaseloadTool").mkdir()
    monkeypatch.setattr(app_paths.sys, "executable", r"C:\Program Files\WindowsApps\Python.3.12\python.exe")
    monkeypatch.setattr(app_paths, "_warned", False)

    app_paths.data_dir()

    assert capsys.readouterr().err == ""


# --- "with my data" builds: starter data copied in on first launch ----------

def _starter(folder, **files):
    folder.mkdir()
    for name, text in files.items():
        (folder / name).write_text(text, encoding="utf-8")
    return folder


def test_starter_data_is_copied_in_on_first_launch(tmp_path):
    starter = _starter(tmp_path / "starter_data", **{
        "groups.json": '[{"name": "C769"}]', "test_mode.json": '{"redirect_email": "me@example.test"}',
    })
    copied = app_paths.install_starter_data(starter)
    assert sorted(copied) == ["groups.json", "test_mode.json"]
    assert app_paths.test_mode_file().exists()  # starts in TEST MODE, not live


def test_starter_data_never_overwrites_this_computers_data(tmp_path):
    starter = _starter(tmp_path / "starter_data", **{"groups.json": '[{"name": "Old"}]'})
    app_paths.groups_file().write_text('[{"name": "Already here"}]', encoding="utf-8")
    assert app_paths.install_starter_data(starter) == []
    assert "Already here" in app_paths.groups_file().read_text(encoding="utf-8")


def test_no_starter_folder_means_nothing_to_do(tmp_path):
    assert app_paths.install_starter_data(tmp_path / "missing") == []


def test_running_from_source_never_installs_starter_data():
    assert app_paths.install_starter_data() == []
