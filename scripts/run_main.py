#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_FILE = PROJECT_ROOT / "micro" / "main.py"


def main():
    parser = argparse.ArgumentParser(
        description="Run micro/main.py on the connected board with mpremote.",
    )
    parser.add_argument(
        "--device",
        help="Optional mpremote device/port, for example /dev/tty.usbmodemXXXX.",
    )
    args = parser.parse_args()

    if not MAIN_FILE.exists():
        raise SystemExit("main.py not found: {}".format(MAIN_FILE))

    command = ["mpremote"]
    if args.device:
        command.extend(["connect", args.device])

    command.extend(["run", str(MAIN_FILE)])
    run(command)


def run(command):
    print("+", " ".join(command))
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
