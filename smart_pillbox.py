"""
Smart Medicine Pill Box
=======================
Hardware : Raspberry Pi Zero W
Sensors  : DS3231 RTC, IR sensors (x3), Buzzer, LED (x3),
           16x4 LCD (I2C), SIM800L GSM module
Language : Python 3

Dose schedule (edit below):
  - Pill 1 : 09:00 AM
  - Pill 2 : 12:00 PM
  - Pill 3 : 09:00 PM

Team: Kesini E, Sri Priya E, Akanksha M, Ahmed Pasha A
Guide: V. Arun, Associate Professor, ECE

Install dependencies:
  sudo pip3 install RPi.GPIO smbus2 RPLCD pyserial

Wiring summary:
  LCD SDA         -> GPIO 2  (I2C SDA)
  LCD SCL         -> GPIO 3  (I2C SCL)
  RTC SDA         -> GPIO 2  (shared I2C bus)
  RTC SCL         -> GPIO 3  (shared I2C bus)
  Buzzer          -> GPIO 17
  LED Box 1       -> GPIO 27
  LED Box 2       -> GPIO 22
  LED Box 3       -> GPIO 23
  IR Sensor Box 1 -> GPIO 5  (LOW when box opened)
  IR Sensor Box 2 -> GPIO 6
  IR Sensor Box 3 -> GPIO 13
  GSM TX          -> GPIO 14 (UART TX)
  GSM RX          -> GPIO 15 (UART RX)
"""

import RPi.GPIO as GPIO
import smbus2
import serial
import time
import datetime
import threading

# ─── GPIO Pin definitions ──────────────────────────────────────────────────
BUZZER_PIN   = 17
LED_PINS     = [27, 22, 23]        # LEDs for box 1, 2, 3
IR_PINS      = [5,  6,  13]        # IR sensors for box 1, 2, 3

# ─── Dose schedule ─────────────────────────────────────────────────────────
# Each tuple: (hour, minute) in 24-hour format
DOSE_TIMES = [
    (9,  0),   # Pill 1 — Morning  09:00
    (12, 0),   # Pill 2 — Noon     12:00
    (21, 0),   # Pill 3 — Night    21:00
]

REMINDER_WAIT_SECONDS = 120        # Wait 2 min before sending SMS if no action

# ─── Caregiver phone number ────────────────────────────────────────────────
CAREGIVER_NUMBER = "+91 7036281027"  # Replace with actual number

# ─── LCD I2C address ───────────────────────────────────────────────────────
LCD_I2C_ADDRESS = 0x27             # Try 0x3F if 0x27 doesn't work
LCD_I2C_BUS     = 1

# ─── RTC DS3231 I2C address ────────────────────────────────────────────────
RTC_ADDRESS = 0x68

# ─── GSM serial port ───────────────────────────────────────────────────────
GSM_PORT     = "/dev/ttyS0"        # Use /dev/ttyAMA0 on older Pi models
GSM_BAUDRATE = 9600


# ══════════════════════════════════════════════════════════════════════════════
# LCD DRIVER  (16x4, I2C backpack, PCF8574)
# ══════════════════════════════════════════════════════════════════════════════
class LCD:
    # PCF8574 bit positions
    RS = 0; RW = 1; EN = 2; BL = 3
    D4 = 4; D5 = 5; D6 = 6; D7 = 7

    ROW_OFFSETS = [0x00, 0x40, 0x14, 0x54]   # 16x4 row offsets

    def __init__(self, address=LCD_I2C_ADDRESS, bus=LCD_I2C_BUS):
        self.bus     = smbus2.SMBus(bus)
        self.address = address
        self._bl     = 1 << self.BL
        self._init_display()

    def _write_i2c(self, data):
        self.bus.write_byte(self.address, data | self._bl)

    def _pulse_enable(self, data):
        self._write_i2c(data | (1 << self.EN))
        time.sleep(0.0005)
        self._write_i2c(data & ~(1 << self.EN))
        time.sleep(0.0001)

    def _write4(self, data, mode=0):
        high = (data & 0xF0) | (mode << self.RS)
        low  = ((data << 4) & 0xF0) | (mode << self.RS)
        self._pulse_enable(high)
        self._pulse_enable(low)

    def _init_display(self):
        time.sleep(0.05)
        for _ in range(3):
            self._pulse_enable(0x30)
            time.sleep(0.005)
        self._pulse_enable(0x20)          # 4-bit mode
        self._write4(0x28)                # 2-line, 5x8 font
        self._write4(0x0C)                # Display ON, cursor OFF
        self._write4(0x06)                # Entry mode
        self.clear()

    def clear(self):
        self._write4(0x01)
        time.sleep(0.002)

    def set_cursor(self, col, row):
        addr = self.ROW_OFFSETS[row] + col
        self._write4(0x80 | addr)

    def write(self, text):
        for ch in str(text):
            self._write4(ord(ch), mode=1)

    def print_line(self, row, text):
        self.set_cursor(0, row)
        self.write(text.ljust(16))


