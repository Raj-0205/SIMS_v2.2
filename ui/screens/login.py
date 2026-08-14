# ui/screens/login.py

import flet as ft

__all__ = ["LoginScreen"]


class LoginScreen(ft.Container):
    """Initial entry point simulating route protection."""

    def __init__(self, page: ft.Page) -> None:
        super().__init__(
            expand=True,
            alignment=ft.Alignment.CENTER,
        )

        self._page = page

        self.content = ft.Card(
            elevation=5,
            content=ft.Container(
                width=400,
                padding=40,
                content=ft.Column(
                    tight=True,
                    spacing=25,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(
                            ft.Icons.ACCOUNT_CIRCLE,
                            size=80,
                        ),
                        ft.Text(
                            "SIMS v2.2",
                            size=28,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.TextField(
                            label="Username",
                            value="admin",
                            autofocus=True,
                        ),
                        ft.TextField(
                            label="Password",
                            value="admin",
                            password=True,
                            can_reveal_password=True,
                        ),
                        ft.ElevatedButton(
                            content=ft.Text("Login to ERP"),
                            icon=ft.Icons.LOGIN,
                            width=200,
                            height=45,
                            # TODO (Production): Replace with AuthenticationService
                            on_click=lambda _: self._page.go("/dashboard"),
                        ),
                    ],
                ),
            ),
        )
