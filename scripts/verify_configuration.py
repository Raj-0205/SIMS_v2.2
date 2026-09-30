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

from core.configuration.service import ConfigService


def main() -> None:
    ConfigService.initialize()

    app = ConfigService.app()
    db = ConfigService.database()

    print("=" * 40)
    print("Configuration Engine Verification")
    print("=" * 40)

    print(f"App Name      : {app.name}")
    print(f"Version       : {app.version}")
    print(f"Environment   : {app.environment.value}")
    print(f"Debug         : {app.debug}")

    print()

    print(f"Database      : {db.engine}")
    print(f"Path          : {db.path}")
    print(f"Journal Mode  : {db.journal_mode}")
    print(f"Foreign Keys  : {db.foreign_keys}")
    print(f"Cache Size    : {db.cache_size}")

    print()
    print("✅ Configuration Engine OK")


if __name__ == "__main__":
    main()
