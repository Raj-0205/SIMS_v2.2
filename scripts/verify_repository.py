import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Auto-detect local virtual environment site-packages if running under system python
for venv_name in (".venv", "venv"):
    for lib_dir in ("lib", "lib64"):
        for sp in (PROJECT_ROOT / venv_name / lib_dir).glob("python*/site-packages"):
            if sp.is_dir() and str(sp) not in sys.path:
                sys.path.insert(0, str(sp))

os.environ["SIMS_ENV"] = "testing"

from core.configuration.service import ConfigService
from core.logger.service import LogService
from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.database.repository import BaseRepository
from core.service.base import BaseService

def main():
    repo = BaseRepository()
    try:
        ConfigService.initialize()
        LogService.initialize()
        DatabaseEngine.initialize()
        MigrationEngine.initialize()
        MigrationEngine.upgrade()

        print("Repository Verification")

        with BaseService.unit_of_work():
            # Guarantee exact schema and completely clean state
            repo.execute("DROP TABLE IF EXISTS __verify_repository_temp")
            repo.execute(
                """
                CREATE TABLE __verify_repository_temp (
                    id INTEGER PRIMARY KEY,
                    data TEXT NOT NULL
                )
                """
            )

            # 1. INSERT
            inserted = repo.execute(
                "INSERT INTO __verify_repository_temp (data) VALUES (?)", 
                ("test_data",)
            )
            if inserted == 1:
                print("INSERT OK")
            else:
                raise Exception("INSERT failed")

            # 2. SELECT
            record = repo.execute_fetchone(
                "SELECT * FROM __verify_repository_temp WHERE data = ?", 
                ("test_data",)
            )
            if record and record["data"] == "test_data":
                print("SELECT OK")
            else:
                raise Exception("SELECT failed")

            # 3. UPDATE
            updated = repo.execute(
                "UPDATE __verify_repository_temp SET data = ? WHERE id = ?", 
                ("updated_data", record["id"])
            )
            if updated == 1:
                print("UPDATE OK")
            else:
                raise Exception("UPDATE failed")

            # 4. DELETE
            deleted = repo.execute(
                "DELETE FROM __verify_repository_temp WHERE id = ?", 
                (record["id"],)
            )
            if deleted == 1:
                print("DELETE OK")
            else:
                raise Exception("DELETE failed")

            # 5. EXISTS
            repo.execute(
                "INSERT INTO __verify_repository_temp (data) VALUES (?)", 
                ("exists_data",)
            )
            exists = repo.exists(
                "SELECT 1 FROM __verify_repository_temp WHERE data = ? LIMIT 1", 
                ("exists_data",)
            )
            if exists:
                print("EXISTS OK")
            else:
                raise Exception("EXISTS failed")

            # Clean up temporary table
            repo.execute("DROP TABLE IF EXISTS __verify_repository_temp")

        print("Repository OK")

    except Exception as exc:
        print(f"❌ Verification Failed: {exc}")
        sys.exit(1)
    finally:
        try:
            repo.execute("DROP TABLE IF EXISTS __verify_repository_temp")
        except Exception as exc:
            print(f"Cleanup Warning: {exc}")
        DatabaseEngine.shutdown()

if __name__ == "__main__":
    main()
