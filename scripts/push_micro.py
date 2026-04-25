#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MICRO_DIR = PROJECT_ROOT / "micro"
CONFIG_FILE = MICRO_DIR / "config.json"

CLEAN_BOARD_CODE = """
import os


def remove(path):
    try:
        mode = os.stat(path)[0]
        is_dir = mode & 0x4000
    except OSError:
        return

    if is_dir:
        for name in os.listdir(path):
            remove(path + "/" + name)
        os.rmdir(path)
    else:
        os.remove(path)


for name in os.listdir():
    remove(name)
"""


def main():
    parser = argparse.ArgumentParser(
        description="Push MicroPython application files to the connected board.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete all files from the board filesystem before copying files.",
    )
    parser.add_argument(
        "--device",
        help="Optional mpremote device/port, for example /dev/tty.usbmodemXXXX.",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not reset the board after copying files.",
    )
    parser.add_argument(
        "--no-main",
        "--nomain",
        dest="no_main",
        action="store_true",
        help="Do not copy main.py, preventing the application from auto-starting.",
    )
    args = parser.parse_args()

    files = sorted(MICRO_DIR.glob("*.py"))
    if args.no_main:
        files = [path for path in files if path.name != "main.py"]

    if CONFIG_FILE.exists():
        files.append(CONFIG_FILE)

    if not files:
        raise SystemExit("No files found to copy from {}".format(MICRO_DIR))

    mpremote_prefix = ["mpremote"]
    if args.device:
        mpremote_prefix.extend(["connect", args.device])

    if args.clean:
        run(mpremote_prefix + ["exec", CLEAN_BOARD_CODE])

    for path in files:
        run(mpremote_prefix + ["cp", str(path), ":"])

    if not args.no_reset:
        run(mpremote_prefix + ["reset"])


def run(command):
    print("+", " ".join(command))
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
