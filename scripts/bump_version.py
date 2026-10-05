import pathlib
import re
import subprocess
import sys

VERSION_FILES = [pathlib.Path("novem/version.py"), pathlib.Path("novem_launcher.py")]


def main() -> None:
    if len(sys.argv) > 1:
        # Use provided version
        next_version = sys.argv[1]
        subprocess.check_call(["uv", "version", next_version])
    else:
        # Default: patch bump
        next_version = subprocess.check_output(["uv", "version", "--bump", "patch", "--short"], text=True).strip()

    for version_file in VERSION_FILES:
        content = version_file.read_text()
        content = re.sub(r'^__version__ = ".*?"', f'__version__ = "{next_version}"', content, flags=re.M)
        version_file.write_text(content)
    print(f"Version bumped to {next_version}")


if __name__ == "__main__":
    main()
