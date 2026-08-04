# src/views/template_editor_webview.py
import os
import threading
import webview


class _EditorAPI:
    def __init__(self, template_id, on_save_callback):
        self.template_id = template_id
        self.on_save_callback = on_save_callback
        self.window = None

    def on_save(self, name, body):
        if self.on_save_callback:
            self.on_save_callback(self.template_id, name, body)
        if self.window:
            self.window.destroy()

    def on_cancel(self):
        if self.window:
            self.window.destroy()


def open_template_editor(template_id=None, template_name="", template_body="", on_save_callback=None):
    """Opens the Quill-based rich template editor in its own window, running on a
    background thread so it doesn't block the main CustomTkinter event loop."""

    def _run():
        api = _EditorAPI(template_id, on_save_callback)

        html_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets", "quill", "editor.html"
        )

        window = webview.create_window(
            "Template Editor",
            html_path,
            js_api=api,
            width=700,
            height=600
        )
        api.window = window

        def _on_loaded():
            safe_name = (template_name or "").replace("'", "\\'")
            safe_body = (template_body or "").replace("`", "\\`")
            window.evaluate_js(f"loadTemplate('{safe_name}', `{safe_body}`)")

        window.events.loaded += _on_loaded

        webview.start()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()