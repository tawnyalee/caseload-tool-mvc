# main.py
import customtkinter as ctk
from src.controllers.app_controller import AppController

def main():
    # Set the overall look and feel of the app
    ctk.set_appearance_mode("System")  # Modes: "System", "Dark", "Light"
    ctk.set_default_color_theme("blue") # Themes: "blue", "green", "dark-blue"

    # Initialize the "brain" of our app (the Controller)
    app = AppController()
    
    # Start the Tkinter main event loop
    app.run()

if __name__ == "__main__":
    main()