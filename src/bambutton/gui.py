#!/usr/bin/env python3
import contextlib
import io
import json
import sys
import time
from pathlib import Path

import serial.tools.list_ports

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

            if event == "-REFRESH_BOARDS-":
                refresh_boards(window)

            elif event == "-FLASH-":
                try:
                    board = normalize_serial_port(values.get("-BOARD-"))
                    firmware_path = validate_firmware(first_firmware_file())
                    config_path = config_path_for_mode(values)
                    flash_board(board, firmware_path, config_path)
                    sg.popup("Firmware and project files flashed.")
                except Exception as exc:
                    sg.popup_error("Could not flash firmware", str(exc))
    finally:
        window.close()


def build_window():
    sg.theme("SystemDefault")

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
                        ),
                        sg.Text("Flash generic firmware, then configure the board in its web GUI."),
                    ],
                    [
                        sg.Radio(
                            "Config based setup",
                            "SETUP_MODE",
                            key="-CONFIG-",
                            enable_events=True,
                        ),
                        sg.Text("Flash generic firmware with an existing config.json file."),
                    ],
                ],
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                "Board",
                [
                    [
                        sg.Text("Serial port (optional)", size=(20, 1)),
                        sg.Combo([], key="-BOARD-", size=(32, 1), enable_events=True),
                        sg.Button("Refresh boards", key="-REFRESH_BOARDS-"),
                    ],
                    [sg.Text("Leave blank to auto-detect the connected ESP32-C3.")],
                ],
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
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                "Flash",
                [
                    [sg.Button("Flash", key="-FLASH-", disabled=True), sg.Button("Exit")],
                    [sg.Text("", key="-VALIDATION-", text_color="firebrick", size=(72, 2))],
                ],
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


def refresh_boards(window, show_errors=True):
    try:
        boards = list_boards()
        window["-BOARD-"].update(values=boards, value=boards[0] if len(boards) == 1 else "")
    except Exception as exc:
        window["-BOARD-"].update(values=[], value="")
        if show_errors:
            sg.popup_error("Could not list boards", str(exc))


def list_boards():
    boards = []

    for port in sorted(serial.tools.list_ports.comports()):
        if port.device:
            boards.append(port.device)

    return boards


def flash_board(board, firmware_path, config_path):
    board = normalize_serial_port(board)
    firmware_path = validate_firmware(firmware_path)
    if config_path is not None:
        config_path = validate_config_file(config_path)

    flash_firmware(board, firmware_path)
    time.sleep(FIRMWARE_RESTART_DELAY_SECONDS)
    push_micro_files(board, config_path, clean=True)


def flash_firmware(board, firmware_path):
    run_esptool(esptool_args(board, "erase_flash"))
    run_esptool(esptool_args(board, "write_flash", "-z", "0x0", str(firmware_path)))


def push_micro_files(board, config_path, clean=False):
    if config_path is not None:
        config_path = validate_config_file(config_path)

    if clean:
        run_mpremote(mpremote_args(board, "exec", CLEAN_BOARD_CODE))

    for path in sorted(MICRO_DIR.glob("*.py")):
        run_mpremote(mpremote_args(board, "cp", str(path), ":"))

    if config_path is not None:
        run_mpremote(mpremote_args(board, "cp", str(config_path), ":config.json"))
    run_mpremote(mpremote_args(board, "reset"))


def mpremote_args(board, *args):
    board = normalize_serial_port(board)
    if board:
        return ["connect", board] + list(args)

    return list(args)


def esptool_args(board, *args):
    command = ["--chip", "esp32c3"]
    board = normalize_serial_port(board)
    if board:
        command.extend(["--port", board])

    return command + list(args)


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


def normalize_serial_port(board):
    if board is None:
        return None

    board = str(board).strip()
    return board or None


def first_firmware_file():
    firmware_files = sorted(DEFAULT_FIRMWARE_DIR.glob("*.bin"))
    if firmware_files:
        return firmware_files[0]

    return ""


if __name__ == "__main__":
    main()
