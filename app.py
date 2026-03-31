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
    return "Industrial Physics Simulator (v2) is LIVE."

def run_simulator():
    BROKER = "mqtt-dashboard.com"
    TOPIC = "manufacturing/sensor/all_machines"
    # Requirement 3: 10 Machines
    MACHINES = [f"M-{i:03}" for i in range(101, 111)]
    
    # Configuration for "Machine Nature"
    # States: RUNNING, STOPPING, STOPPED, STARTING
    states = {}
    for m in MACHINES:
        states[m] = {
            "status": "RUNNING",
            "temp": 25.0,
            "vib": 0.2,
            "press": 120.0,
            "rpm": 1500,
            "timer": time.time() + random.randint(1800, 3600), # Req 18: At least 30 mins
            "health_degradation": 0 # 0 to 1, increases before failure
        }

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(BROKER, 1883)

    while True:
        now = time.time()
        
        for m_id in MACHINES:
            s = states[m_id]
            
            # --- STATE TRANSITION LOGIC (The Rhythm) ---
            
            if s["status"] == "RUNNING":
                # If 30+ mins passed, 10% chance to start degrading
                if now > s["timer"] and random.random() < 0.01:
                    s["status"] = "WARNING"
                    s["timer"] = now + 300 # 5 mins of warning before stop
                
                # Normal Physics
                target_temp = 82.0 + (s["health_degradation"] * 30)
                s["temp"] += (target_temp - s["temp"]) * 0.05 # Gradual rise
                s["vib"] = 0.25 + (s["health_degradation"] * 0.8) + random.uniform(-0.02, 0.02)
                s["rpm"] = 1500 + random.randint(-5, 5)
                s["press"] = 120.0 + random.uniform(-1, 1)

            elif s["status"] == "WARNING":
                # Values start changing "slowly" before stopping (Req 19)
                s["health_degradation"] += 0.01
                s["temp"] += 0.5
                s["vib"] += 0.05
                if now > s["timer"]:
                    s["status"] = "STOPPED"
                    s["timer"] = now + random.randint(180, 300) # Req 17: 3-5 mins stop

            elif s["status"] == "STOPPED":
                # Cool down physics
                s["temp"] += (25.0 - s["temp"]) * 0.02 # Slow cooling
                s["vib"] += (0.01 - s["vib"]) * 0.1
                s["press"] += (0.0 - s["press"]) * 0.1
                s["rpm"] = 0
                if now > s["timer"]:
                    s["status"] = "STARTING"
                    s["timer"] = now + 60 # 1 min to warm up

            elif s["status"] == "STARTING":
                s["rpm"] = 1500
                s["press"] = 120.0
                s["temp"] += 2.0
                if s["temp"] > 60: # Once warm enough, set to running
                    s["status"] = "RUNNING"
                    s["health_degradation"] = 0
                    s["timer"] = now + 1800 # Req 18: Reset 30 min timer

            # --- DATA ANOMALIES (Req 10 & 11) ---
            
            # Construct Base JSON (Req 1 & 2)
            display_status = "RUNNING" if s["status"] in ["RUNNING", "WARNING", "STARTING"] else "STOPPED"
            
            payload = {
                "machine_id": m_id,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "temperature": round(s["temp"], 2),
                "vibration": round(s["vib"], 2),
                "pressure": round(s["press"], 2),
                "rpm": s["rpm"],
                "status": display_status
            }

            # 5% Outliers (Req 10)
            if random.random() < 0.05:
                payload["temperature"] = 999.9 if random.random() < 0.5 else -50.0
            
            # 5% Missing Values (Req 11)
            if random.random() < 0.05:
                del payload[random.choice(["vibration", "pressure", "rpm"])]

            # Publish
            client.publish(TOPIC, json.dumps(payload))

        time.sleep(5)

# Deploy
threading.Thread(target=run_simulator, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
