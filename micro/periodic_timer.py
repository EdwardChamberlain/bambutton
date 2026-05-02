from machine import Timer


class PeriodicTimer:
    _available_timer_ids = [0, 1, 2, 3]

    def __init__(self, period_ms, callback):
        self.period_ms = period_ms
        self.callback = callback
        self.timer_id = self._claim_timer_id()
        self.timer = Timer(self.timer_id)
        self.running = False

    def start(self):
        if self.running:
            return

        self.timer.init(
            period=self.period_ms,
            mode=Timer.PERIODIC,
            callback=self._tick,
        )
        self.running = True

    def stop(self):
        if not self.running:
            return

        self.timer.deinit()
        self.running = False

    def close(self):
        self.stop()
        self._release_timer_id(self.timer_id)

    def _tick(self, timer):
        self.callback()

    @classmethod
    def _claim_timer_id(cls):
        if not cls._available_timer_ids:
            raise RuntimeError("No available timer ids")

        return cls._available_timer_ids.pop(0)

    @classmethod
    def _release_timer_id(cls, timer_id):
        if timer_id in cls._available_timer_ids:
            return

        cls._available_timer_ids.append(timer_id)
        cls._available_timer_ids.sort()
