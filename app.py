# app.py (Modified)

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

# [NEW] buffCalc.py에서 BufferAnalyzer 클래스를 임포트합니다.
try:
    from buffCalc import BufferAnalyzer
except ImportError:
    print("오류: buffCalc.py 파일을 찾을 수 없습니다. app.py와 같은 폴더에 있는지 확인해주세요.")
    BufferAnalyzer = None

# --- 기본 설정 ---
app = Flask(__name__)
CORS(app) # 모든 도메인에서의 요청을 허용

API_KEY = os.environ.get('DFO_API_KEY', 'sRngDaw09CPuVYcpzfL1VG5F8ozrWnQQ')
BASE_URL = "https://api.dfoneople.com/df"
DATA_DIR = "datas"

# [NEW] 버퍼 스킬 이름 목록
BUFFER_SKILLS = ["Divine Invocation", "Valor Blessing", "Forbidden Curse", "Lovely Tempo"]

async def async_get_buff_power(session, server, character_id):
    analyzer = BufferAnalyzer(API_KEY, server, character_id)
    return await analyzer.run_buff_power_analysis(session)

# --- 비동기 API 헬퍼 함수 ---
async def fetch_json(session, url):
    headers = {
        'User-Agent': 'DFO-History-App/1.0 (https://api-dfohistory.duckdns.org)'
    }
    retries = 3
    for attempt in range(retries):
        try:
            if 'apikey=' not in url:
                separator = '?' if '?' not in url else '&'
                url += f"{separator}apikey={API_KEY}"

            # [MODIFIED] session.get 호출에 headers=headers 추가
            async with session.get(url, headers=headers, timeout=10) as response:
                response.raise_for_status()
                return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            print(f"API 요청 실패 (시도 {attempt + 1}/{retries}): {url}, 오류: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(0.5)
            else:
                return None
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

# [NEW] 버프 스킬 정보를 가져오는 비동기 함수
async def async_get_buff_skill(session, server, character_id):
    url = f"{BASE_URL}/servers/{server}/characters/{character_id}/skill/buff/equip/equipment?apikey={API_KEY}"
    return await fetch_json(session, url)

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
    
@app.route("/update_character_cache", methods=["POST"])
async def update_character_cache_route():
    data = request.json
    server = data.get("server")
    character_id = data.get("characterId")

    if not server or not character_id:
        return jsonify({"error": "server or characterId is null"}), 400

    async with aiohttp.ClientSession() as session:
        # create_or_update_profile_cache 함수 호출
        updated_profile = await create_or_update_profile_cache(session, server, character_id)
        if not updated_profile:
            return jsonify({"error": "Failed to update character cache."}), 500
        return jsonify({"status": "success", "profile": updated_profile})

async def get_character_card_data(session, server, character_id, average_set_dmg):
    """단일 캐릭터의 장비 정보와 DPS 정보를 비동기적으로 함께 가져옵니다."""
    try:
        equipment_task = async_get_equipment(session, server, character_id)
        # [MODIFIED] weapon_cdr 기본값을 false로 설정
        analyzer = CharacterAnalyzer(
            api_key=API_KEY, server=server, character_id=character_id,
            cleansing_cdr=True, weapon_cdr=False, average_set_dmg=average_set_dmg
        )
        dps_task = analyzer.run_analysis_for_all_dps(session)

        # 두 태스크를 동시에 실행
        equip_data, dps_results = await asyncio.gather(equipment_task, dps_task)

        if not equip_data:
            return None

        # 기존 장비 정보 처리 로직
        set_info_list = equip_data.get("setItemInfo")
        if set_info_list and isinstance(set_info_list, list) and len(set_info_list) > 0:
            set_info = set_info_list[0]
        else:
            set_info = {}

        # DPS 결과에서 dps 값 추출
        dps_value = dps_results.get("dps") if dps_results and "error" not in dps_results else None

        # [NEW] 버퍼 여부 판별
        is_buffer = False
        buff_skill_data = await async_get_buff_skill(session, server, character_id)
        if buff_skill_data and buff_skill_data.get("skill", {}).get("buff", {}).get("skillInfo", {}).get("name"):
            skill_name = buff_skill_data["skill"]["buff"]["skillInfo"]["name"]
            if any(buffer_skill in skill_name for buffer_skill in BUFFER_SKILLS):
                is_buffer = True

        # [NEW] 버퍼일 경우 버프력 계산
        buff_power_data = None
        if is_buffer and BufferAnalyzer:
            buffer_analyzer = BufferAnalyzer(API_KEY, server, character_id)
            buff_power_data = await buffer_analyzer.run_buff_power_analysis(session)
            # 여기서는 캐시에서 가져오는 것이 아니므로, 직접 계산된 값을 사용
            dps_value = buff_power_data.get("total_buff_score") # 버퍼일 경우 DPS 대신 버프력 사용

        # 최종 결과 조합
        return {
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
            "serverId": server,
            "dps": dps_value, # 버퍼일 경우 버프력, 아닐 경우 DPS
            "is_buffer": is_buffer # [NEW] is_buffer 추가
        }
    except Exception as e:
        print(f"Error processing character {character_id}: {e}")
        return None
    
@app.route("/search", methods=["POST"])
async def search():
    data = request.json
    server, name = data.get("server"), data.get("name")
    average_set_dmg = data.get("average_set_dmg", False)

    async with aiohttp.ClientSession() as session:
        characters_summary = await async_search_characters(session, server, name)
        if not characters_summary:
            return jsonify({"results": []})

        tasks = []
        for char_summary in characters_summary:
            tasks.append(
                asyncio.create_task(
                    _process_character_for_search( # [MODIFIED] profile_task 등은 _process_character_for_search 내부에서 처리
                        session, server, char_summary, average_set_dmg
                    )
                )
            )

        results = await asyncio.gather(*tasks)
        final_result = [res for res in results if res is not None]

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

@app.route("/buff_power", methods=["POST"])
async def buff_power():
    if BufferAnalyzer is None:
        return jsonify({"error": "Buff analysis module (buffCalc.py) is not loaded."}), 500

    data = request.json
    server = data.get("server")
    character_id = data.get("characterId") # Use characterId directly for buffCalc

    if not server or not character_id:
        return jsonify({"error": "server와 characterId는 필수 입력 항목입니다."}), 400

    async with aiohttp.ClientSession() as session:
        buff_results = await async_get_buff_power(session, server, character_id)
        if not buff_results or "error" in buff_results:
            return jsonify(buff_results or {"error": "버프 계산에 실패했습니다."}), 500
        return jsonify(buff_results)



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
async def search_explorer():
    try:
        data = request.get_json()
        servers = ["cain", "siroco"]
        explorer_name = data.get("name")
        if not explorer_name:
            return jsonify({"results": []})

        final_result = []
        for serverId in servers:
            base_path = Path(DATA_DIR) / serverId / explorer_name
            if not base_path.exists() or not base_path.is_dir():
                continue

            for char_dir in base_path.iterdir():
                if not char_dir.is_dir():
                    continue

                profile_path = char_dir / "profile.json"
                if profile_path.exists():
                    try:
                        with open(profile_path, "r", encoding="utf-8") as f:
                            profile_data = json.load(f)
                            final_result.append(profile_data)
                    except json.JSONDecodeError:
                        print(f"Warning: Could not decode profile.json for {char_dir.name}")
                        continue

        return jsonify({"results": final_result})

    except Exception as e:
        print(f"[💥] Unhandled exception in /search_explorer: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500


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

@app.route("/dps", methods=["POST"])
async def get_dps():
    if CharacterAnalyzer is None:
        return jsonify({"error": "DPS 분석 모듈(dmgCalc.py)이 로드되지 않았습니다."}), 500

    data = request.json
    server = data.get("server")
    character_name = data.get("characterName")

    # 클라이언트가 요청한 옵션
    average_set_dmg = data.get("average_set_dmg", False)

    if not server or not character_name:
        return jsonify({"error": "server와 characterName은 필수 입력 항목입니다."}), 400

    async with aiohttp.ClientSession() as session:
        character_id = await async_get_character_id(session, server, character_name)
        if not character_id:
            return jsonify({"error": f"캐릭터 '{character_name}'를(을) 찾을 수 없습니다."}), 404

        # 1. 새 함수를 호출하여 모든 DPS 결과와 최신 정보를 가져옵니다.
        analyzer = CharacterAnalyzer(API_KEY, server, character_id)
        all_results = await analyzer.run_analysis_for_all_dps(session)

        # [MODIFIED] 백그라운드에서 캐시를 업데이트하는 로직 제거
        # await create_or_update_profile_cache(session, server, character_id)

        # 3. 클라이언트가 요청한 옵션에 맞는 DPS 결과를 선택하여 반환합니다.
        if average_set_dmg:
            results_to_return = all_results.get("normalized", {})
        else:
            results_to_return = all_results.get("normal", {})
        
        # [NEW] full_results도 함께 반환하여 프론트엔드에서 캐시 업데이트에 사용하도록 함
        results_to_return["full_dps_data"] = all_results 

    if not results_to_return or "error" in results_to_return:
        return jsonify(results_to_return or {"error": "DPS 계산에 실패했습니다."}), 500

    return jsonify(results_to_return)

# [NEW] 버프 스킬 정보를 제공하는 엔드포인트
@app.route("/buff_skill", methods=["POST"])
async def buff_skill():
    data = request.json
    server = data.get("server")
    character_id = data.get("characterId")

    if not server or not character_id:
        return jsonify({"error": "server와 characterId는 필수 입력 항목입니다."}), 400

    async with aiohttp.ClientSession() as session:
        buff_skill_data = await async_get_buff_skill(session, server, character_id)
        if not buff_skill_data:
            return jsonify({"error": "Failed to fetch buff skill data"}), 500
        return jsonify(buff_skill_data)

# app.py 파일에 이 함수 전체를 추가해주세요.
# CharacterAnalyzer, Path, json, datetime 등이 import 되어 있는지 확인하세요.
async def create_or_update_profile_cache(
    session, server, character_id, profile_data, equipment_data,
    is_buffer=False, dps_data=None, total_buff_score=None
):
    """
    캐릭터의 프로필 캐시 파일을 생성하거나 업데이트합니다.
    이 함수는 이미 가져오고/계산된 데이터를 기반으로 동작합니다.
    """
    if not profile_data or not equipment_data:
        print(f"Error: Missing profile_data or equipment_data for cache update for {character_id}")
        return None

    adventure_name = profile_data.get("adventureName")
    if not adventure_name:
        print(f"Error: Missing adventureName for cache update for {character_id}")
        return None

    # 세트 아이템 정보를 추출합니다.
    set_info = {}
    if equipment_data and equipment_data.get("setItemInfo"):
        set_info_list = equipment_data["setItemInfo"]
        if set_info_list and isinstance(set_info_list, list) and len(set_info_list) > 0:
            set_info_data = set_info_list[0]
            set_info = {
                "setItemName": set_info_data.get("setItemName", ""),
                "setItemRarityName": set_info_data.get("setItemRarityName", ""),
                "setPoint": set_info_data.get("active", {}).get("setPoint", {}).get("current", 0)
            }

    # 캐시 파일에 저장할 최종 JSON 데이터를 구성합니다.
    cache_content = {
        "characterId": profile_data.get("characterId"),
        "characterName": profile_data.get("characterName"),
        "adventureName": profile_data.get("adventureName"),
        "jobName": profile_data.get("jobName"),
        "jobGrowName": profile_data.get("jobGrowName"),
        "fame": profile_data.get("fame"),
        "level": profile_data.get("level"),
        "serverId": server,
        **set_info,
        "dps": {
            "normal": dps_data.get("normal") if dps_data else None,
            "normalized": dps_data.get("normalized") if dps_data else None
        },
        "is_buffer": is_buffer,
        "total_buff_score": total_buff_score,
        "last_updated": datetime.datetime.utcnow().isoformat() + "Z"
    }

    # 구성된 데이터를 profile.json 파일로 저장합니다.
    char_dir = Path(DATA_DIR) / server / adventure_name / character_id
    char_dir.mkdir(parents=True, exist_ok=True)
    profile_path = char_dir / "profile.json"
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(cache_content, f, ensure_ascii=False, indent=2)

    return cache_content
@app.route("/update_profile_cache_backend", methods=["POST"])
async def update_profile_cache_backend():
    data = request.json
    server = data.get("server")
    character_id = data.get("characterId")
    profile_data_from_frontend = data.get("profileData")
    equipment_data_from_frontend = data.get("equipmentData")
    is_buffer = data.get("isBuffer", False)
    dps_data_from_frontend = data.get("dpsData")
    total_buff_score_from_frontend = data.get("totalBuffScore")

    if not all([server, character_id, profile_data_from_frontend, equipment_data_from_frontend]):
        return jsonify({"error": "Missing required data for cache update."}), 400

    async with aiohttp.ClientSession() as session:
        updated_profile = await create_or_update_profile_cache(
            session, server, character_id, profile_data_from_frontend, equipment_data_from_frontend,
            is_buffer=is_buffer, dps_data=dps_data_from_frontend, total_buff_score=total_buff_score_from_frontend
        )
        if not updated_profile:
            return jsonify({"error": "Failed to update profile cache."}), 500
        return jsonify({"status": "success", "profile": updated_profile})

async def _process_character_for_search(session, server, char_summary_data, average_set_dmg): # [MODIFIED] character_id 대신 char_summary_data 직접 전달
    character_id = char_summary_data['characterId']
    # [NEW] adventureName은 profile_data에서만 가져올 수 있으므로, 먼저 profile을 캐시에서 확인하거나 API 호출
    # searchCharacters API는 adventureName을 직접 제공하지 않으므로, profile_data를 가져와야 합니다.
    profile_data_initial = await async_get_profile(session, server, character_id)
    if not profile_data_initial:
        return None
    adventure_name = profile_data_initial.get("adventureName")
    if not adventure_name:
        return None

    char_dir = Path(DATA_DIR) / server / adventure_name / character_id
    profile_path = char_dir / "profile.json"

    # [NEW] 캐시 파일이 존재하면 읽어서 반환
    if profile_path.exists():
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                # cached_data에 dps 또는 total_buff_score가 없거나 업데이트가 필요한 경우
                # (예: average_set_dmg 옵션 변경 또는 오래된 캐시)
                # 여기서는 간단히 캐시가 있으면 사용하도록 함.
                # 필요에 따라 캐시 만료 로직 (예: 'last_updated' 기반) 추가 가능
                return cached_data
        except json.JSONDecodeError:
            print(f"Warning: Could not decode profile.json for {character_id}. Recalculating.")
            # JSON 디코딩 실패 시 아래 API 호출 로직으로 넘어감

    # [MODIFIED] 캐시가 없거나 유효하지 않으면 API 호출하여 계산 및 캐시 생성
    # profile_task, equipment_task, buff_skill_task는 여기서 직접 생성
    profile_task = asyncio.create_task(async_get_profile(session, server, character_id))
    equipment_task = asyncio.create_task(async_get_equipment(session, server, character_id))
    buff_skill_task = asyncio.create_task(async_get_buff_skill(session, server, character_id))

    profile_data, equipment_data, buff_skill_data = await asyncio.gather(
        profile_task, equipment_task, buff_skill_task
    )

    if not profile_data or not equipment_data:
        return None

    # is_buffer 판별
    is_buffer = False
    if buff_skill_data and buff_skill_data.get("skill", {}).get("buff", {}).get("skillInfo", {}).get("name"):
        skill_name = buff_skill_data["skill"]["buff"]["skillInfo"]["name"]
        if any(buffer_skill in skill_name for buffer_skill in BUFFER_SKILLS):
            is_buffer = True

    # DPS 또는 Buff Score 계산
    normal_dps = None
    normalized_dps = None
    total_buff_score = None
    full_dps_data = None # 캐시 업데이트를 위해 전체 DPS 데이터를 저장

    if is_buffer:
        buff_analyzer = BufferAnalyzer(API_KEY, server, character_id)
        buff_results = await buff_analyzer.run_buff_power_analysis(session)
        if buff_results and "total_buff_score" in buff_results:
            total_buff_score = buff_results["total_buff_score"]
    else:
        analyzer = CharacterAnalyzer(API_KEY, server, character_id)
        all_dps_results = await analyzer.run_analysis_for_all_dps(session)
        if "error" not in all_dps_results:
            normal_dps = all_dps_results.get("normal", {}).get("dps")
            normalized_dps = all_dps_results.get("normalized", {}).get("dps")
            full_dps_data = all_dps_results # 전체 DPS 데이터를 캐시 저장용으로 보존

    # 캐시 업데이트 (API 호출 후)
    await create_or_update_profile_cache(
        session, server, character_id, profile_data, equipment_data,
        is_buffer=is_buffer,
        dps_data={"normal": normal_dps, "normalized": normalized_dps}, # 간소화된 DPS 데이터 전달
        total_buff_score=total_buff_score
    )

    # 검색 결과 카드에 필요한 정보 반환 (profile.json의 내용과 유사)
    set_info = {}
    if equipment_data.get("setItemInfo"):
        set_info_list = equipment_data["setItemInfo"]
        if set_info_list and isinstance(set_info_list, list) and len(set_info_list) > 0:
            set_info_data = set_info_list[0]
            set_info = {
                "setItemName": set_info_data.get("setItemName", ""),
                "setItemRarityName": set_info_data.get("setItemRarityName", ""),
                "setPoint": set_info_data.get("active", {}).get("setPoint", {}).get("current", 0)
            }

    return {
        "characterId": profile_data.get("characterId"),
        "characterName": profile_data.get("characterName"),
        "adventureName": profile_data.get("adventureName"),
        "jobName": profile_data.get("jobName"),
        "jobGrowName": profile_data.get("jobGrowName"),
        "fame": profile_data.get("fame"),
        "level": profile_data.get("level"),
        "serverId": server,
        **set_info,
        "dps": { "normal": normal_dps, "normalized": normalized_dps },
        "is_buffer": is_buffer,
        "total_buff_score": total_buff_score,
        "last_updated": datetime.datetime.utcnow().isoformat() + "Z"
    }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)