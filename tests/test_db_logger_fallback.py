import sys
import pytest
from unittest.mock import MagicMock, patch
from core.database.engine import DatabaseEngine
from core.logger.service import LogService

def test_db_logger_info_fallback():
    """Verify that _DBLogger.info falls back to stderr when LogService fails."""
    with patch("core.logger.service.LogService.info", side_effect=Exception("LogService Crash")):
        with patch("sys.stderr", new_callable=MagicMock()) as mock_stderr:
            DatabaseEngine._DBLogger.info("Test Info Message")
            # Check if stderr was written to. Since print() might call write multiple times
            # (e.g. for the string and the newline), we check the joined output.
            actual_output = "".join(call.args[0] for call in mock_stderr.write.call_args_list)
            assert "[DATABASE_EMERGENCY_LOG] INFO: Test Info Message (LogService failed: LogService Crash)" in actual_output

def test_db_logger_warning_fallback():
    """Verify that _DBLogger.warning falls back to stderr when LogService fails."""
    with patch("core.logger.service.LogService.warning", side_effect=Exception("LogService Crash")):
        with patch("sys.stderr", new_callable=MagicMock()) as mock_stderr:
            DatabaseEngine._DBLogger.warning("Test Warning Message")
            actual_output = "".join(call.args[0] for call in mock_stderr.write.call_args_list)
            assert "[DATABASE_EMERGENCY_LOG] WARNING: Test Warning Message (LogService failed: LogService Crash)" in actual_output

def test_db_logger_error_fallback():
    """Verify that _DBLogger.error falls back to stderr when LogService fails."""
    with patch("core.logger.service.LogService.error", side_effect=Exception("LogService Crash")):
        with patch("sys.stderr", new_callable=MagicMock()) as mock_stderr:
            DatabaseEngine._DBLogger.error("Test Error Message")
            actual_output = "".join(call.args[0] for call in mock_stderr.write.call_args_list)
            assert "[DATABASE_EMERGENCY_LOG] ERROR: Test Error Message (LogService failed: LogService Crash)" in actual_output

def test_db_logger_primary_works():
    """Verify that _DBLogger still uses LogService when it's working."""
    with patch("core.logger.service.LogService.info") as mock_info:
        with patch("sys.stderr", new_callable=MagicMock()) as mock_stderr:
            DatabaseEngine._DBLogger.info("Normal Message")
            mock_info.assert_called_once_with("Normal Message", context="DATABASE")
            # Stderr should NOT have been written to
            assert mock_stderr.write.call_count == 0
