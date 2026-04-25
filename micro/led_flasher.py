from machine import Pin, Timer


class LedFlasher:
    def __init__(
        self,
        pin_number,
        should_flash,
        interval_ms=250,
        timer_id=0,
        inactive_value=0,
    ):
        self.led = Pin(pin_number, Pin.OUT)
        self.should_flash = should_flash
        self.interval_ms = interval_ms
        self.inactive_value = inactive_value
        self.timer = Timer(timer_id)

    def start(self):
        self.timer.init(
            period=self.interval_ms,
            mode=Timer.PERIODIC,
            callback=self._tick,
        )

    def stop(self, led_value=None):
        self.timer.deinit()

        if led_value is not None:
            self.led.value(led_value)

    def on(self):
        self.led.value(1)

    def off(self):
        self.led.value(0)

    def _tick(self, timer):
        if self.should_flash():
            self.led.value(not self.led.value())
        else:
            self.led.value(self.inactive_value)
