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
import itertools

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
    
try:
    with open('DFO_API_KEY', 'r') as f:
        # 파일의 첫 줄만 읽고, 쉼표로 구분하여 키 리스트 생성
        api_keys_str = f.readline().strip()
        API_KEYS = [key.strip() for key in api_keys_str.split(',')]
except FileNotFoundError:
    print("오류: DFO_API_KEY 파일을 찾을 수 없습니다.")
    API_KEYS = ['sRngDaw09CPuVYcpzfL1VG5F8ozrWnQQ']

if not API_KEYS:
    raise ValueError("오류: DFO_API_KEY 파일에 유효한 키가 없습니다.")

key_cycler = itertools.cycle(API_KEYS)

def get_next_api_key():
    """순환하며 다음 API 키를 반환합니다."""
    return next(key_cycler)

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
    """주어진 URL로 비동기 GET 요청을 보내고 JSON 응답을 반환합니다. (API 키 순환 적용)"""
    headers = {
        'User-Agent': 'DFO-History-App/1.0 (https://api-dfohistory.duckdns.org)'
    }
    retries = 3
    for attempt in range(retries):
        try:
            # 요청마다 다음 키를 순서대로 가져옵니다.
            current_api_key = get_next_api_key()

            if 'apikey=' in url:
                import re
                # 이미 apikey가 있다면 교체
                url_with_key = re.sub(r'apikey=[^&]*', f'apikey={current_api_key}', url)
            else:
                # apikey가 없다면 추가
                separator = '?' if '?' not in url else '&'
                url_with_key = f"{url}{separator}apikey={current_api_key}"

            async with session.get(url_with_key, headers=headers, timeout=10) as response:
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

# app.py

