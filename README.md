# Bambuddy Plate Clear Button

A physical one-button plate-clear control for Bambuddy.

This project turns a small ESP32-C3 board into a wireless despatch button for your 3D printer setup. Press the button when a printer plate has been cleared, and the board sends the clear-plate request to Bambuddy via its API. A status LED provides simple visual feedback so the button can live near the printer as a dedicated shop-floor control.

## Setup Routes

There are two supported ways to configure a board.

### Recommended: Setup Assistant GUI

Most users should use the setup assistant GUI. Release builds will be published so users will not need to install Python, `mpremote`, or `esptool` themselves.

The GUI guides the user through:

- Selecting the MicroPython firmware `.bin`.
- Selecting a connected ESP32-C3 board.
- Entering Bambuddy API connection details.
- Fetching printers from Bambuddy and choosing by friendly name.
- Setting the LED pin, button pin, Wi-Fi SSID, and Wi-Fi password.
- Flashing firmware and required code.
- Pushing settings-only updates.

### Advanced: Manual Flashing

Advanced users can use the Python scripts and command-line tools directly. This is useful for development, debugging, or working outside the packaged release assistant.

Manual setup requires:

- Python installed locally.
- Dependencies from `requirements.txt`.
- A data-capable USB cable.
- Knowing the serial port if `mpremote` cannot auto-detect the board.

## Layout

```text
.
├── firmware/   MicroPython firmware binaries for the board
├── micro/      MicroPython source files copied to the ESP32-C3
├── scripts/    Local helper scripts
└── src/        PC-side setup GUI
```

Whilst this repo does carry a firmware binary for the ESP32-C3 Generic board I strongly recommend using the latest version from the [micropython website](https://micropython.org/download/ESP32_GENERIC_C3/?utm_source=chatgpt.com)

Key files:

- `micro/main.py` - board entry point and application loop.
- `micro/config.json` - runtime configuration loaded by the board at boot.
- `micro/config_loader.py` - config loader with defaults.
- `micro/api.py` - low-level API-key HTTP client.
- `micro/bambuddy_api.py` - route-level Bambuddy API wrapper.
- `micro/wifi.py` - Wi-Fi connection helper.
- `micro/gpio_button.py` - debounced GPIO interrupt button helper.
- `micro/led_flasher.py` - timer-driven LED flasher.
- `firmware/ESP32_GENERIC_C3-20260406-v1.28.0.bin` - bundled ESP32-C3 MicroPython firmware image.
- `scripts/push_micro.py` - copies required MicroPython files to the board with `mpremote`.
- `scripts/run_main.py` - runs `micro/main.py` on the board without copying it as an auto-start file.
- `src/bambuddy_config_gui.py` - GUI for selecting firmware, board, pins, Wi-Fi, API key, and printer.

## Setup Assistant GUI

For end users, use the built installer when available.

For development, run the GUI from source:

```bash
python -m pip install -r requirements.txt
python src/bambuddy_config_gui.py
```

## Manual Configuration

Manual users can edit `micro/config.json` before copying the files to the board:

```json
{
  "wifi": {
    "ssid": "your-wifi-ssid",
    "password": "your-wifi-password",
    "timeout_seconds": 10
  },
  "api": {
    "base_url": "http://your-server-ip:8000/api/v1",
    "key": "your-api-key"
  },
  "printer": {
    "id": 3,
    "poll_interval_seconds": 5
  },
  "led": {
    "pin": 8,
    "flash_interval_ms": 250,
    "inactive_value": 0
  },
  "button": {
    "pin": 3,
    "debounce_ms": 150
  }
}
```

## Manual Copying

With `mpremote` installed and the ESP32-C3 connected:

```bash
scripts/push_micro.py
```

To push only configuration changes:

```bash
mpremote cp micro/config.json :
mpremote reset
```

To wipe the board filesystem before copying the project files:

```bash
scripts/push_micro.py --clean
```

To copy support files without `main.py`, preventing the app from auto-starting:

```bash
scripts/push_micro.py --no-main
```

To wipe the board and leave it without an auto-starting `main.py`:

```bash
scripts/push_micro.py --clean --no-main
```

If `mpremote` needs an explicit serial port:

```bash
scripts/push_micro.py --device /dev/tty.usbmodemXXXX
```

## Manual Run Without Auto-Start

To launch `micro/main.py` manually from your computer:

```bash
scripts/run_main.py
```

This relies on `mpremote` auto-detecting the connected board. If needed, pass the device explicitly:

```bash
scripts/run_main.py --device /dev/tty.usbmodemXXXX
```

The support modules and `config.json` still need to exist on the board. A typical development flow is:

```bash
scripts/push_micro.py --clean --nomain
scripts/run_main.py
```

## Manual Firmware Flashing

The GUI performs these steps for normal users. Advanced users can run them manually with `esptool.py`, replacing the serial port with the board's port:

```bash
esptool.py --chip esp32c3 --port /dev/tty.usbmodemXXXX erase_flash
esptool.py --chip esp32c3 --port /dev/tty.usbmodemXXXX write_flash -z 0x0 firmware/ESP32_GENERIC_C3-20260406-v1.28.0.bin
```

After flashing firmware, copy the MicroPython files:

```bash
scripts/push_micro.py --clean
```

## Hardware

### Purchased Parts

- [ESP32-C3 Super Mini](https://www.aliexpress.com/item/1005008805263277.html?spm=a2g0o.order_list.order_list_main.5.61041802T9J6qU)
- [LED Button](https://www.aliexpress.com/item/1005004920346156.html?) - select the **3-6V momentary** option.

### Wiring Notes

The current default configuration uses the onboard LED (although I would recommend using a switch like above that has a built in LED so it is visible):

Use GPIO numbers, not physical pin positions printed by a seller diagram.

#### Button wiring:
- Connect one side of the momentary switch to GPIO 3 or your configured pin.
- Connect the other side of the switch to GND.
- The firmware enables the ESP32-C3 internal pull-up, so the button reads high when idle and low when pressed.
- The interrupt is configured for the falling edge, so it triggers on button press.

#### LED wiring:
- The LED output defaults to GPIO 8.
- If using the ESP32-C3 board's built-in LED, confirm your board uses GPIO 8. Some boards use a different LED GPIO.
- If wiring the LED inside the external button, connect it only according to the button's voltage/current requirements.
- Do not feed 5V into an ESP32-C3 GPIO. ESP32-C3 GPIO is 3.3V logic.
- If the button LED needs more current than a GPIO can safely provide, drive it through a transistor/MOSFET instead of directly from the GPIO.

#### Power and USB:

- Use a data-capable USB cable. Charge-only USB cables will power the board but will not appear to `mpremote`.
- Power the ESP32-C3 from USB during setup and flashing.
- Disconnect power before changing wiring.
