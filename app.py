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
    """ 슬롯별로 장비와 융합석 정보를 map으로 정리 """
    slot_map = {}
    for eq in equipment_list:
        slot = eq.get("slotName") or eq.get("slotId")
        slot_map[slot] = {
            "itemId": eq.get("itemId"),
            "isUpgradeInfo": "No"
        }
        if eq.get("upgradeInfo"):
            slot_map[slot + "_fusion"] = {
                "itemId": eq["upgradeInfo"].get("itemId"),
                "isUpgradeInfo": "Yes"
            }
    return slot_map

def compare_equipment_changes(old_eq, new_eq):
    """ 변경된 슬롯 정보만 추출 """
    if not old_eq or not old_eq.get("equipment"): return []

    old_map = extract_slot_map(old_eq["equipment"])
    new_map = extract_slot_map(new_eq["equipment"])

    changes = []
    all_slots = set(old_map.keys()) | set(new_map.keys())
    for slot in all_slots:
        before = old_map.get(slot)
        after = new_map.get(slot)
        if before != after:
            changes.append((slot, before, after))
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
    new_items = {}
    for item in new_eq.get("equipment", []):
        slot = item.get("slotName") or item.get("slotId")
        new_items[slot] = {
            "itemId": item.get("itemId"),
            "upgradeId": item.get("upgradeInfo", {}).get("itemId")
        }

    old_items = {}
    is_first_time = not os.path.exists(eq_path)
    if not is_first_time:
        with open(eq_path, "r", encoding="utf-8") as f:
            old_data = json.load(f)
            for item in old_data.get("equipment", []):
                slot = item.get("slotName") or item.get("slotId")
                old_items[slot] = {
                    "itemId": item.get("itemId"),
                    "upgradeId": item.get("upgradeInfo", {}).get("itemId")
                }

    changed_slots = []
    for slot in new_items:
        new_info = new_items[slot]
        old_info = old_items.get(slot)
        if old_info != new_info:
            changed_slots.append(slot)

    # ✅ 최초 조회 시에는 기록하지 않고 장비만 저장
    if changed_slots and not is_first_time:
        history = []
        if os.path.exists(hist_path):
            with open(hist_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        entry = {
            "date": datetime.date.today().isoformat(),
            "before": [
                {
                    "slotName": s,
                    "isUpgradeInfo": "Yes" if old_items.get(s, {}).get("upgradeId") else "No",
                    "itemId": old_items.get(s, {}).get("upgradeId") or old_items.get(s, {}).get("itemId")
                }
                for s in changed_slots
            ],
            "after": [
                {
                    "slotName": s,
                    "isUpgradeInfo": "Yes" if new_items.get(s, {}).get("upgradeId") else "No",
                    "itemId": new_items.get(s, {}).get("upgradeId") or new_items.get(s, {}).get("itemId")
                }
                for s in changed_slots
            ]
        }
        history.append(entry)
        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(history[-30:], f, ensure_ascii=False, indent=2)

    with open(eq_path, "w", encoding="utf-8") as f:
        json.dump(new_eq, f, ensure_ascii=False, indent=2)

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
