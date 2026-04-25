from machine import Pin
import micropython
import time


micropython.alloc_emergency_exception_buf(100)


class GPIOButton:
    def __init__(
        self,
        pin_number,
        on_press,
        debounce_ms=100,
        pull=Pin.PULL_UP,
        trigger=Pin.IRQ_FALLING,
    ):
        self.pin_number = pin_number
        self.on_press = on_press
        self.debounce_ms = debounce_ms
        self.pin = Pin(pin_number, Pin.IN, pull)
        self.trigger = trigger
        self.last_press_ms = 0
        self._scheduled_press = self._handle_scheduled_press

    def start(self):
        self.pin.irq(trigger=self.trigger, handler=self._irq)

    def stop(self):
        self.pin.irq(handler=None)

    def _irq(self, pin):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_press_ms) < self.debounce_ms:
            return

        self.last_press_ms = now

        try:
            micropython.schedule(self._scheduled_press, pin)
        except RuntimeError:
            pass

    def _handle_scheduled_press(self, pin):
        self.on_press(pin)
