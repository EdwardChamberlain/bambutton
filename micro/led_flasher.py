from machine import Pin
from periodic_timer import PeriodicTimer


class LedFlasher:
    def __init__(
        self,
        pin_number,
        should_flash,
        interval_ms=250,
        inactive_value=0,
        fast_should_flash=None,
    ):
        self.led = Pin(pin_number, Pin.OUT)
        self.should_flash = should_flash
        self.fast_should_flash = fast_should_flash
        self.interval_ms = interval_ms
        self.inactive_value = inactive_value
        self._normal_flash_phase = False
        timer_interval_ms = (
            max(1, self.interval_ms // 2)
            if self.fast_should_flash is not None
            else self.interval_ms
        )
        self.timer = PeriodicTimer(timer_interval_ms, self._tick)

    def start(self):
        self.timer.start()

    def stop(self, led_value=None):
        self.timer.stop()

        if led_value is not None:
            self.led.value(led_value)

    def on(self):
        self.led.value(1)

    def off(self):
        self.led.value(0)

    def _tick(self):
        if self.fast_should_flash is None:
            if self.should_flash():
                self._toggle()
            else:
                self._set_inactive()
            return

        if self.fast_should_flash():
            self._normal_flash_phase = False
            self._toggle()
        elif self.should_flash():
            if self._normal_flash_phase:
                self._toggle()
            self._normal_flash_phase = not self._normal_flash_phase
        else:
            self._normal_flash_phase = False
            self._set_inactive()

    def _toggle(self):
        self.led.value(not self.led.value())

    def _set_inactive(self):
        if callable(self.inactive_value):
            self.led.value(self.inactive_value())
        else:
            self.led.value(self.inactive_value)
