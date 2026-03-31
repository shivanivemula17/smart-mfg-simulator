import paho.mqtt.client as mqtt
import json
import time
import random
import threading
from datetime import datetime, timezone
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Industrial Physics Simulator (20 Machines) is LIVE!"

def run_simulator():
    BROKER = "mqtt-dashboard.com"
    TOPIC = "manufacturing/sensor/all_machines"
    # Requirement 3: 20 Machines
    MACHINES = [f"M-{i:03}" for i in range(101, 121)] 
    
    # Internal State Tracking
    machine_data = {}
    for m in MACHINES:
        machine_data[m] = {
            "status": "Running",
            "temp": 25.0,
            "rpm": 0,
            "press": 0,
            "vib": 0,
            "state_timer": time.time(),
            "target_duration": random.randint(1800, 2700), # 30-45 mins in seconds
            "health_bias": random.uniform(0.9, 1.1) # Some machines run naturally hotter
        }

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(BROKER, 1883)

    def update_physics(m_id):
        m = machine_data[m_id]
        now = time.time()
        elapsed = now - m["state_timer"]

        # --- 1. STATE SWITCHING LOGIC (Requirement 15, 16, 17, 18) ---
        if m["status"] == "Running" and elapsed > m["target_duration"]:
            m["status"] = "Stopped"
            m["state_timer"] = now
            m["target_duration"] = random.randint(300, 600) # 5-10 mins stop
        
        elif m["status"] == "Stopped" and elapsed > m["target_duration"]:
            m["status"] = "Running"
            m["state_timer"] = now
            m["target_duration"] = random.randint(1800, 2700) # 30-45 mins run

        # --- 2. PHYSICS RAMPING (Requirement 12, 13, 14, 20) ---
        if m["status"] == "Running":
            # RPM Ramps up to 1500
            m["rpm"] += (1500 - m["rpm"]) * 0.1 
            # Temp Ramps up to 85.5
            target_t = 85.5 * m["health_bias"]
            m["temp"] += (target_t - m["temp"]) * 0.02
            # Pressure follows RPM
            m["press"] += (120.3 - m["press"]) * 0.1
            # Vibration has a "running rhythm"
            m["vib"] = 0.32 + (random.uniform(-0.05, 0.05))
        else:
            # STOPPED: Slow wind down (Requirement 18, 20)
            m["rpm"] += (0 - m["rpm"]) * 0.1
            m["press"] += (0 - m["press"]) * 0.1
            # Temp cools slowly toward room temp (25°C)
            m["temp"] += (25.0 - m["temp"]) * 0.01
            m["vib"] += (0 - m["vib"]) * 0.1

        # Add small rhythm/noise to values
        cur_temp = round(m["temp"] + random.uniform(-0.2, 0.2), 2)
        cur_vib = round(max(0, m["vib"] + random.uniform(-0.02, 0.02)), 3)
        cur_pres = round(max(0, m["press"] + random.uniform(-0.5, 0.5)), 1)
        cur_rpm = int(m["rpm"] + random.randint(-5, 5))

        # --- 3. OUTLIERS & MISSING VALUES (Requirement 9, 10) ---
        # 5% Outliers
        is_outlier = random.random() < 0.05
        if is_outlier:
            cur_temp = 500.0 if random.random() > 0.5 else -50.0
            cur_rpm = 9999

        payload = {
            "machine_id": m_id,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "temperature": cur_temp,
            "vibration": cur_vib,
            "pressure": cur_pres,
            "rpm": cur_rpm,
            "status": m["status"]
        }

        # 5% Missing Values (Remove one key)
        if random.random() < 0.05:
            key_to_del = random.choice(["temperature", "vibration", "pressure", "rpm"])
            del payload[key_to_del]

        return payload

    while True:
        try:
            for m_id in MACHINES:
                data = update_physics(m_id)
                client.publish(TOPIC, json.dumps(data))
            time.sleep(5) # Batch every 5 seconds
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

# Start in background
threading.Thread(target=run_simulator, daemon=True).start()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
