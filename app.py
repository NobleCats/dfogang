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
        
        profile = get_equipment(server, char_id)
        set_info_list = profile.get("setItemInfo", [])
        if set_info_list and isinstance(set_info_list[0], dict):
            set_info = set_info_list[0]
            set_name = set_info.get("setItemName", "")
            set_rarity = set_info.get("setItemRarityName", "")
            set_point = set_info.get("active", {}).get("setPoint", {}).get("current", 0)
        else:
            set_name = ""
            set_rarity = ""
            set_point = 0

        result.append({
            "characterId": char_id,
            "characterName": profile.get("characterName", ""),
            "jobName": profile.get("jobName", ""),
            "jobGrowName": profile.get("jobGrowName", ""),
            "adventureName": profile.get("adventureName", ""),
            "fame": profile.get("fame", 0),
            "level": profile.get("level", 0),
            "setItemName": set_name,
            "setItemRarityName": set_rarity,
            "setPoint": set_point,
            "serverId": server
        })
        #result.append(char)

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
            continue

        for char_dir in base_path.iterdir():
            if not char_dir.is_dir():
                continue

            equipment_path = char_dir / "equipment.json"
            if not equipment_path.exists():
                continue

            try:
                with open(equipment_path, encoding="utf-8") as f:
                    equip_data = json.load(f)

                    # ✅ setItemInfo 처리
                    set_info_list = equip_data.get("setItemInfo", [])
                    if set_info_list and isinstance(set_info_list[0], dict):
                        set_info = set_info_list[0]
                        set_name = set_info.get("setItemName", "")
                        set_rarity = set_info.get("setItemRarityName", "")
                        set_point = set_info.get("active", {}).get("setPoint", {}).get("current", 0)
                    else:
                        set_name = ""
                        set_rarity = ""
                        set_point = 0

                    result.append({
                        "characterId": char_dir.name,
                        "characterName": equip_data.get("characterName", ""),
                        "jobName": equip_data.get("jobName", ""),
                        "jobGrowName": equip_data.get("jobGrowName", ""),
                        "adventureName": equip_data.get("adventureName", ""),
                        "fame": equip_data.get("fame", 0),
                        "level": equip_data.get("level", 0),
                        "setItemName": set_name,
                        "setItemRarityName": set_rarity,
                        "setPoint": set_point,
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
        history = history_cleaner(history)
        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(history[-30:], f, ensure_ascii=False, indent=2)

    # ✅ 최신 장비 저장
    with open(eq_path, "w", encoding="utf-8") as f:
        json.dump(new_eq, f, ensure_ascii=False, indent=2)

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
    print("💡 fame_path =", fame_path)
    # 현재 명성 불러오기
    current_fame = profile.get("fame")
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    # 기록이 없다면 새로 만듦
    if not os.path.exists(fame_path):
        fame_history = []
    else:
        with open(fame_path, "r", encoding="utf-8") as f:
            fame_history = json.load(f)

    # 마지막 기록과 현재 명성이 다를 경우에만 추가
    if not fame_history or fame_history[-1]["fame"] != current_fame:
        print("📌 추가하려는 데이터:", today_str, current_fame)
        print("💾 저장 직전 fame_history:", fame_history)
        fame_history.append({ "date": today_str, "fame": current_fame })
        print("⚠️ 명성 기록 추가됨:", current_fame)
        os.makedirs(os.path.dirname(fame_path), exist_ok=True)
        with open(fame_path, "w", encoding="utf-8") as f:
            json.dump(fame_history, f, ensure_ascii=False, indent=2)
    else:
        print("✅ 명성 동일 - 기록 생략:", current_fame)

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

def history_cleaner(history):
    """같은 날짜 내에서 원복된 변경사항은 제거하는 함수"""
    grouped = defaultdict(list)

    # 날짜별로 그룹핑
    for entry in history:
        grouped[entry["date"]].append(entry)

    cleaned_history = []

    for date, entries in grouped.items():
        temp = []

        for entry in entries:
            temp.append({
                "before": entry["before"],
                "after": entry["after"]
            })

        # 슬롯별 변경 추적
        slot_state = {}

        for change in temp:
            for b in change["before"]:
                key = (b["slotName"], b["isUpgradeInfo"])
                slot_state[key] = b["itemId"]

            for a in change["after"]:
                key = (a["slotName"], a["isUpgradeInfo"])
                slot_state[key] = a["itemId"]

        # 같은 날 원래 상태로 돌아온 경우 제거
        filtered = []
        for change in temp:
            undone = True
            for b, a in zip(change["before"], change["after"]):
                key = (b["slotName"], b["isUpgradeInfo"])
                # 마지막 상태가 최초 상태와 다르면 유지
                if slot_state.get(key) != b["itemId"]:
                    undone = False
                    break
            if not undone:
                filtered.append(change)

        # 날짜별 결과를 다시 합침
        for f in filtered:
            cleaned_history.append({
                "date": date,
                "before": f["before"],
                "after": f["after"]
            })

    # 최신 30개만 유지
    return cleaned_history[-30:]

if __name__ == "__main__":
    app.run(debug=True)