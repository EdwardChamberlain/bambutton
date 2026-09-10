import network
import time


DEFAULT_HOSTNAME = "bambutton"
RETRY_DELAY_SECONDS = 10


class ConnectionTimeout(RuntimeError):
    pass


class WiFi:
    def __init__(
        self,
        ssid,
        password,
        status_led=None,
        timeout_seconds=10,
        connected_led_value=0,
        failed_led_value=1,
        hostname=DEFAULT_HOSTNAME,
    ):
        self.ssid = ssid
        self.password = password
        self.status_led = status_led
        self.timeout_seconds = timeout_seconds
        self.connected_led_value = connected_led_value
        self.failed_led_value = failed_led_value
        self.hostname = hostname or DEFAULT_HOSTNAME
        self.wlan = network.WLAN(network.STA_IF)

    def connect(self, watchdog_feed=None):
        # Set this before activating the interface so DHCP and mDNS can use it.
        network.hostname(self.hostname)
        self.wlan.active(True)
        # self.wlan.config(txpower=8.5)
        self.wlan.config(pm=network.WLAN.PM_NONE)

        if not self.wlan.isconnected():
            print("Connecting to Wi-Fi:", self.ssid)
            self.wlan.connect(self.ssid, self.password)
            self._wait_for_connection(watchdog_feed)

        self._set_led(self.connected_led_value)
        print("Connected to Wi-Fi")
        print("Network config:", self.wlan.ifconfig())
        return self.wlan

    def connect_forever(self, watchdog_feed=None):
        while True:
            try:
                return self.connect(watchdog_feed=watchdog_feed)
            except (ConnectionTimeout, OSError) as exc:
                print("Wi-Fi connection failed:", exc)
                self.disconnect()
                self._sleep_before_retry(watchdog_feed)

    def ensure_connected(self, watchdog_feed=None):
        if self.is_connected():
            return self.wlan

        print("Wi-Fi connection lost; reconnecting")
        return self.connect_forever(watchdog_feed=watchdog_feed)

    def disconnect(self):
        self.wlan.disconnect()

    def is_connected(self):
        return self.wlan.isconnected()

    def ifconfig(self):
        return self.wlan.ifconfig()

    def _wait_for_connection(self, watchdog_feed=None):
        started_at = time.ticks_ms()

        while not self.wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), started_at) > self.timeout_seconds * 1000:
                self._set_led(self.failed_led_value)
                raise ConnectionTimeout("Wi-Fi connection timed out")

            if watchdog_feed is not None:
                watchdog_feed()
            self._toggle_led()
            time.sleep(0.25)

    def _sleep_before_retry(self, watchdog_feed=None):
        remaining_seconds = RETRY_DELAY_SECONDS

        while remaining_seconds > 0:
            if watchdog_feed is not None:
                watchdog_feed()

            sleep_seconds = min(1, remaining_seconds)
            time.sleep(sleep_seconds)
            remaining_seconds -= sleep_seconds

    def _toggle_led(self):
        if self.status_led:
            self.status_led.value(not self.status_led.value())

    def _set_led(self, value):
        if self.status_led:
            self.status_led.value(value)
