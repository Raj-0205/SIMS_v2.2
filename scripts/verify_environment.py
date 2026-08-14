import importlib
import platform
import sys

REQUIRED = {
    "flet": "0.85.3",
    "pydantic": "2.13.4",
    "yaml": None,
    "httpx": "0.28.1",
    "msgpack": "1.2.1",
}


def check_package(name, expected):
    try:
        module = importlib.import_module(name)
        version = getattr(module, "__version__", "Unknown")

        if expected and version != expected:
            print(f"[WARN] {name}: {version} (expected {expected})")
        else:
            print(f"[ OK ] {name}: {version}")

    except ImportError:
        print(f"[FAIL] {name}: Not Installed")
        return False

    return True


def main():
    print("SIMS Environment Verification")
    print("-" * 40)
    print(f"Python : {platform.python_version()}")
    print()

    success = True

    for pkg, version in REQUIRED.items():
        success &= check_package(pkg, version)

    print()

    if success:
        print("Environment OK")
        sys.exit(0)

    print("Environment FAILED")
    sys.exit(1)


if __name__ == "__main__":
    main()
