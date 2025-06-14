import asyncio
import aiohttp
from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
from collections import defaultdict
from pathlib import Path
import os
import json

# --- dmgCalc.py에서 CharacterAnalyzer 클래스를 임포트합니다 ---
# 이 코드가 작동하려면 dmgCalc.py와 app.py가 같은 폴더에 있어야 합니다.
try:
    from dmgCalc import CharacterAnalyzer
except ImportError:
    print("오류: dmgCalc.py 파일을 찾을 수 없습니다. app.py와 같은 폴더에 있는지 확인해주세요.")
    CharacterAnalyzer = None

# --- 기본 설정 ---
app = Flask(__name__)
CORS(app) # 모든 도메인에서의 요청을 허용

API_KEY = os.environ.get('DFO_API_KEY', 'sRngDaw09CPuVYcpzfL1VG5F8ozrWnQQ')
BASE_URL = "https://api.dfoneople.com/df"
DATA_DIR = "datas"

# --- 비동기 API 헬퍼 함수 ---
async def fetch_json(session, url):
    """주어진 URL로 비동기 GET 요청을 보내고 JSON 응답을 반환합니다."""
    try:
        # URL에 API 키가 없을 경우 자동으로 추가합니다.
        if 'apikey=' not in url:
            url += f"&apikey={API_KEY}"

        async with session.get(url) as response:
            response.raise_for_status()  # 200 OK가 아니면 예외 발생
            return await response.json()
    except aiohttp.ClientError as e:
        print(f"API 요청 실패: {url}, 오류: {e}")
        return None

async def async_search_characters(session, server, name):
    url = f"{BASE_URL}/servers/{server}/characters?characterName={name}&limit=50&wordType=full&apikey={API_KEY}"
    data = await fetch_json(session, url)
    return data.get('rows', []) if data else []

async def async_get_profile(session, server, character_id):
    url = f"{BASE_URL}/servers/{server}/characters/{character_id}?apikey={API_KEY}"
    return await fetch_json(session, url)

async def async_get_equipment(session, server, character_id):
    url = f"{BASE_URL}/servers/{server}/characters/{character_id}/equip/equipment?apikey={API_KEY}"
    return await fetch_json(session, url)

async def async_get_character_id(session, server, name):
    """캐릭터 이름으로 캐릭터 ID를 비동기적으로 조회합니다. (정확도 높은 match 옵션 사용)"""
    url = f"{BASE_URL}/servers/{server}/characters?characterName={name}&wordType=match"
    data = await fetch_json(session, url)
    if data and data.get("rows"):
        return data["rows"][0]["characterId"]
    return None

# --- 기존 라우트 (변경 없음) ---

@app.route("/profile", methods=["POST"])
async def profile():
    data = request.json
    server, name = data.get("server"), data.get("name")
    
    async with aiohttp.ClientSession() as session:
        character_id = await async_get_character_id(session, server, name)
        if not character_id:
            return jsonify({"error": "Character not found"}), 404
        
        profile_data = await async_get_profile(session, server, character_id)
        if not profile_data:
            return jsonify({"error": "Failed to fetch profile"}), 500
            
        return jsonify(profile_data)

@app.route("/search", methods=["POST"])
async def search():
    data = request.json
    server, name = data.get("server"), data.get("name")

    async with aiohttp.ClientSession() as session:
        characters = await async_search_characters(session, server, name)
        if not characters:
            return jsonify({"error": "No characters found"}), 404
        
        tasks = [async_get_equipment(session, server, char["characterId"]) for char in characters]
        equipment_results = await asyncio.gather(*tasks)

        final_result = []
        for equip_data in equipment_results:
            if not equip_data: continue

            # [FIXED] setItemInfo가 None이거나 비어있는 경우를 방어적으로 처리
            set_info_list = equip_data.get("setItemInfo")
            if set_info_list and isinstance(set_info_list, list) and len(set_info_list) > 0:
                set_info = set_info_list[0]
            else:
                set_info = {} # 기본값으로 빈 딕셔너리 사용

            final_result.append({
                "characterId": equip_data.get("characterId", ""),
                "characterName": equip_data.get("characterName", ""),
                "jobName": equip_data.get("jobName", ""),
                "jobGrowName": equip_data.get("jobGrowName", ""),
                "adventureName": equip_data.get("adventureName", ""),
                "fame": equip_data.get("fame", 0),
                "level": equip_data.get("level", 0),
                "setItemName": set_info.get("setItemName", ""),
                "setItemRarityName": set_info.get("setItemRarityName", ""),
                "setPoint": set_info.get("active", {}).get("setPoint", {}).get("current", 0),
                "serverId": server
            })
            
    return jsonify({"results": final_result})

