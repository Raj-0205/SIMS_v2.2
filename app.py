# app.py

import flet as ft
from core.startup.bootstrap import ApplicationBootstrapper

if __name__ == "__main__":
    bootstrapper = ApplicationBootstrapper()
    ui_entry_point = bootstrapper.launch()

    try:
        ft.run(ui_entry_point)
    except AttributeError:
        ft.app(target=ui_entry_point)
