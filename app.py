import asyncio
import aiohttp
from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
from collections import defaultdict
from pathlib import Path
import os
import json

# 동시 요청을 100개로 제한하는 세마포어 생성
SEMAPHORE = asyncio.Semaphore(100)

async def run_dps_with_semaphore(analyzer, session):
    async with SEMAPHORE:
        # 이 블록 안의 코드는 동시에 최대 100개만 실행됩니다.
        return await analyzer.run_analysis(session)

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
        dps_task = run_dps_with_semaphore(analyzer, session)

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
            "dps": dps_value
        }
    except Exception as e:
        print(f"Error processing character {character_id}: {e}")
        return None

@app.route("/search", methods=["POST"])
async def search():
    data = request.json
    server, name = data.get("server"), data.get("name")

    async with aiohttp.ClientSession() as session:
        characters = await async_search_characters(session, server, name)
        if not characters:
            return jsonify({"results": []})

        tasks = []
        for char in characters:
            character_id = char["characterId"]
            adventure_name = char["adventureName"] # 검색 결과에서 모험단 이름 가져오기
            
            # profile.json 경로 설정
            profile_path = Path(DATA_DIR) / server / adventure_name / character_id / "profile.json"
            
            if profile_path.exists():
                # 캐시가 존재하면 파일 읽기
                with open(profile_path, "r", encoding="utf-8") as f:
                    tasks.append(asyncio.sleep(0, result=json.load(f))) # 비동기 작업처럼 만들기
            else:
                # 캐시가 없으면 생성 작업 추가
                tasks.append(create_or_update_profile_cache(session, server, character_id))

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
        average_set_dmg = data.get("average_set_dmg", False)

        # 1단계: 로컬 파일 시스템에서 조회할 캐릭터 목록 수집
        characters_to_process = []
        for serverId in servers:
            base_path = Path(f"datas/{serverId}/{explorer_name}")
            if not base_path.exists(): continue
            for char_dir in base_path.iterdir():
                if not char_dir.is_dir(): continue
                equipment_path = char_dir / "equipment.json"
                if not equipment_path.exists(): continue
                
                with open(equipment_path, encoding="utf-8") as f:
                    equip_data = json.load(f)

                set_info_list = equip_data.get("setItemInfo")
                set_info = {}
                if set_info_list and isinstance(set_info_list, list) and len(set_info_list) > 0:
                    set_info = set_info_list[0]

                characters_to_process.append({
                    "base_data": {
                        "characterId": char_dir.name, "characterName": equip_data.get("characterName", ""),
                        "jobName": equip_data.get("jobName", ""), "jobGrowName": equip_data.get("jobGrowName", ""),
                        "adventureName": equip_data.get("adventureName", ""), "fame": equip_data.get("fame", 0),
                        "level": equip_data.get("level", 0), "setItemName": set_info.get("setItemName", ""),
                        "setItemRarityName": set_info.get("setItemRarityName", ""),
                        "setPoint": set_info.get("active", {}).get("setPoint", {}).get("current", 0),
                        "serverId": serverId
                    },
                    "characterId": char_dir.name, "serverId": serverId
                })

        if not characters_to_process:
            return jsonify({"results": []})

        # 2단계: 수집된 모든 캐릭터의 DPS를 병렬로 계산 (오류 처리 강화)
        async with aiohttp.ClientSession() as session:
            tasks = []
            for char_info in characters_to_process:
                # [MODIFIED] weapon_cdr 기본값을 false로 설정
                analyzer = CharacterAnalyzer(
                    api_key=API_KEY,
                    server=char_info["serverId"],
                    character_id=char_info["characterId"],
                    cleansing_cdr=True, weapon_cdr=False, average_set_dmg=average_set_dmg
                )
                tasks.append(run_dps_with_semaphore(analyzer, session))
            
            dps_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 3단계: 기본 캐릭터 데이터에 계산된 DPS 결과 결합
        final_result = []
        for i, char_info in enumerate(characters_to_process):
            dps_data = dps_results[i]
            
            # 개별 태스크의 실패 여부 확인
            if isinstance(dps_data, Exception):
                print(f"[❌] DPS calculation for {char_info['characterId']} failed with an exception: {dps_data}")
                dps_value = None
            else:
                dps_value = dps_data.get("dps") if dps_data and "error" not in dps_data else None
            
            char_info["base_data"]["dps"] = dps_value
            final_result.append(char_info["base_data"])

        return jsonify({"results": final_result})

    except Exception as e:
        # 이 함수 전체에서 발생하는 예외를 처리하여 서버가 다운되는 것을 방지합니다.
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

        # 2. 백그라운드에서 캐시를 업데이트합니다.
        # (별도 태스크로 분리하거나, 여기서 동기적으로 처리)
        await create_or_update_profile_cache(session, server, character_id)

        # 3. 클라이언트가 요청한 옵션에 맞는 DPS 결과를 선택하여 반환합니다.
        if average_set_dmg:
            results_to_return = all_results.get("normalized", {})
        else:
            results_to_return = all_results.get("normal", {})
            
    if not results_to_return or "error" in results_to_return:
        return jsonify(results_to_return or {"error": "DPS 계산에 실패했습니다."}), 500

    return jsonify(results_to_return)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

async def create_or_update_profile_cache(session, server, character_id):
    """캐릭터의 프로필 정보를 API에서 가져와 profile.json 캐시 파일을 생성하거나 업데이트합니다."""
    profile_data = await async_get_profile(session, server, character_id)
    if not profile_data:
        return None

    # CharacterAnalyzer를 한 번만 생성하고 한 번만 실행합니다.
    analyzer = CharacterAnalyzer(API_KEY, server, character_id)
    all_dps_results = await analyzer.run_analysis_for_all_dps(session)

    if "error" in all_dps_results:
        return None # 에러 발생 시 캐시 생성 중단

    # 결과에서 DPS 값과 장비 정보 추출
    normal_dps = all_dps_results.get("normal", {}).get("dps")
    normalized_dps = all_dps_results.get("normalized", {}).get("dps")
    equip_data = all_dps_results.get("equipment_data")

    # 세트 정보 추출
    set_info = {}
    if equip_data and equip_data.get("setItemInfo"):
        set_info_data = equip_data["setItemInfo"][0]
        set_info = {
            "setItemName": set_info_data.get("setItemName", ""),
            "setItemRarityName": set_info_data.get("setItemRarityName", ""),
            "setPoint": set_info_data.get("active", {}).get("setPoint", {}).get("current", 0)
        }

    # profile.json에 저장할 최종 데이터
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
            "normal": normal_dps,
            "normalized": normalized_dps
        },
        "last_updated": datetime.datetime.utcnow().isoformat() + "Z"
    }

    # 파일 저장
    adventure_name = profile_data.get("adventureName")
    char_dir = Path(DATA_DIR) / server / adventure_name / character_id
    char_dir.mkdir(parents=True, exist_ok=True)
    profile_path = char_dir / "profile.json"
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(cache_content, f, ensure_ascii=False, indent=2)

    return cache_content

