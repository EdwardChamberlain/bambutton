#!/usr/bin/env python3
import contextlib
import io
import json
import sys
import time
from pathlib import Path

try:
    import FreeSimpleGUI as sg
except ImportError:
    print("FreeSimpleGUI is not installed. Run: python -m pip install -r requirements.txt")
    raise


PACKAGE_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = Path(__file__).resolve().parents[2]
if hasattr(sys, "_MEIPASS"):
    RESOURCE_ROOT = Path(sys._MEIPASS) / "bambutton"
else:
    RESOURCE_ROOT = SOURCE_ROOT if (SOURCE_ROOT / "micro").exists() else PACKAGE_ROOT

MICRO_DIR = RESOURCE_ROOT / "micro"
DEFAULT_FIRMWARE_DIR = RESOURCE_ROOT / "firmware"
FIRMWARE_RESTART_DELAY_SECONDS = 2

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
    window = build_window()

    try:
        while True:
            event, values = window.read(timeout=250)
            if event in (sg.WIN_CLOSED, "Exit"):
                break

            update_action_states(window, values)

            if event == "-FLASH-":
                try:
                    firmware_path = validate_firmware(first_firmware_file())
                    config_path = config_path_for_mode(values)
                    flash_board(firmware_path, config_path)
                    sg.popup("Firmware and project files flashed.")
                except Exception as exc:
                    sg.popup_error("Could not flash firmware", str(exc))
    finally:
        window.close()


def build_window():
    sg.theme("LightBlue3")
    sg.set_options(
        font=("Helvetica", 11),
        element_padding=(6, 5),
        margins=(18, 18),
    )

    layout = [
        [
            sg.Frame(
                "Setup mode",
                [
                    [
                        sg.Radio(
                            "Web GUI setup",
                            "SETUP_MODE",
                            default=True,
                            key="-WEB-",
                            enable_events=True,
                            size=(24, 1),
                            pad=(0, 5),
                        ),
                        sg.Text(
                            "Flash generic firmware, then configure the board in its web GUI.",
                            expand_x=True,
                            pad=(12, 5),
                        ),
                    ],
                    [
                        sg.Radio(
                            "Config based setup",
                            "SETUP_MODE",
                            key="-CONFIG-",
                            enable_events=True,
                            size=(24, 1),
                            pad=(0, 5),
                        ),
                        sg.Text(
                            "Flash generic firmware with an existing config.json file.",
                            expand_x=True,
                            pad=(12, 5),
                        ),
                    ],
                ],
                pad=(0, 8),
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                "Configuration file",
                [
                    [
                        sg.Text("config.json", size=(16, 1)),
                        sg.Input(key="-CONFIG_PATH-", enable_events=True, visible=False, expand_x=True),
                        sg.FileBrowse(
                            "Browse",
                            key="-CONFIG_BROWSE-",
                            target="-CONFIG_PATH-",
                            file_types=(("JSON configuration", "*.json"), ("All files", "*.*")),
                            visible=False,
                        ),
                    ],
                ],
                key="-CONFIG_FRAME-",
                visible=False,
                pad=(0, 8),
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                "Flash",
                [
                    [
                        sg.Button(
                            "Flash",
                            key="-FLASH-",
                            disabled=True,
                            size=(12, 1),
                            expand_x=True,
                            pad=(0, 6),
                        )
                    ],
                    [
                        sg.Text(
                            "",
                            key="-VALIDATION-",
                            text_color="firebrick",
                            size=(72, 2),
                            expand_x=True,
                            pad=(0, 8),
                        )
                    ],
                    [sg.Text("", expand_x=True), sg.Button("Exit", size=(12, 1), pad=(0, 6))],
                ],
                pad=(0, 8),
                expand_x=True,
            )
        ],
    ]

    window = sg.Window("Bambutton Setup", layout, finalize=True)
    update_action_states(window, window.read(timeout=0)[1])
    return window