@app.route("/equipment", methods=["POST"])
async def equipment():
    data = request.json
    server, name = data.get("server"), data.get("name")

    async with aiohttp.ClientSession() as session:
        character_id = await async_get_character_id(session, server, name)
        if not character_id:
            return jsonify({"error": "Character not found"}), 404
        
        profile_task = async_get_profile(session, server, character_id)
        equipment_task = async_get_equipment(session, server, character_id)
        profile_data, new_eq = await asyncio.gather(profile_task, equipment_task)
        
        if not profile_data or not new_eq:
            return jsonify({"error": "Failed to fetch character data"}), 500

    adventure_name = profile_data.get("adventureName")
    fame = profile_data.get("fame")
    
    char_dir = Path(DATA_DIR) / server / adventure_name / character_id
    char_dir.mkdir(parents=True, exist_ok=True)
    eq_path = char_dir / "equipment.json"
    hist_path = char_dir / "history.json"

    new_items = {}
    for item in new_eq.get("equipment", []):
        slot = item.get("slotName") or item.get("slotId")
        new_items[f"{slot}_gear"] = item.get("itemId")
        if upgrade := item.get("upgradeInfo"):
            new_items[f"{slot}_fusion"] = upgrade.get("itemId")

    old_items = {}
    is_first_time = not eq_path.exists()
    if not is_first_time:
        # 파일이 존재하지 않을 경우를 대비하여 try-except 블록 추가
        try:
            with open(eq_path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                for item in old_data.get("equipment", []):
                    slot = item.get("slotName") or item.get("slotId")
                    old_items[f"{slot}_gear"] = item.get("itemId")
                    if upgrade := item.get("upgradeInfo"):
                        old_items[f"{slot}_fusion"] = upgrade.get("itemId")
        except (json.JSONDecodeError, FileNotFoundError):
            old_data = {} # 파일 읽기 실패 시 빈 데이터로 처리

    changed_keys = [key for key in new_items if old_items.get(key) != new_items.get(key)]

    if changed_keys and not is_first_time:
        history = []
        if hist_path.exists():
            try:
                with open(hist_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                history = [] # 파일 읽기 실패 시 빈 리스트로 처리

        def parse_change_key(k):
            return (k.rsplit("_", 1)[0], "Yes" if k.endswith("_fusion") else "No")

        entry = {
            "date": datetime.date.today().isoformat(),
            "before": [{"slotName": parse_change_key(k)[0], "isUpgradeInfo": parse_change_key(k)[1], "itemId": old_items.get(k)} for k in changed_keys],
            "after": [{"slotName": parse_change_key(k)[0], "isUpgradeInfo": parse_change_key(k)[1], "itemId": new_items.get(k)} for k in changed_keys]
        }
        history.append(entry)
        history = history_cleaner(history)
        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
            
    with open(eq_path, "w", encoding="utf-8") as f:
        json.dump(new_eq, f, ensure_ascii=False, indent=2)

    return jsonify({"equipment": new_eq, "explorerName": adventure_name, "fame": fame})

@app.route("/fame-history", methods=["POST"])
async def fame_history():
    data = request.json
    server, character_name = data.get("server"), data.get("characterName")

    async with aiohttp.ClientSession() as session:
        character_id = await async_get_character_id(session, server, character_name)
        if not character_id: return jsonify({"records": []})

        profile_data = await async_get_profile(session, server, character_id)
        if not profile_data: return jsonify({"error": "Failed to fetch profile"}), 500
            
    adventure_name = profile_data.get("adventureName")
    fame_path = Path(DATA_DIR) / server / adventure_name / character_id / "fame.json"
    current_fame = profile_data.get("fame")
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    fame_history_data = []
    if fame_path.exists():
        try:
            with open(fame_path, "r", encoding="utf-8") as f:
                fame_history_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            fame_history_data = [] # 파일 읽기 실패 시 빈 리스트로 처리
            
    if not fame_history_data or fame_history_data[-1].get("fame") != current_fame:
        fame_history_data.append({"date": today_str, "fame": current_fame})
        fame_path.parent.mkdir(parents=True, exist_ok=True)
        with open(fame_path, "w", encoding="utf-8") as f:
            json.dump(fame_history_data, f, ensure_ascii=False, indent=2)

    return jsonify({"records": fame_history_data})

@app.route('/item-fame/<item_id>')
async def get_item_fame(item_id):
    async with aiohttp.ClientSession() as session:
        url = f"{BASE_URL}/items/{item_id}?apikey={API_KEY}"
        data = await fetch_json(session, url)
        if data:
            return jsonify({"fame": data.get("fame", None)})
        return jsonify({"fame": None, "error": "Failed to fetch item"}), 500

@app.route("/history", methods=["POST"])
async def get_history():
    data = request.json
    server, name = data.get("server"), data.get("characterName")

    async with aiohttp.ClientSession() as session:
        character_id = await async_get_character_id(session, server, name)
        if not character_id: return jsonify([])
        
        profile_data = await async_get_profile(session, server, character_id)
        if not profile_data: return jsonify([])

    adventure_name = profile_data.get("adventureName")
    hist_path = Path(DATA_DIR) / server / adventure_name / character_id / "history.json"
    
    if not hist_path.exists(): return jsonify([])
    
    try:
        with open(hist_path, "r", encoding="utf-8") as f:
            history_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return jsonify([])
            
    return jsonify(history_data)

@app.route("/search_explorer", methods=["POST"])
def search_explorer():
    data = request.get_json()
    servers = ["cain", "siroco"]
    explorer_name = data.get("name")
    result = []
    for serverId in servers:
        base_path = Path(f"datas/{serverId}/{explorer_name}")
        if not base_path.exists(): continue
        for char_dir in base_path.iterdir():
            if not char_dir.is_dir(): continue
            equipment_path = char_dir / "equipment.json"
            if not equipment_path.exists(): continue
            try:
                with open(equipment_path, encoding="utf-8") as f:
                    equip_data = json.load(f)
                
                # [FIXED] setItemInfo가 None이거나 비어있는 경우를 방어적으로 처리
                set_info_list = equip_data.get("setItemInfo")
                if set_info_list and isinstance(set_info_list, list) and len(set_info_list) > 0:
                    set_info = set_info_list[0]
                else:
                    set_info = {} # 기본값으로 빈 딕셔너리 사용
                    
                result.append({
                    "characterId": char_dir.name, "characterName": equip_data.get("characterName", ""),
                    "jobName": equip_data.get("jobName", ""), "jobGrowName": equip_data.get("jobGrowName", ""),
                    "adventureName": equip_data.get("adventureName", ""), "fame": equip_data.get("fame", 0),
                    "level": equip_data.get("level", 0), "setItemName": set_info.get("setItemName", ""),
                    "setItemRarityName": set_info.get("setItemRarityName", ""),
                    "setPoint": set_info.get("active", {}).get("setPoint", {}).get("current", 0),
                    "serverId": serverId
                })
            except Exception as e:
                print(f"[❌] Error reading {equipment_path}: {e}")
    if not result: return jsonify({"error": "No explorer name found"}), 404
    return jsonify({"results": result})

@app.route("/search_log", methods=["POST"])
def log_search():
    data = request.get_json()
    log_entry = {
        "timestamp": datetime.date.today().isoformat(),
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        "server": data.get("server", ""), "name": data.get("name", "").strip()
    }
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"search_log_{date_str}.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    return jsonify({"status": "ok"})

def history_cleaner(history):
    grouped = defaultdict(list)
    for entry in history:
        grouped[entry["date"]].append(entry)

    cleaned_history = []
    for date, entries in grouped.items():
        final_slot_state = {}
        initial_slot_state = {}
        for entry in entries:
            for item_before in entry["before"]:
                key = (item_before["slotName"], item_before["isUpgradeInfo"])
                if key not in initial_slot_state:
                    initial_slot_state[key] = item_before["itemId"]
            for item_after in entry["after"]:
                key = (item_after["slotName"], item_after["isUpgradeInfo"])
                final_slot_state[key] = item_after["itemId"]
        
        meaningful_changes = {"date": date, "before": [], "after": []}
        all_keys = set(initial_slot_state.keys()) | set(final_slot_state.keys())
        
        for key in all_keys:
            initial_item = initial_slot_state.get(key)
            final_item = final_slot_state.get(key)
            if initial_item != final_item:
                slot_name, is_upgrade = key
                meaningful_changes["before"].append({"slotName": slot_name, "isUpgradeInfo": is_upgrade, "itemId": initial_item})
                meaningful_changes["after"].append({"slotName": slot_name, "isUpgradeInfo": is_upgrade, "itemId": final_item})

        if meaningful_changes["before"]:
             cleaned_history.append(meaningful_changes)

    return cleaned_history[-30:]

# --- 신규 DPS 계산 엔드포인트 ---
@app.route("/dps", methods=["POST"])
async def get_dps():
    """
    클라이언트로부터 server, characterName 및 계산 옵션을 받아
    dmgCalc 모듈을 사용하여 DPS를 계산하고 결과를 반환합니다.
    """
    if CharacterAnalyzer is None:
        return jsonify({"error": "DPS 분석 모듈(dmgCalc.py)이 로드되지 않았습니다."}), 500

    data = request.json
    server = data.get("server")
    character_name = data.get("characterName")
    
    cleansing_cdr = data.get("cleansing_cdr", True)
    weapon_cdr = data.get("weapon_cdr", True)
    average_set_dmg = data.get("average_set_dmg", False)

    if not server or not character_name:
        return jsonify({"error": "server와 characterName은 필수 입력 항목입니다."}), 400

    async with aiohttp.ClientSession() as session:
        character_id = await async_get_character_id(session, server, character_name)
        if not character_id:
            return jsonify({"error": f"캐릭터 '{character_name}'를(을) 찾을 수 없습니다."}), 404

        analyzer = CharacterAnalyzer(
            api_key=API_KEY, server=server, character_id=character_id,
            cleansing_cdr=cleansing_cdr, weapon_cdr=weapon_cdr,
            average_set_dmg=average_set_dmg
        )
        
        results = await analyzer.run_analysis(session)

    if "error" in results:
        return jsonify(results), 500

    return jsonify(results)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
