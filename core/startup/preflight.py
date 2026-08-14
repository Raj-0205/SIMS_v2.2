import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PreFlightResult:
    """
    Encapsulates the result of the pre-flight environment checks.
    """
    success: bool
    messages: list[str] = field(default_factory=list)


class PreFlightChecker:
    """
    Responsible for verifying the runtime environment before engine initialization.
    """

    MIN_PYTHON_VERSION: tuple[int, int] = (3, 12)

    REQUIRED_DIRECTORIES = (
        "config/default",
        "config/development",
        "config/production",
        "config/testing",
        "database/backups",
        "database/migrations",
        "database/schema",
        "database/seed",
        "runtime/cache",
        "runtime/logs",
        "runtime/sessions",
        "runtime/temp",
        "storage/attendance",
        "storage/cache",
        "storage/documents",
        "storage/exports",
        "storage/imports",
        "storage/receipts",
        "storage/temp",
    )

    def __init__(self) -> None:
        """Initializes the PreFlightChecker with the resolved project root."""
        self._project_root = Path(__file__).resolve().parent.parent.parent

    def run_checks(self) -> PreFlightResult:
        """
        Executes all pre-flight environment checks.

        Returns:
            PreFlightResult: Structured result indicating success and any error messages.
        """
        result = PreFlightResult(success=True)

        self._check_python_version(result)
        if not result.success:
            return result

        self._verify_and_create_directories(result)

        return result

    def _check_python_version(self, result: PreFlightResult) -> None:
        """
        Verifies if the current Python environment meets the minimum version requirement.
        """
        current_version = sys.version_info

        if current_version < self.MIN_PYTHON_VERSION:
            result.success = False
            result.messages.append(
                f"Python "
                f"{self.MIN_PYTHON_VERSION[0]}.{self.MIN_PYTHON_VERSION[1]} "
                f"or higher is required. "
                f"Found {current_version.major}.{current_version.minor}."
            )

    def _verify_and_create_directories(
        self,
        result: PreFlightResult,
    ) -> None:
        """
        Ensures all required directories exist.

        Missing directories are created automatically.
        All failures are collected instead of stopping on the first one.
        """

        for directory in self.REQUIRED_DIRECTORIES:
            dir_path = self._project_root / directory

            try:
                dir_path.mkdir(parents=True, exist_ok=True)

            except OSError as exception:
                result.success = False
                result.messages.append(
                    f"Failed to verify/create '{directory}': {exception}"
                )

        return
