import time
import bambuddy_api
import config_loader
import gpio_button
import led_flasher
import wifi


config = config_loader.load_config()

# -- Runtime Flags ---
PRINTER_AWAITING = False
PENDING_BUTTON_PRESS = False

# -- Initialize LED flasher ---
flasher = led_flasher.LedFlasher(
    pin_number=config["led"]["pin"],
    should_flash=lambda: PRINTER_AWAITING,
    interval_ms=config["led"]["flash_interval_ms"],
    inactive_value=config["led"]["inactive_value"],
)
flasher.start()


# -- Button handler ---
def handle_button_press(pin):
    global PENDING_BUTTON_PRESS

    print("Button pressed on GPIO", config["button"]["pin"])
    PENDING_BUTTON_PRESS = True


button = gpio_button.GPIOButton(
    pin_number=config["button"]["pin"],
    on_press=handle_button_press,
    debounce_ms=config["button"]["debounce_ms"],
)
button.start()


# -- Connect to Wi-Fi --
try:
    network = wifi.WiFi(
        ssid=config["wifi"]["ssid"],
        password=config["wifi"]["password"],
        status_led=None,
        timeout_seconds=config["wifi"]["timeout_seconds"],
    )
    network.connect()

except Exception as exc:
    print("Wi-Fi connection failed:", exc)
    flasher.on()
    raise

# -- Initialize API client --
api = bambuddy_api.BambuddyAPI(
    config["api"]["key"],
    config["api"]["base_url"],
)


# -- Main loop --
while True:
    # Push button press to API if pending
    if PENDING_BUTTON_PRESS:
        if PRINTER_AWAITING:
            PRINTER_AWAITING = False
            api.clear_plate(config["printer"]["id"])
        else:
            print("Button press ignored - printer not awaiting plate clear")

        PENDING_BUTTON_PRESS = False

    # Check printer status
    PRINTER_AWAITING = api.printer_is_awaiting_plate_clear(config["printer"]["id"])
    print("Printer awaiting plate clear:", PRINTER_AWAITING)

    time.sleep(config["printer"]["poll_interval_seconds"])
