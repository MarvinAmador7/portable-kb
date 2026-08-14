"""Read and validate the single source of truth for release versions."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

VERSION_PATTERN = re.compile(r'^__version__ = "([0-9]+\.[0-9]+\.[0-9]+)"$', re.MULTILINE)


def read_version(repository: Path) -> str:
    """Return the release version declared by the package."""

    source = (repository / "src/portable_kb/__init__.py").read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(source)
    if match is None:
        raise ValueError("__version__ must be a stable X.Y.Z release version")
    return match.group(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-output", type=Path)
    arguments = parser.parse_args()
    version = read_version(Path.cwd())
    values = f"version={version}\ntag=v{version}\n"
    if arguments.github_output is None:
        print(values, end="")
    else:
        with arguments.github_output.open("a", encoding="utf-8") as output:
            output.write(values)


if __name__ == "__main__":
    main()
