from src.models.email_template import EmailTemplate
from src.services.template_repository import TemplateRepository


def test_save_and_load_templates(tmp_path):
    """Verify templates can be saved to and loaded from JSON."""
    test_file = tmp_path / "test_templates.json"
    repo = TemplateRepository(file_path=str(test_file))

    # 1. Save new template
    template = EmailTemplate(
        name="Welcome HTML",
        body="<h1>Welcome {{first_name}}</h1>"
    )
    repo.save(template)

    # 2. Load templates back
    loaded = repo.load_all()
    assert len(loaded) == 1
    assert loaded[0].name == "Welcome HTML"
    assert loaded[0].body == "<h1>Welcome {{first_name}}</h1>"
    assert loaded[0].id == template.id