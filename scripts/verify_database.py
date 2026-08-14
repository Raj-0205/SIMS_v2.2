# scripts/verify_database.py

import sys
import sqlite3

from core.configuration.service import ConfigService
from core.logger.service import LogService
from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.database.transaction import TransactionManager
from core.database.repository import BaseRepository
from core.database.exceptions import DatabaseExecutionError

class VerificationError(Exception):
    """Custom exception for verification script failures."""
    pass

def print_status(label: str, status: str = "OK"):
    """Helper to maintain strict deterministic console output alignment."""
    print(f"{label} ".ljust(27, '.') + f" {status}")

def main():
    print("========================================")
    print("SIMS Database Stack Verification")
    print("========================================\n")

    repo = BaseRepository()
    table_name = "__verify_db_stack"
    cleanup_failed = False

    try:
        # 1. Bootstrap
        ConfigService.initialize()
        print_status("Configuration")

        LogService.initialize()
        print_status("Logger")

        DatabaseEngine.initialize()
        print_status("Database Engine")

        MigrationEngine.initialize()
        MigrationEngine.upgrade()
        
        # 2. Migration Verification
        version = MigrationEngine.current_version()
        if version < 0:
            raise VerificationError("Invalid migration version returned.")
        
        migration = MigrationEngine.current_migration()
        if version > 0 and migration is None:
            raise VerificationError("Migration info missing despite version > 0.")
            
        print_status("Migration Engine")

        print("\nRepository")
        
        # Setup Temporary Verification Table (Autonomous execution)
        repo.execute_script(f"""
            DROP TABLE IF EXISTS {table_name};
            CREATE TABLE {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL
            );
        """)

        # 3 & 6. Repository & Autonomous Verification
        # INSERT
        inserted = repo.execute(f"INSERT INTO {table_name} (data) VALUES (?)", ("test_insert",))
        if inserted != 1: raise VerificationError("INSERT did not return deterministic rowcount")
        print_status("  INSERT")

        # SELECT
        record = repo.fetch_one(f"SELECT * FROM {table_name} WHERE data = ?", ("test_insert",))
        if not record or record["data"] != "test_insert": raise VerificationError("SELECT failed to return valid dict")
        print_status("  SELECT")

        # UPDATE
        updated = repo.execute(f"UPDATE {table_name} SET data = ? WHERE id = ?", ("updated_data", record["id"]))
        if updated != 1: raise VerificationError("UPDATE did not return deterministic rowcount")
        print_status("  UPDATE")

        # DELETE
        deleted = repo.execute(f"DELETE FROM {table_name} WHERE id = ?", (record["id"],))
        if deleted != 1: raise VerificationError("DELETE did not return deterministic rowcount")
        print_status("  DELETE")

        # EXISTS
        repo.execute(f"INSERT INTO {table_name} (data) VALUES (?)", ("exists_data",))
        exists = repo.exists(f"SELECT 1 FROM {table_name} WHERE data = ?", ("exists_data",))
        if not exists: raise VerificationError("EXISTS failed to evaluate correctly")
        print_status("  EXISTS")

        # COUNT
        count = repo.count(f"SELECT COUNT(*) FROM {table_name}")
        if not isinstance(count, int) or count < 1: raise VerificationError("COUNT failed to return integer scalar")
        print_status("  COUNT")

        # EXECUTE_MANY
        many_data = [("many_1",), ("many_2",), ("many_3",)]
        many_inserted = repo.execute_many(f"INSERT INTO {table_name} (data) VALUES (?)", many_data)
        if many_inserted != 3: raise VerificationError("EXECUTE_MANY did not return accurate delta sum")
        print_status("  EXECUTE MANY")

        print("\nTransaction")
        # 4. Transaction Verification (Commit)
        TransactionManager.begin()
        print_status("  BEGIN")
        
        repo.execute(f"INSERT INTO {table_name} (data) VALUES (?)", ("txn_commit",))
        TransactionManager.commit()
        
        txn_record = repo.fetch_one(f"SELECT * FROM {table_name} WHERE data = ?", ("txn_commit",))
        if not txn_record: raise VerificationError("Transaction COMMIT failed to persist data")
        print_status("  COMMIT")

        # 5. Rollback Verification
        TransactionManager.begin()
        repo.execute(f"INSERT INTO {table_name} (data) VALUES (?)", ("txn_rollback",))
        TransactionManager.rollback()
        
        rb_record = repo.fetch_one(f"SELECT * FROM {table_name} WHERE data = ?", ("txn_rollback",))
        if rb_record: raise VerificationError("Transaction ROLLBACK failed, data incorrectly persisted")
        print_status("  ROLLBACK")

        print("")
        # 7. Error Translation
        try:
            repo.execute("SELECT * FROM invalid_table_name_for_verification")
            raise VerificationError("Error Translation failed: Statement executed without exception")
        except DatabaseExecutionError:
            pass # Successfully translated
        except sqlite3.Error as exc:
            raise VerificationError(f"Error Translation failed: Leaked sqlite3.Error to application layer: {exc}")
        except VerificationError:
            raise
        except Exception as exc:
            raise VerificationError(f"Error Translation failed: Raised unexpected generic exception type: {type(exc)}")
        print_status("Error Translation")

        print("\n========================================")
        print("DATABASE STACK VERIFIED")
        print("========================================")

    except VerificationError as exc:
        print(f"\n❌ Verification Failed: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\n❌ Unexpected System Error: {exc}")
        sys.exit(1)
    finally:
        # 8. Guaranteed Cleanup
        if DatabaseEngine.is_initialized():
            try:
                repo.execute_script(f"DROP TABLE IF EXISTS {table_name};")
            except Exception:
                pass
            
            try:
                DatabaseEngine.shutdown()
            except Exception:
                pass

            print_status("Cleanup")

        # Final state verification isolated outside the block
        if DatabaseEngine.is_initialized():
            cleanup_failed = True

    if cleanup_failed:
        print("\n❌ Verification Failed: DatabaseEngine failed to shut down completely.")
        sys.exit(1)

if __name__ == "__main__":
    main()
