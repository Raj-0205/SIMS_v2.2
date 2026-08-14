# app.py

import flet as ft
from ui.router import AppRouter 

def bootstrap_logs():
    print("========================================")
    print("SIMS v2.2 - Bootstrapping Application")
    print("========================================")
    print("[INFO] Application Ready. Launching UI...")

def main(page: ft.Page):
    page.title = "SIMS v2.2 - ERP Dashboard"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    router = AppRouter(page)
    page.go("login")

if __name__ == "__main__":
    bootstrap_logs()
    try:
        ft.run(main)
    except AttributeError:
        ft.app(target=main)
