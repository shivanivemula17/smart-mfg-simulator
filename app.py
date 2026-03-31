import paho.mqtt.client as mqtt
import json
import time
import random
import threading
from datetime import datetime, timezone
import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Industrial Physics Engine is LIVE and Streaming!"

# --- PHYSICS CONSTANTS ---
ROOM_TEMP = 25.0
MAX_HEALTHY_TEMP = 85.0
CRITICAL_TEMP = 115.0
NORMAL_RPM = 1500
NORMAL_PRESSURE = 120.0

def run_simulator():
    BROKER = "mqtt-dashboard.com"
    TOPIC = "manufacturing/sensor/all_machines"
    MACHINES = [f"M-{i:03}" for i in range(101, 111)]
    
    # Track the life-cycle of each machine
    # States: 'STABLE', 'DECAYING', 'STOPPED'
    m_state = {}
    for m in MACHINES:
        m_state[m] = {
            "status": "RUNNING",
            "internal_mode": "STABLE",
            "temp": ROOM_TEMP,
            "vib": 0.1,
            "pres": NORMAL_PRESSURE,
            "rpm": 0,
            "state_start": time.time(),
            "min_run_time": 1800, # 30 minutes in seconds
            "stop_duration": random.randint(180, 300) # 3-5 mins
        }

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(BROKER, 1883)

    while True:
        current_time = time.time()
        
        for m_id in MACHINES:
            s = m_state[m_id]
            elapsed = current_time - s["state_start"]

            # --- 1. STATE TRANSITION LOGIC (The Rhythm) ---
            
            # If machine is RUNNING and STABLE
            if s["status"] == "RUNNING" and s["internal_mode"] == "STABLE":
                # Ramp up RPM and Temp if just started
                s["rpm"] += (NORMAL_RPM - s["rpm"]) * 0.2
                s["temp"] += (MAX_HEALTHY_TEMP - s["temp"]) * 0.05
                s["vib"] += (0.3 - s["vib"]) * 0.1
                
                # After 30 mins, check if we should start decaying (Requirement 18, 19)
                if elapsed > s["min_run_time"]:
                    if random.random() < 0.01: # Small chance to start failing
                        s["internal_mode"] = "DECAYING"
                        s["state_start"] = current_time

            # If machine is in GRADUAL DECAY (Requirement 16, 19, 21)
            elif s["internal_mode"] == "DECAYING":
                # Values change slowly but dangerously
                s["temp"] += 0.5  # Getting hotter
                s["vib"] += 0.02  # Shaking more
                s["pres"] -= 0.1  # Losing pressure
                s["rpm"] -= 2     # Slowing down
                
                # Once temp hits critical or 10 mins pass, STOP the machine
                if s["temp"] >= CRITICAL_TEMP or (current_time - s["state_start"]) > 600:
                    s["status"] = "STOPPED"
                    s["internal_mode"] = "STOPPED"
                    s["state_start"] = current_time
                    s["stop_duration"] = random.randint(180, 300)

            # If machine is STOPPED (Requirement 17)
            elif s["status"] == "STOPPED":
                s["rpm"] += (0 - s["rpm"]) * 0.3
                s["temp"] += (ROOM_TEMP - s["temp"]) * 0.02 # Cool down slowly
                s["pres"] += (0 - s["pres"]) * 0.2
                s["vib"] += (0 - s["vib"]) * 0.3
                
                # After 3-5 mins, Restart
                if elapsed > s["stop_duration"]:
                    s["status"] = "RUNNING"
                    s["internal_mode"] = "STABLE"
                    s["state_start"] = current_time

            # --- 2. DATA INJECTION (Outliers & Missing Values) ---
            
            # Requirement 1: Base JSON
            data = {
                "machine_id": m_id,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "temperature": round(s["temp"], 2),
                "vibration": round(s["vib"], 2),
                "pressure": round(s["pres"], 2),
                "rpm": int(s["rpm"]),
                "status": s["status"]
            }

            # Requirement 10: 5% Outliers (Sensor Glitches)
            if random.random() < 0.05:
                data["temperature"] = 999.9 if random.random() > 0.5 else -50.0

            # Requirement 11: 5% Missing Values
            if random.random() < 0.05:
                key_to_del = random.choice(["temperature", "vibration", "pressure", "rpm"])
                del data[key_to_del]

            client.publish(TOPIC, json.dumps(data))

        time.sleep(5) # 5 second interval for stability

threading.Thread(target=run_simulator, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
