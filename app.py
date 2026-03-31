import paho.mqtt.client as mqtt
import json
import time
import random
import threading
from datetime import datetime, timezone
from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Industrial Physics Simulator (10 Machines) is ACTIVE"

# --- SIMULATOR CONFIG ---
BROKER = "mqtt-dashboard.com"
TOPIC = "manufacturing/sensor/all_machines"
MACHINES = [f"M-{i:03}" for i in range(101, 111)]

# Internal state memory for 10 machines
# States: 'IDLE', 'STARTING', 'HEALTHY', 'DEGRADING', 'STOPPING'
m_data = {}
for m in MACHINES:
    m_data[m] = {
        "state": "IDLE",
        "temp": 25.0,
        "rpm": 0,
        "vib": 0.01,
        "press": 1.0,
        "timer": random.randint(180, 300), # 3-5 mins in seconds
        "total_run_time": 0
    }

def run_physics_engine():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(BROKER, 1883)

    while True:
        for m in MACHINES:
            s = m_data[m]
            
            # --- STATE MACHINE LOGIC ---
            if s["state"] == "IDLE":
                s["timer"] -= 5
                if s["timer"] <= 0:
                    s["state"] = "STARTING"
                    s["timer"] = 60 # 1 min startup

            elif s["state"] == "STARTING":
                s["rpm"] += 150 # Slow ramp up
                s["press"] += 12
                s["temp"] += 2.0
                s["timer"] -= 5
                if s["rpm"] >= 1500:
                    s["state"] = "HEALTHY"
                    s["timer"] = random.randint(1800, 2400) # At least 30-40 mins

            elif s["state"] == "HEALTHY":
                # Jitter values slightly for realism
                s["rpm"] = random.randint(1490, 1510)
                s["temp"] += (80 - s["temp"]) * 0.05
                s["vib"] = round(random.uniform(0.2, 0.35), 2)
                s["press"] = round(random.uniform(118, 122), 2)
                s["timer"] -= 5
                if s["timer"] <= 0:
                    s["state"] = "DEGRADING"
                    s["timer"] = 300 # 5 min degradation

            elif s["state"] == "DEGRADING":
                s["vib"] += 0.05 # Vibration climbs
                s["temp"] += 1.5 # Getting hot
                s["rpm"] -= 20   # Losing power
                s["timer"] -= 5
                if s["timer"] <= 0 or s["temp"] > 115:
                    s["state"] = "STOPPING"
                    s["timer"] = 60

            elif s["state"] == "STOPPING":
                s["rpm"] = max(0, s["rpm"] - 200)
                s["press"] = max(1, s["press"] - 20)
                s["temp"] -= 1.0 # Cooling
                s["timer"] -= 5
                if s["rpm"] == 0:
                    s["state"] = "IDLE"
                    s["timer"] = random.randint(180, 300) # 3-5 min stop

            # --- MAP INTERNAL STATES TO EXTERNAL STATUS (Requirement 20) ---
            ext_status = "STOPPED" if s["state"] == "IDLE" else "RUNNING"

            # --- CONSTRUCT PAYLOAD (Requirement 1) ---
            payload = {
                "machine_id": m,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "temperature": round(s["temp"], 2),
                "vibration": round(s["vib"], 2),
                "pressure": round(s["press"], 2),
                "rpm": int(s["rpm"]),
                "status": ext_status
            }

            # --- 5% OUTLIERS (Requirement 10) ---
            if random.random() < 0.05:
                payload["temperature"] = 999.9 if random.random() > 0.5 else -50.0

            # --- 5% MISSING VALUES (Requirement 11) ---
            if random.random() < 0.05:
                key_to_del = random.choice(["vibration", "pressure", "rpm"])
                del payload[key_to_del]

            client.publish(TOPIC, json.dumps(payload))
        
        time.sleep(5) # The "Heartbeat" every 5 seconds

# Start simulation in separate thread
threading.Thread(target=run_physics_engine, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
