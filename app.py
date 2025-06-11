from flask import Flask, request, jsonify, send_file
import requests
import os
import json
from flask_cors import CORS
app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get('DFO_API_KEY', 'sRngDaw09CPuVYcpzfL1VG5F8ozrWnQQ')

DATA_DIR = "datas"
ICON_BASE_FOLDER = "assets\equipments"
WEAPON_PREFIXES = [
    "One in a Hundred",
    "One of a Kind",
    "Legendary Lore",
    "Heroic Saga",
    "Primeval Star"
]


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

    # ✅ 변경된 경로
    char_dir = os.path.join(DATA_DIR, server, adventure_name, character_id)
    os.makedirs(char_dir, exist_ok=True)
    eq_path = os.path.join(char_dir, "equipment.json")
    hist_path = os.path.join(char_dir, "history.json")
    fame_path = os.path.join(char_dir, "fame.json")

    new_eq = get_equipment(server, character_id)

    # ✅ 기존과 동일한 장비 비교 및 기록
    old_eq = None
    if os.path.exists(eq_path):
        with open(eq_path, "r", encoding="utf-8") as f:
            old_eq = json.load(f)

    changed = (old_eq != new_eq)
    if changed:
        history = []
        if os.path.exists(hist_path):
            with open(hist_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        history.append({
            "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
            "change": "equipment_updated",
            "old": old_eq,
            "new": new_eq
        })
        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(history[-30:], f, ensure_ascii=False, indent=2)
        with open(eq_path, "w", encoding="utf-8") as f:
            json.dump(new_eq, f, ensure_ascii=False, indent=2)

    # ✅ Fame 기록 추가
    fame_history = []
    today = __import__('datetime').datetime.utcnow().date().isoformat()
    fame_value = new_eq.get("fame", None)
    if fame_value is not None:
        if os.path.exists(fame_path):
            with open(fame_path, "r", encoding="utf-8") as f:
                fame_history = json.load(f)
        if not any(record["date"] == today for record in fame_history):
            fame_history.append({ "date": today, "fame": fame_value })
        fame_history = fame_history[-30:]
        with open(fame_path, "w", encoding="utf-8") as f:
            json.dump(fame_history, f, ensure_ascii=False, indent=2)

    return jsonify({"changed": changed, "equipment": new_eq})

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
