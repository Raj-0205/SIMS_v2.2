# @Final
# File: scripts/verify_configuration.py
# Status: NEW

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