def update_action_states(window, values):
    values = values or {}
    config_mode = values.get("-CONFIG-", False)

    window["-CONFIG_FRAME-"].update(visible=config_mode)
    window["-CONFIG_PATH-"].update(visible=config_mode)
    window["-CONFIG_BROWSE-"].update(visible=config_mode)

    errors = collect_basic_errors(values)
    window["-FLASH-"].update(disabled=bool(errors))
    window["-VALIDATION-"].update(errors[0] if errors else "")


def collect_basic_errors(values):
    errors = []

    if values.get("-CONFIG-"):
        try:
            validate_config_file(values.get("-CONFIG_PATH-", ""))
        except ValueError as exc:
            errors.append(str(exc))

    return errors


def config_path_for_mode(values):
    if values.get("-CONFIG-"):
        return validate_config_file(values.get("-CONFIG_PATH-", ""))

    return None


def validate_config_file(path):
    config_path = Path(path).expanduser()
    if not config_path.is_file():
        raise ValueError("Choose a config.json file.")
    if config_path.suffix.lower() != ".json":
        raise ValueError("Configuration file must end in .json.")

    try:
        with config_path.open() as config_file:
            config = json.load(config_file)
    except (OSError, ValueError):
        raise ValueError("Configuration file must contain valid JSON.")

    if not isinstance(config, dict):
        raise ValueError("Configuration file must contain a JSON object.")

    return config_path


def flash_board(firmware_path, config_path):
    firmware_path = validate_firmware(firmware_path)
    if config_path is not None:
        config_path = validate_config_file(config_path)

    flash_firmware(firmware_path)
    time.sleep(FIRMWARE_RESTART_DELAY_SECONDS)
    push_micro_files(config_path, clean=True)


def flash_firmware(firmware_path):
    run_esptool(esptool_args("erase_flash"))
    run_esptool(esptool_args("write_flash", "-z", "0x0", str(firmware_path)))


def push_micro_files(config_path, clean=False):
    if config_path is not None:
        config_path = validate_config_file(config_path)

    if clean:
        run_mpremote(mpremote_args("exec", CLEAN_BOARD_CODE))

    for path in sorted(MICRO_DIR.glob("*.py")):
        run_mpremote(mpremote_args("cp", str(path), ":"))

    if config_path is not None:
        run_mpremote(mpremote_args("cp", str(config_path), ":config.json"))
    run_mpremote(mpremote_args("reset"))


def mpremote_args(*args):
    return list(args)


def esptool_args(*args):
    return ["--chip", "esp32c3"] + list(args)


def run_mpremote(args, capture=False):
    import mpremote.main

    return run_python_entrypoint("mpremote", mpremote.main.main, args, capture)


def run_esptool(args, capture=False):
    import esptool

    return run_python_entrypoint("esptool", esptool._main, args, capture)


def run_python_entrypoint(name, entrypoint, args, capture=False):
    old_argv = sys.argv
    stdout = CapturedText()
    stderr = CapturedText()
    sys.argv = [name] + list(args)

    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = call_entrypoint(entrypoint)
    finally:
        sys.argv = old_argv

    if exit_code:
        message = stderr.getvalue() or stdout.getvalue() or "{} failed".format(name)
        raise RuntimeError(message.strip())

    return ToolResult(stdout.getvalue(), stderr.getvalue())


def call_entrypoint(entrypoint):
    try:
        result = entrypoint()
    except SystemExit as exc:
        if exc.code is None:
            return 0
        if isinstance(exc.code, int):
            return exc.code
        return 1

    return result or 0


class ToolResult:
    def __init__(self, stdout="", stderr=""):
        self.stdout = stdout
        self.stderr = stderr


class CapturedText(io.StringIO):
    encoding = "utf-8"


def validate_firmware(path):
    firmware_path = Path(path).expanduser()
    if not firmware_path.is_file():
        raise ValueError("Choose a firmware .bin file.")
    if firmware_path.suffix.lower() != ".bin":
        raise ValueError("Firmware file must end in .bin.")
    return firmware_path


def first_firmware_file():
    firmware_files = sorted(DEFAULT_FIRMWARE_DIR.glob("*.bin"))
    if firmware_files:
        return firmware_files[0]

    return ""


if __name__ == "__main__":
    main()
