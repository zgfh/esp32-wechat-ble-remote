"""BLE remote-key bridge for ESP32 MicroPython.

GPIO 26/27 drive optocoupler inputs. The remote's original RF transmitter and
rolling-code logic remain untouched: this program only emulates short presses.
"""
import bluetooth
import os
import ubinascii
import uhashlib
from machine import Pin
from micropython import const
from time import ticks_add, ticks_diff, ticks_ms, sleep_ms

LOCK_PIN, UNLOCK_PIN, PRESS_MS = 26, 27, 180
BLE_DEVICE_NAME = "ESP32-Car-Remote"
# Set a unique long random value here and in miniprogram/app.js. Never commit it.
BLE_PAIRING_SECRET = "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET"

SERVICE_UUID = bluetooth.UUID("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
COMMAND_UUID = bluetooth.UUID("6e400002-b5a3-f393-e0a9-e50e24dcca9e")
STATUS_UUID = bluetooth.UUID("6e400003-b5a3-f393-e0a9-e50e24dcca9e")
CONNECT, DISCONNECT, WRITE = const(1), const(2), const(3)
READ, WRITE_FLAG, NOTIFY = const(0x0002), const(0x0008), const(0x0010)

buttons = {"lock": Pin(LOCK_PIN, Pin.OUT, value=0), "unlock": Pin(UNLOCK_PIN, Pin.OUT, value=0)}
release_at, connections, authenticated, nonce = {"lock": None, "unlock": None}, set(), set(), ""

def digest(text):
    return ubinascii.hexlify(uhashlib.sha256(text.encode()).digest()).decode()

def advertise():
    name = BLE_DEVICE_NAME.encode()
    ble.gap_advertise(500000, adv_data=b"\x02\x01\x06" + bytes((len(name) + 1, 9)) + name)

def publish(text):
    value = text.encode()
    ble.gatts_write(status_handle, value)
    for conn in connections:
        try: ble.gatts_notify(conn, status_handle, value)
        except OSError: pass

def press(name):
    if release_at[name] is None:
        buttons[name].on()
        release_at[name] = ticks_add(ticks_ms(), PRESS_MS)

def release_expired():
    now = ticks_ms()
    for name, deadline in release_at.items():
        if deadline is not None and ticks_diff(now, deadline) >= 0:
            buttons[name].off()
            release_at[name] = None

def on_ble(event, data):
    global nonce
    if event == CONNECT:
        conn, _, _ = data
        connections.add(conn); authenticated.discard(conn)
        nonce = ubinascii.hexlify(os.urandom(12)).decode()
        publish("CHALLENGE:" + nonce)
    elif event == DISCONNECT:
        conn, _, _ = data
        connections.discard(conn); authenticated.discard(conn); advertise()
    elif event == WRITE:
        conn, handle = data
        if handle != command_handle: return
        try: message = ble.gatts_read(command_handle).decode().strip()
        except UnicodeError: publish("ERROR:BAD_ENCODING"); return
        if message == "AUTH:" + digest(BLE_PAIRING_SECRET + ":" + nonce):
            authenticated.add(conn); publish("AUTH_OK")
        elif conn not in authenticated: publish("ERROR:AUTH_REQUIRED")
        elif message == "CMD:LOCK": press("lock"); publish("OK:LOCK")
        elif message == "CMD:UNLOCK": press("unlock"); publish("OK:UNLOCK")
        else: publish("ERROR:UNKNOWN_COMMAND")

ble = bluetooth.BLE(); ble.active(True)
((command_handle, status_handle),) = ble.gatts_register_services(((SERVICE_UUID, ((COMMAND_UUID, WRITE_FLAG), (STATUS_UUID, READ | NOTIFY))),))
ble.irq(on_ble); publish("READY"); advertise()
print("BLE ready as", BLE_DEVICE_NAME)
while True:
    release_expired()
    sleep_ms(20)
