#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path


def _git(*args):
    """Run Git with ``args`` and return its standard output."""
    return subprocess.run(
        ["git", *args], check=True, stdout=subprocess.PIPE, text=True
    ).stdout


def deleted_files(ref):
    """Return deleted paths at ``ref`` mapped to their last first-parent blob."""
    output = _git("log", ref, "--diff-filter=D", "--format=commit:%H", "--name-only")
    result = {}
    commit = None
    for line in output.splitlines():
        if line.startswith("commit:"):
            commit = line.removeprefix("commit:")
        elif line and commit and line not in result:
            try:
                result[line] = _git("rev-parse", f"{commit}^:{line}").strip()
            except subprocess.CalledProcessError:
                print(f"Skipping {line}: no blob in the first parent of {commit}")
    return result


def main():
    """Generate the obsolete-file inventory from command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Write hashes for every file deleted from a git branch."
    )
    parser.add_argument("--ref", default="main", help="branch or revision to scan")
    parser.add_argument("--output", default="obsolete_files.json")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.write_text(
        json.dumps(deleted_files(args.ref), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
