import pathlib
import re
import subprocess

VERSION_FILE = pathlib.Path("novem/version.py")


def main() -> None:
    next_version = subprocess.check_output(["poetry", "version", "patch", "-s"], text=True).strip()

    content = VERSION_FILE.read_text()
    content = re.sub(r'__version__ = ".*?"', f'__version__ = "{next_version}"', content)
    VERSION_FILE.write_text(content)
    print(f"Version bumped to {next_version}")


if __name__ == "__main__":
    main()
