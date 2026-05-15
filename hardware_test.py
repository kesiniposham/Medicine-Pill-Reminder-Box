"""
hardware_test.py — Run this FIRST to verify each component works
before running the main smart_pillbox.py script.

Usage:
  python3 hardware_test.py
"""

import RPi.GPIO as GPIO
import smbus2
import serial
import time

BUZZER_PIN = 17
LED_PINS   = [27, 22, 23]
IR_PINS    = [5,  6,  13]

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# ─── Test 1: LEDs ──────────────────────────────────────────────────────────
print("\n[TEST 1] LEDs — each should blink once")
for i, pin in enumerate(LED_PINS):
    GPIO.setup(pin, GPIO.OUT)
    print(f"  LED {i+1} (GPIO {pin}) ON")
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(0.5)
    GPIO.output(pin, GPIO.LOW)
    print(f"  LED {i+1} OFF")
    time.sleep(0.3)

# ─── Test 2: Buzzer ────────────────────────────────────────────────────────
print("\n[TEST 2] Buzzer — should beep 3 times")
GPIO.setup(BUZZER_PIN, GPIO.OUT)
for _ in range(3):
    GPIO.output(BUZZER_PIN, GPIO.HIGH)
    time.sleep(0.2)
    GPIO.output(BUZZER_PIN, GPIO.LOW)
    time.sleep(0.2)

# ─── Test 3: IR sensors ────────────────────────────────────────────────────
print("\n[TEST 3] IR sensors — wave hand over each sensor when prompted")
for i, pin in enumerate(IR_PINS):
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    input(f"  Press Enter then wave hand over Box {i+1} sensor (GPIO {pin})...")
    detected = False
    for _ in range(20):
        if GPIO.input(pin) == GPIO.LOW:
            detected = True
            break
        time.sleep(0.1)
    print(f"  Box {i+1}: {'DETECTED ✓' if detected else 'NOT detected ✗'}")

# ─── Test 4: RTC ───────────────────────────────────────────────────────────
print("\n[TEST 4] RTC DS3231 — reading current time")
try:
    bus = smbus2.SMBus(1)
    data = bus.read_i2c_block_data(0x68, 0x00, 7)
    def bcd(v): return (v // 16 * 10) + (v % 16)
    h, m, s = bcd(data[2] & 0x3F), bcd(data[1]), bcd(data[0] & 0x7F)
    d, mo, y = bcd(data[4]), bcd(data[5] & 0x1F), bcd(data[6]) + 2000
    print(f"  RTC time: {d:02d}/{mo:02d}/{y}  {h:02d}:{m:02d}:{s:02d}  ✓")
except Exception as e:
    print(f"  RTC ERROR: {e}  — check I2C wiring")

# ─── Test 5: LCD ───────────────────────────────────────────────────────────
print("\n[TEST 5] LCD — should display test message")
try:
    from smart_pillbox import LCD
    lcd = LCD()
    lcd.print_line(0, "LCD Test OK!    ")
    lcd.print_line(1, "Smart Pill Box  ")
    print("  LCD: message written — check display  ✓")
except Exception as e:
    print(f"  LCD ERROR: {e}")

# ─── Test 6: GSM ───────────────────────────────────────────────────────────
print("\n[TEST 6] GSM — sending AT command")
try:
    ser = serial.Serial("/dev/ttyS0", 9600, timeout=2)
    ser.write(b"AT\r\n")
    time.sleep(1)
    resp = ser.read(ser.in_waiting).decode(errors="ignore").strip()
    print(f"  GSM response: '{resp}'  {'✓' if 'OK' in resp else '✗ — check wiring/power'}")
    ser.close()
except Exception as e:
    print(f"  GSM ERROR: {e}")

GPIO.cleanup()
print("\n─── Hardware test complete ───")
