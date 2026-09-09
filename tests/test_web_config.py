import json

import pytest

from micro import web_config


def base_config():
    return {
        "wifi": {
            "ssid": "old-network",
            "password": "old-password",
            "hostname": "bambutton",
            "timeout_seconds": 10,
        },
        "api": {
            "base_url": "http://old-host:8000/api/v1",
            "key": "old-key",
            "request_timeout_seconds": 3,
        },
        "printer": {"id": 1, "poll_interval_seconds": 3},
        "led": {"pin": 3, "flash_interval_ms": 250},
        "button": {"pin": 4, "debounce_ms": 150, "pull": "down", "trigger": "rising"},
    }


def valid_form():
    return {
        "hostname": "shop-button",
        "wifi_ssid": "new network",
        "wifi_password": "new-password",
        "api_base_url": "http://new-host:8000/api/v1/",
        "api_key": "new-key",
        "printer_id": "7",
        "led_pin": "5",
        "button_pin": "6",
    }


def test_parse_form_decodes_url_encoded_values():
    assert web_config.parse_form("wifi_ssid=shop+wifi&api_key=a%2Bb") == {
        "wifi_ssid": "shop wifi",
        "api_key": "a+b",
    }


def test_build_config_updates_web_fields_and_preserves_other_settings():
    current = base_config()

    updated = web_config.build_config(valid_form(), current)

    assert updated["wifi"] == {
        "ssid": "new network",
        "password": "new-password",
        "hostname": "shop-button",
        "timeout_seconds": 10,
    }
    assert updated["api"]["base_url"] == "http://new-host:8000/api/v1"
    assert updated["api"]["key"] == "new-key"
    assert updated["printer"]["id"] == 7
    assert updated["led"]["pin"] == 5
    assert updated["button"]["pin"] == 6
    assert current["printer"]["id"] == 1
    assert current["api"]["base_url"] == "http://old-host:8000/api/v1"


def test_blank_secrets_keep_existing_values():
    current = base_config()
    form = valid_form()
    form["wifi_password"] = ""
    form["api_key"] = ""

    updated = web_config.build_config(form, current)

    assert updated["wifi"]["password"] == "old-password"
    assert updated["api"]["key"] == "old-key"


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("hostname", "bad name", "Hostname may contain only letters, numbers, and hyphens."),
        ("api_base_url", "new-host:8000", "API base URL must start with http:// or https:// and contain no spaces."),
        ("led_pin", "22", "LED pin must be between 0 and 21."),
        ("button_pin", "5", "LED pin and button pin must be different."),
    ],
)
def test_build_config_rejects_invalid_values(field, value, error):
    form = valid_form()
    form[field] = value

    with pytest.raises(ValueError, match=error):
        web_config.build_config(form, base_config())


def test_save_config_writes_json(tmp_path):
    path = tmp_path / "config.json"
    config = base_config()

    web_config.save_config(str(path), config)

    assert json.loads(path.read_text()) == config


def test_config_page_contains_form_and_does_not_require_formatting_js():
    page = web_config.render_config_page(base_config())

    assert 'action="/save"' in page
    assert 'name="hostname"' in page
    assert 'fetch("/api/printers")' in page
    assert "__HOSTNAME__" not in page


def test_debug_page_does_not_expose_secrets():
    page = web_config.render_debug_page(base_config(), {"IP address": "192.168.1.20"})

    assert "old-password" not in page
    assert "old-key" not in page
    assert "192.168.1.20" in page


def test_save_request_sets_restart_flag_and_returns_updated_page(tmp_path):
    server = object.__new__(web_config.WebConfigServer)
    server.config = base_config()
    server.api = None
    server.status_provider = lambda: {}
    server.config_path = str(tmp_path / "config.json")
    server.restart_requested = False

    status, content_type, page = server.handle_request(
        "POST",
        "/save",
        "&".join("{}={}".format(key, value) for key, value in valid_form().items()),
    )

    assert status == 200
    assert content_type.startswith("text/html")
    assert server.restart_requested is True
    assert "shop-button" in page
    assert json.loads((tmp_path / "config.json").read_text())["printer"]["id"] == 7
