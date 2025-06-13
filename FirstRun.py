import os
import time
import json
import requests
import datetime
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

API_KEY = "sRngDaw09CPuVYcpzfL1VG5F8ozrWnQQ"
BASE_URL = "https://api.dfoneople.com/df"
SERVER_ID = "siroco"
SAVE_DIR = f"datas/{SERVER_ID}"

START_FAME = 30000
END_FAME = 90000
STEP = 1
THREAD_WORKERS = 10  # 병렬 처리 개수 (조절 가능)

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch(endpoint):
    url = f"{BASE_URL}{endpoint}&apikey={API_KEY}" if "?" in endpoint else f"{BASE_URL}{endpoint}?apikey={API_KEY}"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return res.json()
        else:
            print(f"❌ Error {res.status_code} for {url}")
    except Exception as e:
        print(f"❌ Exception for {url}: {e}")
    return None

def process_character(char):
    char_id = char["characterId"]
    profile = fetch(f"/servers/{SERVER_ID}/characters/{char_id}")
    if not profile:
        return

    explorerName = profile.get("adventureName", "unknown").replace("/", "_").replace("\\", "_")
    save_path = f"{SAVE_DIR}/{explorerName}/{char_id}"
    ensure_dir(save_path)

    if os.path.exists(f"{save_path}/equipment.json"):
        return

    save_json(f"{save_path}/profile.json", profile)

    equipment = fetch(f"/servers/{SERVER_ID}/characters/{char_id}/equip/equipment")
    if equipment:
        save_json(f"{save_path}/equipment.json", equipment)

    status = fetch(f"/servers/{SERVER_ID}/characters/{char_id}/status")
    if status:
        today = datetime.date.today().isoformat()
        fame_val = status.get("fame", 0)
        save_json(f"{save_path}/fame.json", [{"date": today, "fame": fame_val}])

def process_fame(fame):
    result = fetch(f"/servers/{SERVER_ID}/characters-fame?minFame={fame}&maxFame={fame}&limit=200")
    if not result:
        time.sleep(0.3)
        return

    with ThreadPoolExecutor(max_workers=THREAD_WORKERS) as executor:
        futures = [executor.submit(process_character, char) for char in result.get("rows", [])]
        for future in as_completed(futures):
            future.result()
    time.sleep(0.3)

if __name__ == "__main__":
    for fame in tqdm(range(START_FAME, END_FAME + 1, STEP)):
        process_fame(fame)