# ══════════════════════════════════════════════════════════════════════════════
# RTC DS3231
# ══════════════════════════════════════════════════════════════════════════════
class RTC:
    def __init__(self, bus=LCD_I2C_BUS):
        self.bus = smbus2.SMBus(bus)

    def _bcd_to_dec(self, val):
        return (val // 16 * 10) + (val % 16)

    def get_time(self):
        """Returns (hour, minute, second, day, month, year)"""
        data = self.bus.read_i2c_block_data(RTC_ADDRESS, 0x00, 7)
        second = self._bcd_to_dec(data[0] & 0x7F)
        minute = self._bcd_to_dec(data[1])
        hour   = self._bcd_to_dec(data[2] & 0x3F)
        day    = self._bcd_to_dec(data[4])
        month  = self._bcd_to_dec(data[5] & 0x1F)
        year   = self._bcd_to_dec(data[6]) + 2000
        return hour, minute, second, day, month, year

    def get_datetime_str(self):
        h, m, s, d, mo, y = self.get_time()
        return f"{d:02d}/{mo:02d}/{y}  {h:02d}:{m:02d}:{s:02d}"


# ══════════════════════════════════════════════════════════════════════════════
# GSM MODULE
# ══════════════════════════════════════════════════════════════════════════════
class GSM:
    def __init__(self):
        self.ser = serial.Serial(GSM_PORT, GSM_BAUDRATE, timeout=2)
        time.sleep(3)
        self._init()

    def _send_at(self, cmd, wait=1):
        self.ser.write((cmd + "\r\n").encode())
        time.sleep(wait)
        resp = self.ser.read(self.ser.in_waiting).decode(errors="ignore")
        print(f"GSM << {cmd}  >> {resp.strip()}")
        return resp

    def _init(self):
        self._send_at("AT")
        self._send_at("ATE0")
        self._send_at("AT+CMGF=1")     # Text mode SMS

    def send_sms(self, number, message):
        print(f"Sending SMS to {number}: {message}")
        self._send_at(f'AT+CMGS="{number}"', wait=1)
        self.ser.write((message + chr(26)).encode())   # Ctrl+Z
        time.sleep(4)
        resp = self.ser.read(self.ser.in_waiting).decode(errors="ignore")
        print(f"SMS response: {resp.strip()}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PILL BOX CONTROLLER
# ══════════════════════════════════════════════════════════════════════════════
class PillBox:
    def __init__(self):
        self._setup_gpio()
        self.lcd = LCD()
        self.rtc = RTC()
        self.gsm = GSM()

        # Track which doses have been handled today
        self.dose_handled = [False, False, False]
        self.last_check_date = None

        self.lcd.clear()
        self.lcd.print_line(0, "Smart Pill Box")
        self.lcd.print_line(1, "Initialising...")
        time.sleep(2)
        print("Smart Pill Box ready.")

    def _setup_gpio(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        GPIO.setup(BUZZER_PIN, GPIO.OUT)
        GPIO.output(BUZZER_PIN, GPIO.LOW)

        for pin in LED_PINS:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)

        for pin in IR_PINS:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    # ── Buzzer helpers ────────────────────────────────────────────────────
    def buzzer_on(self):
        GPIO.output(BUZZER_PIN, GPIO.HIGH)

    def buzzer_off(self):
        GPIO.output(BUZZER_PIN, GPIO.LOW)

    def buzzer_beep(self, times=3, duration=0.3):
        for _ in range(times):
            self.buzzer_on()
            time.sleep(duration)
            self.buzzer_off()
            time.sleep(0.2)

    # ── LED helpers ───────────────────────────────────────────────────────
    def led_on(self, box_index):
        GPIO.output(LED_PINS[box_index], GPIO.HIGH)

    def led_off(self, box_index):
        GPIO.output(LED_PINS[box_index], GPIO.LOW)

    def led_blink(self, box_index, stop_event, interval=0.5):
        """Blink LED in a background thread until stop_event is set."""
        def _blink():
            while not stop_event.is_set():
                GPIO.output(LED_PINS[box_index], GPIO.HIGH)
                time.sleep(interval)
                GPIO.output(LED_PINS[box_index], GPIO.LOW)
                time.sleep(interval)
            GPIO.output(LED_PINS[box_index], GPIO.LOW)
        t = threading.Thread(target=_blink, daemon=True)
        t.start()
        return t

    # ── IR sensor ─────────────────────────────────────────────────────────
    def is_box_open(self, box_index):
        """Returns True if IR sensor detects box is opened (LOW signal)."""
        return GPIO.input(IR_PINS[box_index]) == GPIO.LOW

    def wait_for_box_open(self, box_index, timeout=REMINDER_WAIT_SECONDS):
        """Wait up to timeout seconds for the box to be opened."""
        start = time.time()
        while time.time() - start < timeout:
            if self.is_box_open(box_index):
                return True
            time.sleep(0.5)
        return False

    # ── Dose handling ─────────────────────────────────────────────────────
    def handle_dose(self, dose_index):
        pill_num = dose_index + 1
        print(f"\n--- Dose reminder: Pill {pill_num} ---")

        # Update LCD
        self.lcd.clear()
        self.lcd.print_line(0, f"Time for Pill {pill_num}!")
        self.lcd.print_line(1, "Open box to confirm")

        # Start blinking LED and buzzer
        stop_blink = threading.Event()
        self.led_blink(dose_index, stop_blink)
        self.buzzer_beep(times=5)

        # Wait for box to open
        taken = self.wait_for_box_open(dose_index, timeout=REMINDER_WAIT_SECONDS)

        # Stop LED blink and buzzer
        stop_blink.set()
        self.buzzer_off()

        if taken:
            # Verify box wasn't just opened and closed immediately
            time.sleep(1)
            if not self.is_box_open(dose_index):
                # Box was closed too fast — remind again once
                self.lcd.print_line(0, "Pill taken?     ")
                self.lcd.print_line(1, "Confirm again...")
                self.buzzer_beep(times=3)
                time.sleep(5)

            msg = f"Pill-{pill_num} Taken"
            self.lcd.clear()
            self.lcd.print_line(0, f"Pill {pill_num}: TAKEN")
            self.lcd.print_line(1, "SMS sent to carer")
            print(f"Pill {pill_num} TAKEN")
        else:
            msg = f"Pill-{pill_num} Not Taken"
            self.lcd.clear()
            self.lcd.print_line(0, f"Pill {pill_num}: NOT TAKEN")
            self.lcd.print_line(1, "SMS sent to carer")
            print(f"Pill {pill_num} NOT TAKEN — sending alert")

        self.gsm.send_sms(CAREGIVER_NUMBER, f"Smart Pill Box Alert: {msg}")
        self.dose_handled[dose_index] = True
        time.sleep(3)

    # ── Idle display ──────────────────────────────────────────────────────
    def update_idle_display(self):
        h, m, s, d, mo, y = self.rtc.get_time()
        self.lcd.print_line(0, f"Date: {d:02d}/{mo:02d}/{y}")
        self.lcd.print_line(1, f"Time: {h:02d}:{m:02d}:{s:02d}")

        # Show next dose on row 2/3
        next_dose = self._next_dose_str(h, m)
        self.lcd.print_line(2, f"Next dose: {next_dose}")
        self.lcd.print_line(3, "Smart Pill Box  ")

    def _next_dose_str(self, cur_h, cur_m):
        for i, (dh, dm) in enumerate(DOSE_TIMES):
            if not self.dose_handled[i] and (dh > cur_h or (dh == cur_h and dm > cur_m)):
                suffix = "AM" if dh < 12 else "PM"
                display_h = dh if dh <= 12 else dh - 12
                return f"{display_h:02d}:{dm:02d} {suffix}"
        return "All done today!"

    # ── Daily reset ───────────────────────────────────────────────────────
    def check_daily_reset(self, today_date):
        if self.last_check_date != today_date:
            self.dose_handled = [False, False, False]
            self.last_check_date = today_date
            print(f"New day {today_date} — dose flags reset.")

    # ── Main loop ─────────────────────────────────────────────────────────
    def run(self):
        print("Running main loop. Press Ctrl+C to stop.")
        try:
            while True:
                h, m, s, d, mo, y = self.rtc.get_time()
                today = (y, mo, d)
                self.check_daily_reset(today)

                # Check each dose time
                for i, (dh, dm) in enumerate(DOSE_TIMES):
                    if not self.dose_handled[i] and h == dh and m == dm:
                        self.handle_dose(i)
                        break
                else:
                    # No dose due — show idle screen
                    self.update_idle_display()

                time.sleep(30)    # Check every 30 seconds

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.lcd.clear()
            self.lcd.print_line(0, "System stopped.")
            self.buzzer_off()
            GPIO.cleanup()


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    box = PillBox()
    box.run()
