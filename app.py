from flask import Flask, request, jsonify, send_file
import requests
import datetime
import os
import json
from flask_cors import CORS
app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get('DFO_API_KEY', 'sRngDaw09CPuVYcpzfL1VG5F8ozrWnQQ')

DATA_DIR = "datas"


def get_character_id(server, name):
    url = f"https://api.dfoneople.com/df/servers/{server}/characters?characterName={name}&apikey={API_KEY}"
    r = requests.get(url)
    r.raise_for_status()
    rows = r.json()['rows']
    if not rows:
        return None
    return rows[0]['characterId']

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


@app.route("/search", methods=["POST"])
def search():
    data = request.json
    server = data.get("server")
    name = data.get("name")
    character_id = get_character_id(server, name)
    if not character_id:
        return jsonify({"error": "Character not found"}), 404
    profile = get_profile(server, character_id)
    return jsonify({"characterId": character_id, "profile": profile})

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
        if not fame_log or fame_log[-1]["fame"] != fame_value:
            if not any(entry["date"] == today for entry in fame_log):
                fame_log.append({ "date": today, "fame": fame_value })
                fame_log = fame_log[-30:]
                with open(fame_path, "w", encoding="utf-8") as f:
                    json.dump(fame_log, f, ensure_ascii=False, indent=2)

    return jsonify({ "equipment": new_eq })



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


if __name__ == "__main__":
    app.run(debug=True)