@app.route("/search", methods=["POST"])
async def search():
    data = request.json
    server, name = data.get("server"), data.get("name")

    async with aiohttp.ClientSession() as session:
        # 1. Neople API로 캐릭터 기본 정보 목록을 가져옵니다. (여기엔 adventureName이 없습니다.)
        characters_summary = await async_search_characters(session, server, name)
        if not characters_summary:
            return jsonify({"results": []})

        # 2. 받아온 캐릭터 목록 각각의 상세 프로필을 비동기적으로 모두 조회하여 adventureName을 얻습니다.
        profile_tasks = [async_get_profile(session, server, char['characterId']) for char in characters_summary]
        full_profiles = await asyncio.gather(*profile_tasks)

        tasks = []
        for profile in full_profiles:
            # 프로필 조회가 실패했거나 adventureName이 없는 경우 건너뜁니다.
            if not profile or not profile.get("adventureName"):
                continue

            # 비동기 처리를 위한 내부 헬퍼 함수
            async def process_character(p):
                character_id = p["characterId"]
                adventure_name = p["adventureName"]

                # 3. 이제 adventureName을 사용하여 캐시 파일 경로를 안전하게 만들 수 있습니다.
                profile_path = Path(DATA_DIR) / server / adventure_name / character_id / "profile.json"

                if profile_path.exists():
                    # 캐시 파일이 있으면 읽어서 반환
                    with open(profile_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                else:
                    # 캐시 파일이 없으면 새로 생성
                    return await create_or_update_profile_cache(session, server, character_id)

            tasks.append(process_character(profile))

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
        
        # [수정] 버퍼 정보 조회 시에도 캐시를 업데이트하도록 함수 호출 추가
        await create_or_update_profile_cache(session, server, character_id)
        
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

# app.py 의 기존 /search_explorer 함수를 아래 코드로 교체합니다.

@app.route("/search_explorer", methods=["POST"])
async def search_explorer():
    try:
        data = request.get_json()
        servers = ["cain", "siroco"]
        explorer_name = data.get("name")
        if not explorer_name:
            return jsonify({"results": []})

        # 실시간 DPS 계산 대신, 저장된 profile.json 캐시를 읽어옵니다.
        final_result = []
        for serverId in servers:
            base_path = Path(DATA_DIR) / serverId / explorer_name
            if not base_path.exists() or not base_path.is_dir():
                continue

            # 모험단 폴더 내의 각 캐릭터 폴더를 순회합니다.
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
                        # JSON 파일이 손상된 경우를 대비한 예외 처리
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

    # [수정] 클라이언트가 요청한 모든 옵션을 읽어옵니다.
    average_set_dmg = data.get("average_set_dmg", False)
    cleansing_cdr = data.get("cleansing_cdr", True) # 기본값은 프론트엔드와 일치시키는 것이 좋습니다.
    weapon_cdr = data.get("weapon_cdr", False)

    if not server or not character_name:
        return jsonify({"error": "server와 characterName은 필수 입력 항목입니다."}), 400

    async with aiohttp.ClientSession() as session:
        character_id = await async_get_character_id(session, server, character_name)
        if not character_id:
            return jsonify({"error": f"캐릭터 '{character_name}'를(을) 찾을 수 없습니다."}), 404

        # 1. 새 함수를 호출하여 모든 DPS 결과와 최신 정보를 가져옵니다.
        # [수정] 읽어온 모든 옵션을 CharacterAnalyzer 생성자에 전달합니다.
        analyzer = CharacterAnalyzer(
            api_key=API_KEY,
            server=server,
            character_id=character_id,
            cleansing_cdr=cleansing_cdr,

            weapon_cdr=weapon_cdr,
            average_set_dmg=average_set_dmg # 이 값은 run_analysis_for_all_dps 내부에서 오버라이드되지만, 명시적으로 전달
        )
        all_results = await analyzer.run_analysis_for_all_dps(session)

        # 2. 백그라운드에서 캐시를 업데이트합니다.
        await create_or_update_profile_cache(session, server, character_id)

        # 3. 클라이언트가 요청한 옵션에 맞는 DPS 결과를 선택하여 반환합니다.
        if average_set_dmg:
            results_to_return = all_results.get("normalized", {})
        else:
            results_to_return = all_results.get("normal", {})

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
async def create_or_update_profile_cache(session, server, character_id):
    """캐릭터의 프로필 정보를 API에서 가져와 profile.json 캐시 파일을 생성하거나 업데이트합니다."""
    # 상세 프로필 정보를 가져옵니다.
    profile_data = await async_get_profile(session, server, character_id)
    if not profile_data:
        return None

    # [NEW] 버퍼 여부 판별
    is_buffer = False
    total_buff_score = None # 기본값
    buff_skill_data = await async_get_buff_skill(session, server, character_id)
    
    skill_name = None
    if buff_skill_data:
        skill = buff_skill_data.get("skill")
        if skill and skill.get("buff") and skill.get("buff").get("skillInfo"):
            skill_name = skill.get("buff").get("skillInfo").get("name")

    if skill_name and any(buffer_skill in skill_name for buffer_skill in BUFFER_SKILLS):
        is_buffer = True
        # 버퍼일 경우 버프 능력치 계산
        buff_analyzer = BufferAnalyzer(API_KEY, server, character_id)
        buff_results = await buff_analyzer.run_buff_power_analysis(session)
        if buff_results and "total_buff_score" in buff_results:
            total_buff_score = buff_results["total_buff_score"]


    normal_dps = None
    normalized_dps = None
    equip_data = None

    if not is_buffer: # [MODIFIED] 버퍼가 아닐 때만 DPS 계산
        analyzer = CharacterAnalyzer(API_KEY, server, character_id)
        all_dps_results = await analyzer.run_analysis_for_all_dps(session)

        if "error" not in all_dps_results:
            normal_dps = all_dps_results.get("normal", {}).get("dps")
            normalized_dps = all_dps_results.get("normalized", {}).get("dps")
            equip_data = all_dps_results.get("equipment_data")
    else: # [NEW] 버퍼일 경우 장비 정보는 buffCalc에서 가져오지 않으므로, 여기서 가져옴
        equip_data = await async_get_equipment(session, server, character_id)



    # 세트 아이템 정보를 추출합니다.
    equip_data = await async_get_equipment(session, server, character_id) # Equipment data needed for setItemInfo
    set_info = {}
    if equip_data and equip_data.get("setItemInfo"):
        set_info_list = equip_data["setItemInfo"]
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
        "dps": { # 버퍼일 경우 None이 될 수 있음
            "normal": normal_dps,
            "normalized": normalized_dps
        },
        "is_buffer": is_buffer,
        "total_buff_score": total_buff_score, # [NEW] total_buff_score 추가
        "last_updated": datetime.datetime.utcnow().isoformat() + "Z"
    }

    # 구성된 데이터를 profile.json 파일로 저장합니다.
    adventure_name = profile_data.get("adventureName")
    char_dir = Path(DATA_DIR) / server / adventure_name / character_id
    char_dir.mkdir(parents=True, exist_ok=True)
    profile_path = char_dir / "profile.json"
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(cache_content, f, ensure_ascii=False, indent=2)

    return cache_content

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)