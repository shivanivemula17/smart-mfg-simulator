import paho.mqtt.client as mqtt
import json
import time
import random
import threading
from datetime import datetime, timezone
from flask import Flask

# --- WEB SERVER FOR RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Industrial Simulator is LIVE and Streaming!"

# --- YOUR ORIGINAL SIMULATOR LOGIC ---
def run_simulator():
    BROKER = "mqtt-dashboard.com"
    TOPIC = "manufacturing/sensor/all_machines"
    MACHINES = [f"M-{i:03}" for i in range(101, 111)]
    
    machine_states = {m: {"temp": 25.0, "status": "RUNNING", "health": "GOOD"} for m in MACHINES}

    # Using VERSION2 as per your requirement
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    
    # Add error handling for connection
    try:
        client.connect(BROKER, 1883)
        print("Connected to HiveMQ Broker")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    def generate_industrial_data(m_id):
        state = machine_states[m_id]
        
        # 1. STATUS PATTERN (~60/40)
        if random.random() < 0.05:
            state["status"] = "STOPPED" if state["status"] == "RUNNING" else "RUNNING"
            if state["status"] == "RUNNING": 
                state["health"] = "GOOD" if random.random() > 0.3 else "UNHEALTHY"

        # 2. PHYSICS
        if state["status"] == "RUNNING":
            rpm = random.randint(1450, 1550)
            pressure = round(random.uniform(115.0, 125.0), 2)
            target_temp = 85.0 if state["health"] == "GOOD" else 115.0
            state["temp"] += (target_temp - state["temp"]) * 0.1
            vibration = round(random.uniform(0.1, 0.4), 2) if state["health"] == "GOOD" else round(random.uniform(0.7, 1.4), 2)
        else:
            rpm = 0
            pressure = round(random.uniform(0, 10), 2)
            state["temp"] += (25.0 - state["temp"]) * 0.05
            vibration = round(random.uniform(0, 0.05), 2)

        # 3. OUTLIERS
        if random.random() < 0.05:
            if random.random() < 0.5: state["temp"] = 500.0 
            else: rpm = 9999

        data = {
            "machine_id": m_id,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "temperature": round(state["temp"], 2),
            "vibration": vibration,
            "pressure": pressure,
            "rpm": rpm,
            "status": state["status"]
        }

        # 4. MISSING VALUES
        if random.random() < 0.05:
            key_to_remove = random.choice(["pressure", "vibration", "rpm"])
            del data[key_to_remove]

        return data

    while True:
        try:
            for m_id in MACHINES:
                payload = generate_industrial_data(m_id)
                client.publish(TOPIC, json.dumps(payload))
            # print(f"Batch sent at {datetime.now()}") # Optional logging
            time.sleep(5) # Set to 5s for Render Free Tier stability
        except Exception as e:
            print(f"Error in loop: {e}")
            time.sleep(10)

# Start simulator in background
threading.Thread(target=run_simulator, daemon=True).start()

if __name__ == "__main__":
    # Render provides a PORT environment variable
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)