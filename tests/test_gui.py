import json
import sys

import pytest

from bambutton import gui
from bambutton.gui import run_python_entrypoint


def test_run_python_entrypoint_exposes_utf8_stream_encoding():
    def entrypoint():
        sys.stdout.write(b"ok".decode(sys.stdout.encoding))
        sys.stderr.write(b"warn".decode(sys.stderr.encoding))

    result = run_python_entrypoint("tool", entrypoint, [])

    assert result.stdout == "ok"
    assert result.stderr == "warn"


def test_web_setup_uses_firmware_defaults_without_a_saved_config():
    assert gui.config_path_for_mode({"-WEB-": True}) is None


def test_web_setup_does_not_require_serial_port():
    assert gui.collect_basic_errors({"-WEB-": True}) == []


def test_config_setup_requires_a_config_file_before_flashing():
    assert gui.collect_basic_errors({"-CONFIG-": True}) == ["Choose a config.json file."]


def test_update_action_states_disables_config_controls_in_web_mode(tmp_path):
    class Element:
        def __init__(self):
            self.updates = []

        def update(self, **kwargs):
            self.updates.append(kwargs)

    class Window:
        def __init__(self):
            self.elements = {key: Element() for key in ("-CONFIG_PATH-", "-CONFIG_BROWSE-", "-FLASH-")}

        def __getitem__(self, key):
            return self.elements[key]

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"wifi": {}}))
    window = Window()

    gui.update_action_states(window, {"-WEB-": True})
    assert window.elements["-CONFIG_PATH-"].updates[-1] == {"disabled": True}
    assert window.elements["-CONFIG_BROWSE-"].updates[-1] == {"disabled": True}
    assert window.elements["-FLASH-"].updates[-1] == {"disabled": False}

    gui.update_action_states(
        window,
        {"-CONFIG-": True, "-CONFIG_PATH-": str(config_path)},
    )
    assert window.elements["-CONFIG_PATH-"].updates[-1] == {"disabled": False}
    assert window.elements["-CONFIG_BROWSE-"].updates[-1] == {"disabled": False}
    assert window.elements["-FLASH-"].updates[-1] == {"disabled": False}


def test_config_setup_requires_a_json_object(tmp_path):
    config_path = tmp_path / "saved-config.json"
    config_path.write_text(json.dumps({"wifi": {"ssid": "shop"}}))

    assert gui.config_path_for_mode({"-CONFIG-": True, "-CONFIG_PATH-": str(config_path)}) == config_path


@pytest.mark.parametrize(
    "contents,error",
    [
        ("not json", "valid JSON"),
        ("[]", "JSON object"),
    ],
)
def test_validate_config_file_rejects_invalid_files(tmp_path, contents, error):
    config_path = tmp_path / "config.json"
    config_path.write_text(contents)

    with pytest.raises(ValueError, match=error):
        gui.validate_config_file(config_path)


def test_push_micro_files_installs_selected_file_as_config_json(tmp_path, monkeypatch):
    micro_dir = tmp_path / "micro"
    micro_dir.mkdir()
    (micro_dir / "b_module.py").write_text("# b")
    (micro_dir / "a_module.py").write_text("# a")
    config_path = tmp_path / "saved-config.json"
    config_path.write_text(json.dumps({"wifi": {"ssid": "shop"}}))
    calls = []

    monkeypatch.setattr(gui, "MICRO_DIR", micro_dir)
    monkeypatch.setattr(gui, "run_mpremote", lambda args, capture=False: calls.append(args))

    gui.push_micro_files(config_path, clean=True)

    assert calls[0][0] == "exec"
    assert calls[1][1:] == [str(micro_dir / "a_module.py"), ":"]
    assert calls[2][1:] == [str(micro_dir / "b_module.py"), ":"]
    assert calls[3][1:] == [str(config_path), ":config.json"]
    assert calls[4] == ["reset"]


def test_push_micro_files_omits_config_for_web_gui_setup(tmp_path, monkeypatch):
    micro_dir = tmp_path / "micro"
    micro_dir.mkdir()
    (micro_dir / "main.py").write_text("# main")
    calls = []

    monkeypatch.setattr(gui, "MICRO_DIR", micro_dir)
    monkeypatch.setattr(gui, "run_mpremote", lambda args, capture=False: calls.append(args))

    gui.push_micro_files(None, clean=True)

    assert [call[0] for call in calls] == ["exec", "cp", "reset"]


def test_mpremote_args_uses_auto_detection():
    assert gui.mpremote_args("reset") == ["reset"]


def test_esptool_args_uses_auto_detection():
    assert gui.esptool_args("erase_flash") == ["--chip", "esp32c3", "erase_flash"]


def test_flash_board_flashes_firmware_before_application_files(tmp_path, monkeypatch):
    firmware_path = tmp_path / "firmware.bin"
    firmware_path.write_bytes(b"firmware")
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"wifi": {}}))
    events = []

    monkeypatch.setattr(gui, "flash_firmware", lambda path: events.append(("firmware", path)))
    monkeypatch.setattr(gui.time, "sleep", lambda seconds: events.append(("sleep", seconds)))
    monkeypatch.setattr(
        gui,
        "push_micro_files",
        lambda path, clean=False: events.append(("files", path, clean)),
    )

    gui.flash_board(firmware_path, config_path)

    assert events == [
        ("firmware", firmware_path),
        ("sleep", gui.FIRMWARE_RESTART_DELAY_SECONDS),
        ("files", config_path, True),
    ]
