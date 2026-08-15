# core/startup/bootstrap.py

from __future__ import annotations
from typing import Callable

import flet as ft

from core.configuration.service import ConfigService
from core.logger.service import LogService
from core.startup.preflight import PreFlightChecker
from core.startup.startup_status import StartupStatus
from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from ui.router import AppRouter


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
        self.status = StartupStatus.INITIALIZING

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

        print(f"{self._SEPARATOR}\n")

        return ui_entry_point

    def _report(self, message: str, is_error: bool = False) -> None:
        if LogService.is_initialized():
            if is_error:
                LogService.error(message, context="BOOTSTRAP")
            else:
                LogService.info(message, context="BOOTSTRAP")
        else:
            prefix = "[✗] " if is_error else ""
            print(f"{prefix}{message}")

    def _run_preflight(self) -> None:
        checker = PreFlightChecker()
        result = checker.run_checks()
        if not result.success:
            self.status = StartupStatus.FAILED
            error_messages = "\n".join(result.messages)
            raise RuntimeError(f"PreFlight checks failed:\n{error_messages}")
        self._report("[✓] PreFlight Checks")

    def _initialize_engines(self) -> None:
        engines = (
            self._initialize_configuration,
            self._initialize_logging,
            self._initialize_database,
            self._initialize_audit,
        )
        for engine in engines:
            engine()

    def _initialize_configuration(self) -> None:
        try:
            ConfigService.initialize()
            self._report("[✓] Configuration Engine")
        except Exception as exc:
            self.status = StartupStatus.FAILED
            self._report(f"Configuration Engine Failed: {exc}", is_error=True)
            raise RuntimeError(f"Configuration failed: {exc}") from exc

    def _initialize_logging(self) -> None:
        try:
            LogService.initialize()
            self._report("[✓] Logging Engine Active")
        except Exception as exc:
            self.status = StartupStatus.FAILED
            self._report(f"Logging Engine Failed: {exc}", is_error=True)
            raise RuntimeError(f"Logging failed: {exc}") from exc

    def _initialize_database(self) -> None:
        """Initializes Database and immediately processes Migrations sequentially."""
        try:
            DatabaseEngine.initialize()
            self._report("[✓] Database Engine Active")

            MigrationEngine.initialize()
            MigrationEngine.upgrade()
            self._report("[✓] Migration Engine Active & Up to Date")
        except Exception as exc:
            self.status = StartupStatus.FAILED
            self._report(f"Database/Migration Engine Failed: {exc}", is_error=True)
            raise RuntimeError(f"Database initialization failed: {exc}") from exc

    def _initialize_audit(self) -> None:
        self._report("[✓] Audit Engine (Pending)")

    def _create_ui_entry_point(self) -> Callable[[ft.Page], None]:
        def main_ui(page: ft.Page) -> None:
            app_config = ConfigService.app()

            page.title = f"{app_config.name} v{app_config.version}"
            page.window_width = 1280
            page.window_height = 720
            page.window_min_width = 1024
            page.window_min_height = 768
            page.theme_mode = ft.ThemeMode.LIGHT
            page.padding = 0

            # Single Authoritative Router Instance instantiated safely inside the entry point
            router = AppRouter(page)

            # Navigate using Flet 0.85 API standard (sync wrapper)
            page.navigate("/login")

            if LogService.is_initialized():
                LogService.info("Flet UI Page Loaded and Router Initialized.", context="UI")

        return main_ui
