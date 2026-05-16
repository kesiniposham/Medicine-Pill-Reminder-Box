# 💊 Smart Medicine Pill Box - Raspberry Pi

An IoT-based smart pill reminder system that alerts patients to take medication on time, blinks LEDs on the correct pill box, sounds a buzzer, and notifies the caregiver via SMS if medication is not taken.

---

## 📌 About

Senior citizens and patients with chronic conditions often miss doses or take wrong medications. This system automates reminders with three daily dose alarms, detects whether the pill box was opened (via IR sensor), and sends "PILL TAKEN" or "PILL NOT TAKEN" alerts to the caregiver via GSM.

---

## ✨ Features

- ⏰ Three daily dose alarms (9 AM, 12 PM, 9 PM — configurable)
- 💡 LED blinks on the correct pill box compartment
- 🔔 Buzzer alarm at dose time
- 📦 IR sensor detects whether the box was opened
- 📱 SMS to caregiver: "Pill-N Taken" or "Pill-N Not Taken"
- 🖥️ 16×4 LCD shows date, time, and next dose
- 🔁 Daily auto-reset of dose tracking

---

## 🛠️ Hardware Required

| Component | Quantity |
|---|---|
| Raspberry Pi Zero W | 1 |
| DS3231 RTC module (I2C) | 1 |
| 16×4 LCD with I2C backpack | 1 |
| SIM800L GSM module | 1 |
| IR sensor module | 3 |
| 5mm LED | 3 |
| Buzzer (5V) | 1 |
| 220Ω resistors (for LEDs) | 3 |
| 5V 2.4A power supply | 1 |
| MicroSD card (8GB+, Raspbian) | 1 |

---

## 🔌 Wiring

| Component | Raspberry Pi GPIO |
|---|---|
| LCD SDA | GPIO 2 (SDA) |
| LCD SCL | GPIO 3 (SCL) |
| RTC SDA | GPIO 2 (shared I2C) |
| RTC SCL | GPIO 3 (shared I2C) |
| Buzzer | GPIO 17 |
| LED Box 1 | GPIO 27 |
| LED Box 2 | GPIO 22 |
| LED Box 3 | GPIO 23 |
| IR Sensor Box 1 | GPIO 5 |
| IR Sensor Box 2 | GPIO 6 |
| IR Sensor Box 3 | GPIO 13 |
| GSM TX → Pi RX | GPIO 15 (UART RX) |
| GSM RX ← Pi TX | GPIO 14 (UART TX) |

---

## ⚙️ How It Works

1. RTC continuously tracks real time.
2. At each dose time, the buzzer sounds and the correct box's LED blinks.
3. The IR sensor waits up to **2 minutes** for the patient to open the box.
4. If box is opened → **"Pill-N Taken"** SMS sent to caregiver.
5. If box is not opened in time → **"Pill-N Not Taken"** SMS sent to caregiver.
6. LCD always shows current date, time, and next upcoming dose.
7. Dose tracking resets automatically at midnight each day.

---

## 🚀 Setup on Raspberry Pi

### 1. Enable I2C and UART
```bash
sudo raspi-config
```
- Interface Options → I2C → Enable
- Interface Options → Serial Port → Disable login shell → Enable serial hardware

### 2. Install dependencies
```bash
sudo pip3 install RPi.GPIO smbus2 pyserial
```

### 3. Clone or copy files
```bash
git clone https://github.com/kesiniposham/Smart-Medicine-Pill-Box.git
cd Smart-Medicine-Pill-Box
```

### 4. Configure
Edit `smart_pillbox.py`:
```python
CAREGIVER_NUMBER = "+91XXXXXXXXXX"   # caregiver's phone number

DOSE_TIMES = [
    (9,  0),   # Morning
    (12, 0),   # Noon
    (21, 0),   # Night
]
```

### 5. Test hardware first
```bash
python3 hardware_test.py
```
This verifies each component (LEDs, buzzer, IR sensors, RTC, LCD, GSM) before running the main script.

### 6. Run the main script
```bash
python3 smart_pillbox.py
```

### 7. Auto-start on boot (optional)
```bash
crontab -e
```
Add this line:
```
@reboot python3 /home/pi/Smart-Medicine-Pill-Box/smart_pillbox.py &
```

---

## 🔍 Expected Output (terminal)

```
Smart Pill Box ready.
Running main loop. Press Ctrl+C to stop.

--- Dose reminder: Pill 1 ---
Pill 1 TAKEN
Sending SMS to +91XXXXXXXXXX: Smart Pill Box Alert: Pill-1 Taken

--- Dose reminder: Pill 2 ---
Pill 2 NOT TAKEN — sending alert
Sending SMS to +91XXXXXXXXXX: Smart Pill Box Alert: Pill-2 Not Taken
```

---

## 🔮 Future Enhancements

- [ ] Mobile app control via Bluetooth/Wi-Fi
- [ ] Store dose history to CSV / cloud
- [ ] Voice reminder using text-to-speech
- [ ] RFID to identify which patient is taking pills
- [ ] Camera to visually confirm pill taken

---


## 📄 License

This project is open source and available under the [MIT License](LICENSE).
