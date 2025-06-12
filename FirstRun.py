import os
import time
import json
import requests
import datetime
from tqdm import tqdm

API_KEY = "sRngDaw09CPuVYcpzfL1VG5F8ozrWnQQ"
BASE_URL = "https://api.dfoneople.com/df"
SERVER_ID = "cain"
SAVE_DIR = f"datas/{SERVER_ID}"

START_FAME = 30000
END_FAME = 90000
STEP = 1

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch(endpoint):
    url = f"{BASE_URL}{endpoint}&apikey={API_KEY}" if "?" in endpoint else f"{BASE_URL}{endpoint}?apikey={API_KEY}"
    res = requests.get(url)
    if res.status_code == 200:
        return res.json()
    else:
        print(f"❌ Error {res.status_code} for {url}")
        return None

for fame in tqdm(range(START_FAME, END_FAME + 1, STEP)):
    result = fetch(f"/servers/{SERVER_ID}/characters-fame?minFame={fame}&maxFame={fame}&limit=200")
    if not result:
        time.sleep(0.3)
        continue

    for char in result.get("rows", []):
        char_id = char["characterId"]

        profile = fetch(f"/servers/{SERVER_ID}/characters/{char_id}")
        if not profile:
            continue

        explorerName = profile.get("adventureName", "unknown").replace("/", "_").replace("\\", "_")
        save_path = f"{SAVE_DIR}/{explorerName}/{char_id}"
        ensure_dir(save_path)

        # ✅ Resume 조건: equipment.json 있으면 skip
        if os.path.exists(f"{save_path}/equipment.json"):
            continue

        # 저장: profile.json
        save_json(f"{save_path}/profile.json", profile)

        # 저장: equipment.json
        equipment = fetch(f"/servers/{SERVER_ID}/characters/{char_id}/equip/equipment")
        if equipment:
            save_json(f"{save_path}/equipment.json", equipment)

        # 저장: fame.json
        status = fetch(f"/servers/{SERVER_ID}/characters/{char_id}/status")
        if status:
            today = datetime.date.today().isoformat()
            fame_val = status.get("fame", 0)
            save_json(f"{save_path}/fame.json", [{"date": today, "fame": fame_val}])

        time.sleep(0.3)
