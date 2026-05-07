import pandas as pd
import requests
from datetime import datetime, timezone, timedelta

API_PUT_URL = "http://localhost:7071/api/sensors"
CSV_FILE = "notebook/sensor_data_april_2026.csv"

df = pd.read_csv(CSV_FILE)

def adjust_timestamp(index):
    now = datetime.now(timezone.utc)
    return (now - timedelta(minutes=index)).isoformat()

success = 0
fail = 0

for i, row in df.iterrows():
    payload = {
        "machine_id": row["machine_id"],
        "timestamp": adjust_timestamp(i),
        "variable": row["variable"],
        "value": float(row["value"])
    }

    response = requests.put(API_PUT_URL, json=payload)

    print(response.status_code)
    
    if response.status_code == 200:
        success += 1
    else:
        fail += 1
    if i % 100 == 0:
        print(f"Sent {i} records, status: {response.status_code}")
print("Finalizado")
print("Total OK:", success)
print("Total FAIL:", fail)