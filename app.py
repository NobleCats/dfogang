from flask import Flask, request, jsonify, send_file, Response
import requests
import datetime
from collections import defaultdict
from pathlib import Path
import os
import json
from flask_cors import CORS
app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get('DFO_API_KEY', 'sRngDaw09CPuVYcpzfL1VG5F8ozrWnQQ')

DATA_DIR = "datas"


def search_characters(server, name):
    url = f"https://api.dfoneople.com/df/servers/{server}/characters?characterName={name}&limit=50&wordType=full&apikey={API_KEY}"
    r = requests.get(url)
    r.raise_for_status()
    return r.json().get('rows', [])

def get_profile(server, character_id):
    url = f"https://api.dfoneople.com/df/servers/{server}/characters/{character_id}?apikey={API_KEY}"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()


def get_equipment(server, character_id):
    url = f"https://api.dfoneople.com/df/servers/{server}/characters/{character_id}/equip/equipment?apikey={API_KEY}"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()

def get_character_id(server, name):
    url = f"https://api.dfoneople.com/df/servers/{server}/characters?characterName={name}&limit=1&wordType=full&apikey={API_KEY}"
    r = requests.get(url)
    r.raise_for_status()
    rows = r.json().get("rows", [])
    if rows:
        return rows[0]["characterId"]
    return None


@app.route("/profile", methods=["POST"])
def profile():
    data = request.json
    server = data.get("server")
    name = data.get("name")
    characterId = get_character_id(server, name)

    url = f"https://api.dfoneople.com/df/servers/{server}/characters/{characterId}?apikey={API_KEY}"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()


@app.route("/search", methods=["POST"])
def search():
    data = request.json
    server = data.get("server")
    name = data.get("name")

    characters = search_characters(server, name)
    if not characters:
        return jsonify({"error": "No characters found"}), 404
    
    # ✅ adventureName 붙이기
    result = []
    for char in characters:
        char_id = char.get("characterId")
        try:
            profile = get_profile(server, char_id)
            char["adventureName"] = profile.get("adventureName", "-")
        except Exception as e:
            print(f"[!] Failed to get profile for {char_id}: {e}")
            char["adventureName"] = "-"
        result.append(char)

    return jsonify({"results": result})

@app.route("/search_explorer", methods=["POST"])
def search_explorer():
    data = request.get_json()
    servers = ["cain", "siroco"]
    explorer_name = data.get("name")

    result = []

    for serverId in servers:
        base_path = Path(f"datas/{serverId}/{explorer_name}")
        if not base_path.exists():
            continue  # ❗없으면 그냥 넘어감

        for char_dir in base_path.iterdir():
            if not char_dir.is_dir():
                continue

            equipment_path = char_dir / "equipment.json"
            if not equipment_path.exists():
                continue

            try:
                with open(equipment_path, encoding="utf-8") as f:
                    equip_data = json.load(f)
                    result.append({
                        "characterId": char_dir.name,
                        "characterName": equip_data.get("characterName", ""),
                        "jobName": equip_data.get("jobName", ""),
                        "jobGrowName": equip_data.get("jobGrowName", ""),
                        "adventureName": equip_data.get("adventureName", ""),
                        "fame": equip_data.get("fame", 0),
                        "level": equip_data.get("level", 0),
                        "serverId": serverId
                    })
            except Exception as e:
                print(f"[❌] Error reading {equipment_path}: {e}")

    if not result:
        return jsonify({"error": "No explorer name found"}), 404

    return jsonify({"results": result})





def extract_slot_map(equipment_list):
    result = {}
    for item in equipment_list:
        slot = item.get("slotName") or item.get("slotId")
        if not slot:
            continue
        # 하나의 슬롯에 장비 + 융합석을 각각 분리해서 기록
        result[f"{slot}_gear"] = item.get("itemId")
        upgrade_info = item.get("upgradeInfo", {})
        if upgrade_info:
            result[f"{slot}_fusion"] = upgrade_info.get("itemId")
    return result


def compare_equipment_changes(old_eq, new_eq):
    """ 장비 및 융합석의 변경 슬롯을 각각 감지 """
    if not old_eq or not old_eq.get("equipment"):
        return []

    old_map = extract_slot_map(old_eq["equipment"])
    new_map = extract_slot_map(new_eq["equipment"])

    changes = []
    all_keys = set(old_map.keys()) | set(new_map.keys())
    for key in all_keys:
        before = old_map.get(key)
        after = new_map.get(key)
        if before != after:
            # key는 "slot_fusion" 혹은 "slot_gear" 형태
            base_slot, suffix = key.rsplit("_", 1)
            is_upgrade = "Yes" if suffix == "fusion" else "No"
            changes.append((base_slot, is_upgrade, before, after))
    return changes


