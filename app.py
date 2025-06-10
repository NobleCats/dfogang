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
    name = data.get("name")
    character_id = get_character_id(server, name)
    if not character_id:
        return jsonify({"error": "Character not found"}), 404

    # 경로: datas/server/name/character_id/
    char_dir = os.path.join(DATA_DIR, server, name, character_id)
    os.makedirs(char_dir, exist_ok=True)
    eq_path = os.path.join(char_dir, "equipment.json")
    hist_path = os.path.join(char_dir, "history.json")

    new_eq = get_equipment(server, character_id)
    # 이전 equipment.json 로드
    old_eq = None
    if os.path.exists(eq_path):
        with open(eq_path, "r", encoding="utf-8") as f:
            old_eq = json.load(f)

    # 변화 감지 (여기선 단순 비교, 실제론 슬롯별 비교 권장)
    changed = (old_eq != new_eq)
    if changed:
        # history 기록 append
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
        # 30일 이내 기록만 유지 등 추가 로직 구현 가능
        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(history[-30:], f, ensure_ascii=False, indent=2)
        with open(eq_path, "w", encoding="utf-8") as f:
            json.dump(new_eq, f, ensure_ascii=False, indent=2)

    return jsonify({"changed": changed, "equipment": new_eq})

if __name__ == "__main__":
    app.run(debug=True)
