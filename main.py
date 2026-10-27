# main.py
import customtkinter as ctk
from src.controllers.app_controller import AppController
from src.services import app_paths

def main():
    # Set the overall look and feel of the app
    ctk.set_appearance_mode("System")  # Modes: "System", "Dark", "Light"
    ctk.set_default_color_theme("blue") # Themes: "blue", "green", "dark-blue"

    # One-time copy of data from its old in-repo locations into
    # %LOCALAPPDATA%\CaseloadTool (see app_paths.py). Never overwrites.
    copied = app_paths.migrate_legacy_data()
    # A "with my data" build brings groups/actions/templates/test mode along
    # in starter_data next to the .exe - copied in on first launch here.
    copied += app_paths.install_starter_data()

    # Initialize the "brain" of our app (the Controller)
    app = AppController()
    if copied:
        app.activity_logger.log(f"Copied your existing data ({', '.join(copied)}) to {app_paths.data_dir()}")
    
    # Start the Tkinter main event loop
    app.run()

if __name__ == "__main__":
    main()