@app.route("/equipment", methods=["POST"])
def equipment():
    data = request.json
    server = data.get("server")
    name = data.get("name")  # characterName

    character_id = get_character_id(server, name)
    if not character_id:
        return jsonify({"error": "Character not found"}), 404

    profile = get_profile(server, character_id)
    adventure_name = profile.get("adventureName")

    char_dir = os.path.join(DATA_DIR, server, adventure_name, character_id)
    os.makedirs(char_dir, exist_ok=True)
    eq_path = os.path.join(char_dir, "equipment.json")
    hist_path = os.path.join(char_dir, "history.json")
    fame_path = os.path.join(char_dir, "fame.json")

    new_eq = get_equipment(server, character_id)

    # ✅ 새 장비 정보: 슬롯별로 gear / fusion 분리 저장
    new_items = {}
    for item in new_eq.get("equipment", []):
        slot = item.get("slotName") or item.get("slotId")
        new_items[f"{slot}_gear"] = item.get("itemId")
        upgrade = item.get("upgradeInfo", {})
        if upgrade:
            new_items[f"{slot}_fusion"] = upgrade.get("itemId")

    # ✅ 기존 장비 정보 읽기
    old_items = {}
    is_first_time = not os.path.exists(eq_path)
    if not is_first_time:
        with open(eq_path, "r", encoding="utf-8") as f:
            old_data = json.load(f)
            for item in old_data.get("equipment", []):
                slot = item.get("slotName") or item.get("slotId")
                old_items[f"{slot}_gear"] = item.get("itemId")
                upgrade = item.get("upgradeInfo", {})
                if upgrade:
                    old_items[f"{slot}_fusion"] = upgrade.get("itemId")

    # ✅ 변경 감지
    changed_keys = []
    for key in new_items:
        if old_items.get(key) != new_items.get(key):
            changed_keys.append(key)

    # ✅ 기록: 최초 조회가 아닌 경우만
    if changed_keys and not is_first_time:
        history = []
        if os.path.exists(hist_path):
            with open(hist_path, "r", encoding="utf-8") as f:
                history = json.load(f)

        def parse_change_key(k):
            return (k.rsplit("_", 1)[0], "Yes" if k.endswith("_fusion") else "No")

        entry = {
            "date": datetime.date.today().isoformat(),
            "before": [
                {
                    "slotName": parse_change_key(k)[0],
                    "isUpgradeInfo": parse_change_key(k)[1],
                    "itemId": old_items.get(k)
                }
                for k in changed_keys
            ],
            "after": [
                {
                    "slotName": parse_change_key(k)[0],
                    "isUpgradeInfo": parse_change_key(k)[1],
                    "itemId": new_items.get(k)
                }
                for k in changed_keys
            ]
        }

        history.append(entry)
        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(history[-30:], f, ensure_ascii=False, indent=2)

    # ✅ 최신 장비 저장
    with open(eq_path, "w", encoding="utf-8") as f:
        json.dump(new_eq, f, ensure_ascii=False, indent=2)

    # ✅ 명성 로그 저장
    fame_value = new_eq.get("fame")
    if fame_value is not None:
        fame_log = []
        if os.path.exists(fame_path):
            with open(fame_path, "r", encoding="utf-8") as f:
                fame_log = json.load(f)

        today = datetime.date.today().isoformat()
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

        # 어제 값 찾기
        yesterday_entry = next((entry for entry in reversed(fame_log) if entry["date"] == yesterday), None)

        # 오늘과 어제가 같은 값이면 오늘 기록 제거 (또는 기록 안함)
        if fame_log and fame_log[-1]["date"] == today:
            # 오늘 이미 기록이 있다면, 명성이 달라졌는지 비교
            if fame_log[-1]["fame"] != fame_value:
                fame_log[-1]["fame"] = fame_value  # 업데이트
                with open(fame_path, "w", encoding="utf-8") as f:
                    json.dump(fame_log, f, ensure_ascii=False, indent=2)
        else:
            # 오늘 기록이 없다면 새로 추가
            fame_log.append({ "date": today, "fame": fame_value })
            fame_log = fame_log[-30:]
            with open(fame_path, "w", encoding="utf-8") as f:
                json.dump(fame_log, f, ensure_ascii=False, indent=2)
    return jsonify({
    "equipment": new_eq,
    "explorerName": adventure_name  # ✅ 추가
    })



@app.route("/fame-history", methods=["POST"])
def fame_history():
    data = request.json
    server = data.get("server")
    character_name = data.get("characterName")

    character_id = get_character_id(server, character_name)
    if not character_id:
        return jsonify({ "records": [] })

    profile = get_profile(server, character_id)
    adventure_name = profile.get("adventureName")

    fame_path = os.path.join(DATA_DIR, server, adventure_name, character_id, "fame.json")
    if not os.path.exists(fame_path):
        return jsonify({ "records": [] })

    with open(fame_path, "r", encoding="utf-8") as f:
        fame_history = json.load(f)

    return jsonify({ "records": fame_history })

@app.route('/item-fame/<item_id>')
def get_item_fame(item_id):
    try:
        url = f"https://api.dfoneople.com/df/items/{item_id}?apikey={API_KEY}"
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        fame = data.get("fame", None)
        return jsonify({"fame": fame})
    except Exception as e:
        print(f"[ERROR] Failed to fetch fame for {item_id}: {e}")
        return jsonify({"fame": None, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)

@app.route("/history", methods=["POST"])
def get_history():
    data = request.json
    server = data.get("server")
    name = data.get("characterName")

    character_id = get_character_id(server, name)
    if not character_id:
        return jsonify([])

    profile = get_profile(server, character_id)
    adventure_name = profile.get("adventureName")
    char_dir = os.path.join(DATA_DIR, server, adventure_name, character_id)
    hist_path = os.path.join(char_dir, "history.json")

    if not os.path.exists(hist_path):
        return jsonify([])

    with open(hist_path, "r", encoding="utf-8") as f:
        try:
            history = json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to read history.json: {e}")
            return jsonify([])

    return jsonify(history)
