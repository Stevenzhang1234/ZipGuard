# ZipGuard

ZipGuard is a smart lock project built for our Intro to Engineering course. It combines an ESP32 microcontroller with a handful of sensors and actuators to create a lock that can be controlled remotely and monitors itself for tampering.

## Features

- **Bluetooth unlock** — open the lock from a web interface over Bluetooth.
- **Tamper detection** — a force sensor watches for anyone trying to physically tamper with the lock.
- **Status indication** — an RGB LED shows the current state of the lock (locked, unlocked, alert).
- **Audible alerts** — a buzzer sounds when tampering is detected.

## Components

- ESP32
- Servo motor
- Force sensor
- Buzzer
- RGB LED
- Resistors
- Button

## Repository layout

- [sldp/](sldp/) — main project code for ZipGuard.
  - [main_code.ino](sldp/main_code.ino) — the primary firmware that ties everything together.
  - [bluetooth_module.ino](sldp/bluetooth_module.ino), [bluetooth_on_off.ino](sldp/bluetooth_on_off.ino) — Bluetooth control of the lock.
  - [force_sensor_with_button.ino](sldp/force_sensor_with_button.ino) — tamper detection logic.
  - [ESP32_sender_code.ino](sldp/ESP32_sender_code.ino), [ESP32_receiver_code.ino](sldp/ESP32_receiver_code.ino) — ESP32-to-ESP32 communication.
  - [tests/](sldp/tests/) — standalone sketches used to validate each component individually (servo, force sensor, buzzer, GPS, camera, etc.).
- [workshop-3/](workshop-3/), [workshop-4/](workshop-4/), [workshop-6/](workshop-6/), [workshop-10/](workshop-10/) — supporting code from course workshops.

## Getting started

1. Open the `.ino` sketches in the Arduino IDE with the ESP32 board package installed.
2. Wire up the components as described in the project documentation (ESP32, servo, force sensor, buzzer, RGB LED, button, and resistors).
3. Flash [sldp/main_code.ino](sldp/main_code.ino) to the ESP32.
4. Connect to the lock from the web interface over Bluetooth to lock/unlock.
