# core/startup/bootstrap.py

from __future__ import annotations
from typing import Callable

import flet as ft

from core.configuration.service import ConfigService
from core.logger.service import LogService
from core.startup.preflight import PreFlightChecker
from core.startup.startup_status import StartupStatus


class ApplicationBootstrapper:
    """
    Coordinates the application startup lifecycle, initializes core engines,
    and provides the Flet UI entry point.
    """

    _SEPARATOR = "=" * 40

    def __init__(self) -> None:
        """Initializes the bootstrapper in a NOT_STARTED state."""
        self.status: StartupStatus = StartupStatus.NOT_STARTED

    def launch(self) -> Callable[[ft.Page], None]:
        """
        Executes the full bootstrap sequence.

        Returns:
            Callable[[ft.Page], None]: The main Flet UI entry point.

        Raises:
            RuntimeError: If any critical startup phase fails.
        """
        self.status = StartupStatus.INITIALIZING

        # Pure console fallback for visual headers (these don't go to log files)
        print(self._SEPARATOR)
        print("SIMS v2.2")
        print("Bootstrapping Application")
        print(self._SEPARATOR)

        self._run_preflight()
        self._initialize_engines()

        ui_entry_point = self._create_ui_entry_point()

        self.status = StartupStatus.READY
        
        self._report("Application Ready")
        self._report("Launching UI...")
        
        # Pure console footer
        print(f"{self._SEPARATOR}\n")

        return ui_entry_point

    def _report(self, message: str, is_error: bool = False) -> None:
        """
        Internal reporting helper.
        Uses standard print() before Logger is initialized.
        Once active, seamlessly switches to the enterprise LogService.
        """
        if LogService.is_initialized():
            if is_error:
                LogService.error(message, context="BOOTSTRAP")
            else:
                LogService.info(message, context="BOOTSTRAP")
        else:
            prefix = "[✗] " if is_error else ""
            print(f"{prefix}{message}")

    def _run_preflight(self) -> None:
        """Executes pre-flight checks and halts on failure."""
        checker = PreFlightChecker()
        result = checker.run_checks()

        if not result.success:
            self.status = StartupStatus.FAILED
            error_messages = "\n".join(result.messages)
            raise RuntimeError(f"PreFlight checks failed:\n{error_messages}")

        self._report("[✓] PreFlight Checks")

    def _initialize_engines(self) -> None:
        """
        Orchestrates the strictly ordered initialization of all core application engines.
        """
        engines = (
            self._initialize_configuration,
            self._initialize_logging,
            self._initialize_database,
            self._initialize_audit,
        )
        for engine in engines:
            engine()

    def _initialize_configuration(self) -> None:
        """Initializes the Configuration Engine from disk."""
        try:
            ConfigService.initialize()
            self._report("[✓] Configuration Engine")
        except Exception as exc:
            self.status = StartupStatus.FAILED
            self._report(f"Configuration Engine Failed: {exc}", is_error=True)
            raise RuntimeError(f"Configuration failed: {exc}") from exc

    def _initialize_logging(self) -> None:
        """Initializes the Logger Engine."""
        try:
            LogService.initialize()
            self._report("[✓] Logging Engine Active")
        except Exception as exc:
            self.status = StartupStatus.FAILED
            self._report(f"Logging Engine Failed: {exc}", is_error=True)
            raise RuntimeError(f"Logging failed: {exc}") from exc

    def _initialize_database(self) -> None:
        """Placeholder for Database Engine initialization."""
        self._report("[✓] Database Engine (Pending)")

    def _initialize_audit(self) -> None:
        """Placeholder for Audit Engine initialization."""
        self._report("[✓] Audit Engine (Pending)")

    def _create_ui_entry_point(self) -> Callable[[ft.Page], None]:
        """
        Creates the Flet application target function.
        """
        def main_ui(page: ft.Page) -> None:
            # Dynamically fetch settings from the Configuration Engine
            app_config = ConfigService.app()
            
            app_title = f"{app_config.name} v{app_config.version}"
            
            page.title = app_title
            page.window_width = 1280
            page.window_height = 720
            page.window_min_width = 1024
            page.window_min_height = 768
            page.theme_mode = ft.ThemeMode.LIGHT

            page.vertical_alignment = ft.MainAxisAlignment.CENTER
            page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

            page.add(
                ft.Text(
                    app_title,
                    size=40,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(
                    "Core Framework Initialized Successfully.",
                    size=16,
                ),
                ft.Text(
                    f"Environment: {app_config.environment.value.upper()}",
                    size=12,
                    color=ft.Colors.GREY_500  # <--- FIX APPLIED HERE
                )
            )

            if LogService.is_initialized():
                LogService.info("Flet UI Page Loaded and Displayed.", context="UI")

        return main_ui
