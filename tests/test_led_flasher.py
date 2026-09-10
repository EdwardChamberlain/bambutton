import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


LED_FLASHER_PATH = Path(__file__).parents[1] / "micro" / "led_flasher.py"


def load_led_flasher_module(monkeypatch):
    class FakePin:
        OUT = "out"

        def __init__(self, pin_number, mode):
            self.pin_number = pin_number
            self.mode = mode
            self.state = 0

        def value(self, value=None):
            if value is not None:
                self.state = value
            return self.state

    class FakePeriodicTimer:
        def __init__(self, period_ms, callback):
            self.period_ms = period_ms
            self.callback = callback

        def start(self):
            pass

        def stop(self):
            pass

    monkeypatch.setitem(sys.modules, "machine", SimpleNamespace(Pin=FakePin))
    monkeypatch.setitem(
        sys.modules,
        "periodic_timer",
        SimpleNamespace(PeriodicTimer=FakePeriodicTimer),
    )

    spec = importlib.util.spec_from_file_location(
        "test_led_flasher_module", LED_FLASHER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_connection_failure_flashes_twice_as_fast_as_plate_clear(monkeypatch):
    led_flasher_module = load_led_flasher_module(monkeypatch)
    flasher = led_flasher_module.LedFlasher(
        pin_number=3,
        should_flash=lambda: False,
        fast_should_flash=lambda: True,
        interval_ms=250,
    )

    assert flasher.timer.period_ms == 125
    flasher._tick()
    assert flasher.led.value() == 1
    flasher._tick()
    assert flasher.led.value() == 0


def test_plate_clear_keeps_the_normal_flash_rate(monkeypatch):
    led_flasher_module = load_led_flasher_module(monkeypatch)
    flasher = led_flasher_module.LedFlasher(
        pin_number=3,
        should_flash=lambda: True,
        fast_should_flash=lambda: False,
        interval_ms=250,
    )

    assert flasher.timer.period_ms == 125
    flasher._tick()
    assert flasher.led.value() == 0
    flasher._tick()
    assert flasher.led.value() == 1
    flasher._tick()
    assert flasher.led.value() == 1
    flasher._tick()
    assert flasher.led.value() == 0


def test_flasher_without_fast_mode_keeps_its_existing_interval(monkeypatch):
    led_flasher_module = load_led_flasher_module(monkeypatch)
    flasher = led_flasher_module.LedFlasher(
        pin_number=3,
        should_flash=lambda: True,
        interval_ms=250,
    )

    assert flasher.timer.period_ms == 250
    flasher._tick()
    assert flasher.led.value() == 1
