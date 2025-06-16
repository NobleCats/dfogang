import asyncio
import aiohttp
import re
import json
import os

# --- 유틸리티 함수 (기존과 동일) ---
async def fetch_json(session, url, api_key):
    headers = {'User-Agent': 'DFO-History-App/1.0 (https://api-dfohistory.duckdns.org)'}
    retries = 3
    for attempt in range(retries):
        try:
            if 'apikey=' not in url:
                separator = '?' if '?' not in url else '&'
                url += f"{separator}apikey={api_key}"
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

# --- 상수 정의 ---
# 스킬 이름 상수
SKILL_NAMES = {
    "M_SADER": {"main": "Divine Invocation", "1a": "Apocalypse", "3a": "The Day of Judgment", "aura": "Guardian's Blessing"},
    "F_SADER": {"main": "Valor Blessing", "1a": "Crux of Victoria", "3a": "Laus di Angelus", "aura": "Guardian's Blessing"},
    "ENCHANTRESS": {"main": "Forbidden Curse", "1a": "Marionette", "3a": "The Little Witch's Whimsy", "aura": "First Aid of Love"},
    "MUSE": {"main": "Lovely Tempo", "1a": "On the Stage", "3a": "FINALE: Special Story", "aura": "Ad-lib"},
}

# 직업 ID - 직업 코드 매핑
JOB_ID_TO_CODE = {
    "d1b9435b94e0944517625577549414e9": "M_SADER",
    "26a3934e889417de2b32454634281c60": "F_SADER",
    "5d21752b57f8648e1eda3f1a4e15ec4c": "ENCHANTRESS",
    "dbbdf2dd28072b26f22b77454d665f21": "MUSE",
}

# 계산 공식 상수
FORMULA_CONSTANTS = {
    "Valor Blessing":  {"c": 620, "X": 4348, "Y": 3488, "Z": 0.000357},
    "Divine Invocation": {"c": 620, "X": 4348, "Y": 3488, "Z": 0.000357}, # 여크루와 동일 계수 사용
    "Forbidden Curse": {"c": 665, "X": 4350, "Y": 3500, "Z": 0.000379},
    "Lovely Tempo":    {"c": 665, "X": 4350, "Y": 3500, "Z": 0.000379}, # 인챈과 동일 계수 사용 (가정)
    "Apocalypse":      {"c": 750, "X": 5250, "Y": 5000, "Z": 0.000025},
    "Crux of Victoria":{"c": 750, "X": 5250, "Y": 5000, "Z": 0.000025},
    "Marionette":      {"c": 750, "X": 5250, "Y": 5000, "Z": 0.000025},
    "On the Stage":    {"c": 750, "X": 5250, "Y": 5000, "Z": 0.000025},
}


ENCHANTRESS_BUFF_TABLE = {
    1: {"atk": 34, "stat": 131},
    2: {"atk": 35, "stat": 140},
    3: {"atk": 37, "stat": 149},
    4: {"atk": 38, "stat": 158},
    5: {"atk": 39, "stat": 167},
    6: {"atk": 41, "stat": 175},
    7: {"atk": 42, "stat": 184},
    8: {"atk": 43, "stat": 193},
    9: {"atk": 45, "stat": 202},
    10: {"atk": 46, "stat": 211},
    11: {"atk": 47, "stat": 220},
    12: {"atk": 49, "stat": 229},
    13: {"atk": 50, "stat": 238},
    14: {"atk": 51, "stat": 247},
    15: {"atk": 53, "stat": 256},
    16: {"atk": 54, "stat": 264},
    17: {"atk": 55, "stat": 273},
    18: {"atk": 57, "stat": 282},
    19: {"atk": 58, "stat": 291},
    20: {"atk": 60, "stat": 300},
    21: {"atk": 61, "stat": 309},
    22: {"atk": 62, "stat": 318},
    23: {"atk": 64, "stat": 327},
    24: {"atk": 65, "stat": 336},
    25: {"atk": 66, "stat": 345},
    26: {"atk": 68, "stat": 353},
    27: {"atk": 69, "stat": 362},
    28: {"atk": 70, "stat": 371},
    29: {"atk": 72, "stat": 380},
    30: {"atk": 73, "stat": 389},
    31: {"atk": 74, "stat": 398},
    32: {"atk": 76, "stat": 407},
    33: {"atk": 77, "stat": 416},
    34: {"atk": 78, "stat": 425},
    35: {"atk": 80, "stat": 434},
    36: {"atk": 81, "stat": 442},
    37: {"atk": 82, "stat": 451},
    38: {"atk": 84, "stat": 460},
    39: {"atk": 85, "stat": 469},
    40: {"atk": 87, "stat": 478}
}
MUSE_BUFF_TABLE = {
    1: {"atk": 40, "stat": 162},
    2: {"atk": 42, "stat": 173},
    3: {"atk": 44, "stat": 186},
    4: {"atk": 46, "stat": 196},
    5: {"atk": 47, "stat": 207},
    6: {"atk": 49, "stat": 217},
    7: {"atk": 51, "stat": 227},
    8: {"atk": 52, "stat": 239},
    9: {"atk": 54, "stat": 249},
    10: {"atk": 55, "stat": 262},
    11: {"atk": 56, "stat": 272},
    12: {"atk": 58, "stat": 283},
    13: {"atk": 60, "stat": 295},
    14: {"atk": 61, "stat": 306},
    15: {"atk": 63, "stat": 318},
    16: {"atk": 64, "stat": 328},
    17: {"atk": 65, "stat": 338},
    18: {"atk": 67, "stat": 350},
    19: {"atk": 70, "stat": 360},
    20: {"atk": 72, "stat": 372},
    21: {"atk": 73, "stat": 382},
    22: {"atk": 74, "stat": 394},
    23: {"atk": 76, "stat": 406},
    24: {"atk": 78, "stat": 416},
    25: {"atk": 80, "stat": 428},
    26: {"atk": 82, "stat": 437},
    27: {"atk": 83, "stat": 448},
    28: {"atk": 84, "stat": 460},
    29: {"atk": 86, "stat": 471},
    30: {"atk": 88, "stat": 482},
    31: {"atk": 89, "stat": 493},
    32: {"atk": 92, "stat": 503},
    33: {"atk": 93, "stat": 516},
    34: {"atk": 94, "stat": 527},
    35: {"atk": 96, "stat": 539},
    36: {"atk": 98, "stat": 548},
    37: {"atk": 99, "stat": 559},
    38: {"atk": 101, "stat": 570},
    39: {"atk": 102, "stat": 581},
    40: {"atk": 104, "stat": 593}
}
MSADER_BUFF_TABLE = {
    1: {"atk": 41, "stat": 161},
    2: {"atk": 42, "stat": 171},
    3: {"atk": 44, "stat": 181},
    4: {"atk": 45, "stat": 193},
    5: {"atk": 46, "stat": 204},
    6: {"atk": 48, "stat": 214},
    7: {"atk": 50, "stat": 224},
    8: {"atk": 51, "stat": 236},
    9: {"atk": 53, "stat": 247},
    10: {"atk": 55, "stat": 258},
    11: {"atk": 56, "stat": 269},
    12: {"atk": 57, "stat": 279},
    13: {"atk": 59, "stat": 291},
    14: {"atk": 60, "stat": 301},
    15: {"atk": 62, "stat": 313},
    16: {"atk": 64, "stat": 322},
    17: {"atk": 65, "stat": 333},
    18: {"atk": 67, "stat": 345},
    19: {"atk": 69, "stat": 356},
    20: {"atk": 71, "stat": 366},
    21: {"atk": 72, "stat": 377},
    22: {"atk": 74, "stat": 389},
    23: {"atk": 76, "stat": 399},
    24: {"atk": 77, "stat": 410},
    25: {"atk": 79, "stat": 421},
    26: {"atk": 81, "stat": 431},
    27: {"atk": 81, "stat": 442},
    28: {"atk": 83, "stat": 454},
    29: {"atk": 85, "stat": 464},
    30: {"atk": 86, "stat": 474},
    31: {"atk": 88, "stat": 486},
    32: {"atk": 90, "stat": 497},
    33: {"atk": 91, "stat": 508},
    34: {"atk": 93, "stat": 518},
    35: {"atk": 94, "stat": 531},
    36: {"atk": 95, "stat": 540},
    37: {"atk": 97, "stat": 551},
    38: {"atk": 99, "stat": 562},
    39: {"atk": 100, "stat": 572},
    40: {"atk": 103, "stat": 584}
}
FSADER_BUFF_TABLE = {
    1: {"atk": 39, "stat": 154},
    2: {"atk": 41, "stat": 164},
    3: {"atk": 43, "stat": 176},
    4: {"atk": 44, "stat": 186},
    5: {"atk": 45, "stat": 197},
    6: {"atk": 47, "stat": 206},
    7: {"atk": 49, "stat": 216},
    8: {"atk": 50, "stat": 227},
    9: {"atk": 52, "stat": 237},
    10: {"atk": 53, "stat": 249},
    11: {"atk": 54, "stat": 259},
    12: {"atk": 56, "stat": 269},
    13: {"atk": 58, "stat": 280},
    14: {"atk": 59, "stat": 290},
    15: {"atk": 61, "stat": 302},
    16: {"atk": 62, "stat": 311},
    17: {"atk": 63, "stat": 321},
    18: {"atk": 65, "stat": 332},
    19: {"atk": 67, "stat": 342},
    20: {"atk": 69, "stat": 353},
    21: {"atk": 70, "stat": 363},
    22: {"atk": 71, "stat": 374},
    23: {"atk": 73, "stat": 385},
    24: {"atk": 75, "stat": 395},
    25: {"atk": 77, "stat": 406},
    26: {"atk": 79, "stat": 415},
    27: {"atk": 80, "stat": 425},
    28: {"atk": 81, "stat": 437},
    29: {"atk": 83, "stat": 447},
    30: {"atk": 85, "stat": 458},
    31: {"atk": 86, "stat": 468},
    32: {"atk": 88, "stat": 478},
    33: {"atk": 89, "stat": 489},
    34: {"atk": 90, "stat": 500},
    35: {"atk": 92, "stat": 511},
    36: {"atk": 94, "stat": 520},
    37: {"atk": 95, "stat": 530},
    38: {"atk": 97, "stat": 541},
    39: {"atk": 98, "stat": 551},
    40: {"atk": 100, "stat": 563}
}

msader_aura_table = {
    1: {"stat": 40},
    2: {"stat": 48},
    3: {"stat": 58},
    4: {"stat": 67},
    5: {"stat": 77},
    6: {"stat": 87},
    7: {"stat": 98},
    8: {"stat": 109},
    9: {"stat": 120},
    10: {"stat": 133},
    11: {"stat": 144},
    12: {"stat": 157},
    13: {"stat": 171},
    14: {"stat": 184},
    15: {"stat": 198},
    16: {"stat": 212},
    17: {"stat": 226},
    18: {"stat": 242},
    19: {"stat": 258},
    20: {"stat": 273},
    21: {"stat": 290},
    22: {"stat": 306},
    23: {"stat": 323},
    24: {"stat": 341},
    25: {"stat": 359},
    26: {"stat": 378},
    27: {"stat": 397},
    28: {"stat": 416},
    29: {"stat": 436},
    30: {"stat": 456},
    31: {"stat": 476},
    32: {"stat": 498},
    33: {"stat": 518},
    34: {"stat": 541},
    35: {"stat": 562},
    36: {"stat": 586},
    37: {"stat": 609},
    38: {"stat": 632},
    39: {"stat": 654},
    40: {"stat": 678},
    41: {"stat": 702},
    42: {"stat": 726},
    43: {"stat": 750},
    44: {"stat": 774},
    45: {"stat": 798},
    46: {"stat": 823},
    47: {"stat": 848},
    48: {"stat": 873},
    49: {"stat": 898},
    50: {"stat": 923}
}
common_aura_table = {
    1: {"stat": 14},
    2: {"stat": 37},
    3: {"stat": 59},
    4: {"stat": 82},
    5: {"stat": 104},
    6: {"stat": 127},
    7: {"stat": 149},
    8: {"stat": 172},
    9: {"stat": 194},
    10: {"stat": 217},
    11: {"stat": 239},
    12: {"stat": 262},
    13: {"stat": 284},
    14: {"stat": 307},
    15: {"stat": 329},
    16: {"stat": 352},
    17: {"stat": 374},
    18: {"stat": 397},
    19: {"stat": 419},
    20: {"stat": 442},
    21: {"stat": 464},
    22: {"stat": 487},
    23: {"stat": 509},
    24: {"stat": 532},
    25: {"stat": 554},
    26: {"stat": 577},
    27: {"stat": 599},
    28: {"stat": 622},
    29: {"stat": 644},
    30: {"stat": 667},
    31: {"stat": 689},
    32: {"stat": 712},
    33: {"stat": 734},
    34: {"stat": 757},
    35: {"stat": 779},
    36: {"stat": 802},
    37: {"stat": 824},
    38: {"stat": 847},
    39: {"stat": 869},
    40: {"stat": 892},
    41: {"stat": 914},
    42: {"stat": 937},
    43: {"stat": 959},
    44: {"stat": 982},
    45: {"stat": 1004},
    46: {"stat": 1027},
    47: {"stat": 1049},
    48: {"stat": 1072},
    49: {"stat": 1094},
    50: {"stat": 1117}
}
common_1a_table = {
    1: {"stat": 43},
    2: {"stat": 57},
    3: {"stat": 74},
    4: {"stat": 91},
    5: {"stat": 111},
    6: {"stat": 131},
    7: {"stat": 153},
    8: {"stat": 176},
    9: {"stat": 201},
    10: {"stat": 228},
    11: {"stat": 255},
    12: {"stat": 284},
    13: {"stat": 315},
    14: {"stat": 346},
    15: {"stat": 379},
    16: {"stat": 414},
    17: {"stat": 449},
    18: {"stat": 487},
    19: {"stat": 526},
    20: {"stat": 567},
    21: {"stat": 608},
    22: {"stat": 651},
    23: {"stat": 696},
    24: {"stat": 741},
    25: {"stat": 789},
    26: {"stat": 838},
    27: {"stat": 888},
    28: {"stat": 939},
    29: {"stat": 993},
    30: {"stat": 1047},
    31: {"stat": 1103},
    32: {"stat": 1160},
    33: {"stat": 1219},
    34: {"stat": 1278},
    35: {"stat": 1340},
    36: {"stat": 1403},
    37: {"stat": 1467},
    38: {"stat": 1533},
    39: {"stat": 1600},
    40: {"stat": 1668},
    41: {"stat": 1736},
    42: {"stat": 1804},
    43: {"stat": 1872},
    44: {"stat": 1940},
    45: {"stat": 2008},
    46: {"stat": 2076},
    47: {"stat": 2144},
    48: {"stat": 2212},
    49: {"stat": 2280},
    50: {"stat": 2348},
}
common_3a_table = {
    1: {"percent": 109},
    2: {"percent": 110},
    3: {"percent": 111},
    4: {"percent": 112},
    5: {"percent": 113},
    6: {"percent": 114},
    7: {"percent": 115},
    8: {"percent": 116},
    9: {"percent": 117},
    10: {"percent": 118},
    11: {"percent": 119},
    12: {"percent": 120},
    13: {"percent": 121},
    14: {"percent": 122},
    15: {"percent": 123},
    16: {"percent": 124},
    17: {"percent": 125},
    18: {"percent": 126},
    19: {"percent": 127},
    20: {"percent": 128},
    21: {"percent": 129},
    22: {"percent": 130},
    23: {"percent": 131},
    24: {"percent": 132},
    25: {"percent": 133},
    26: {"percent": 134},
    27: {"percent": 135},
    28: {"percent": 136},
    29: {"percent": 137},
    30: {"percent": 138},
    31: {"percent": 139},
    32: {"percent": 140},
    33: {"percent": 141},
    34: {"percent": 142},
    35: {"percent": 143},
    36: {"percent": 144},
    37: {"percent": 145},
    38: {"percent": 146},
    39: {"percent": 147},
    40: {"percent": 148},
    41: {"percent": 149},
    42: {"percent": 150},
    43: {"percent": 151},
    44: {"percent": 152},
    45: {"percent": 153},
    46: {"percent": 154},
    47: {"percent": 155},
    48: {"percent": 156},
    49: {"percent": 157},
    50: {"percent": 158},
}


BUFF_TABLES = {
    "M_SADER": MSADER_BUFF_TABLE, "F_SADER": FSADER_BUFF_TABLE,
    "ENCHANTRESS": ENCHANTRESS_BUFF_TABLE, "MUSE": MUSE_BUFF_TABLE,
}

class BufferAnalyzer:
    def __init__(self, api_key, server, character_id):
        self.API_KEY = api_key
        self.BASE_URL = f"https://api.dfoneople.com/df/servers/{server}"
        self.CHARACTER_ID = character_id
        self.job_code = None
        self.item_details_cache = {}

    def _parse_stats_from_gear_set(self, gear_set, base_stats):
        """주어진 장비 세트와 기본 스탯을 바탕으로 총 스탯과 버프력을 계산합니다."""
        total_stat = base_stats.get("Intelligence", 0) if self.job_code in ["F_SADER", "ENCHANTRESS", "MUSE"] else base_stats.get("Spirit", 0)
        total_buff_power = 0
        skill_lv_bonuses = {}

        # 장비, 아바타, 크리쳐 아이템 목록을 하나로 합쳐서 처리
        all_items = gear_set.get("equipment", []) + gear_set.get("avatar", []) + gear_set.get("creature", [])
        
        for item in all_items:
            # 1. 아이템 자체 Status (버프력, 주스탯 등)
            for stat in item.get("itemStatus", []):
                name = stat.get("name", "")
                value = stat.get("value", 0)
                if "Buff Power" in name:
                    total_buff_power += value
                elif "Intelligence" in name or "Spirit" in name or "All Stats" in name:
                    total_stat += value
                # 스킬 레벨 증가 옵션 파싱 (예: "Lv. 30 All Skills +1")
                match = re.search(r"Lv\.(\d+).*?Skills\s*\+\s*(\d+)", name)
                if match:
                    level_range_start = int(match.group(1))
                    bonus_level = int(match.group(2))
                    # 이 레벨 범위에 메인 버프가 포함되는지 확인해야 함 (간략화)
                    # 여기서는 30레벨 스킬에만 적용된다고 가정
                    if 25 <= level_range_start <= 35:
                         skill_lv_bonuses["main"] = skill_lv_bonuses.get("main", 0) + bonus_level


            # 2. 마법부여, 튠, 융합옵션 등 추가 옵션
            # (이전 버전의 _parse_status_for_buff_power 와 _parse_explain_for_buff_power 로직을 여기에 통합/확장)
            for source in ["enchant", "tune", "fusionOption"]:
                options = item.get(source, {})
                # Status 파싱
                for stat in options.get("status", []):
                     if "Buff Power" in stat.get("name", ""): total_buff_power += stat.get("value", 0)

                # Explain 파싱 (융합옵션 등)
                for opt in options.get("options", []):
                     explain = opt.get("explainDetail", "")
                     match = re.search(r"Buff Power\s*\+\s*([\d,]+)", explain, re.IGNORECASE)
                     if match: total_buff_power += int(match.group(1).replace(',', ''))
        
        return {"stat": total_stat, "buff_power": total_buff_power, "skill_lv_bonuses": skill_lv_bonuses}

    def _calculate_buff(self, skill_name, skill_level, calculated_stats):
        """단일 버프 스킬의 최종 성능을 계산합니다."""
        if not self.job_code: return {}

        stat = calculated_stats.get("stat", 0)
        buff_power = calculated_stats.get("buff_power", 0)
        
        # 3차 각성 (단순 퍼센트 증가)
        if "3a" in skill_name:
            if skill_level in COMMON_3A_TABLE:
                return {"increase_percent": COMMON_3A_TABLE[skill_level]["percent"]}
            return {}

        # 오라 (단순 스탯 증가)
        if "aura" in skill_name:
            table = MSADER_AURA_TABLE if self.job_code == "M_SADER" else COMMON_AURA_TABLE
            if skill_level in table:
                return {"stat_bonus": table[skill_level]["stat"]}
            return {}

        # 1차 각성 (이미지 우하단 공식)
        if "1a" in skill_name:
            if skill_level not in COMMON_1A_TABLE: return {}
            c = FORMULA_CONSTANTS[skill_name].get("c", 750)
            X = FORMULA_CONSTANTS[skill_name].get("X", 5250)
            Y = FORMULA_CONSTANTS[skill_name].get("Y", 5000)
            Z = FORMULA_CONSTANTS[skill_name].get("Z", 0.000025)
            
            stat_increase = COMMON_1A_TABLE[skill_level]["stat"] * (((stat + X) / (c + 1)) * (buff_power + Y) * Z)
            return {"stat_bonus": round(stat_increase)}

        # 메인 버프 (이미지 좌하단/우상단 공식)
        if "main" in skill_name:
            table = BUFF_TABLES[self.job_code]
            if skill_level not in table: return {}
            
            constants = FORMULA_CONSTANTS[skill_name]
            level_coeffs = table[skill_level]
            
            # 힘/지능 증가량 계산
            stat_bonus = level_coeffs["stat"] * ( ( (stat + constants["X"]) / (constants["c"] + 1) ) * (buff_power + constants["Y"]) * constants["Z"] )
            
            # 공격력 증가량 계산 (물/마/독공) - 공식이 명확하지 않아 계수만 적용
            atk_bonus = level_coeffs["atk"]
            
            return {"stat_bonus": round(stat_bonus), "atk_bonus": atk_bonus}

        return {}

    async def run_buff_power_analysis(self, session):
        # 1. 모든 필요 API 데이터 병렬로 호출
        endpoints = {
            "profile": f"/characters/{self.CHARACTER_ID}",
            "status": f"/characters/{self.CHARACTER_ID}/status",
            "skills": f"/characters/{self.CHARACTER_ID}/skill/style",
            "current_gear": f"/characters/{self.CHARACTER_ID}/equip/equipment",
            "buff_gear": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/equipment",
            "buff_avatar": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/avatar",
            "buff_creature": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/creature",
        }
        tasks = {name: fetch_json(session, f"{self.BASE_URL}{path}", self.API_KEY) for name, path in endpoints.items()}
        api_data = await asyncio.gather(*tasks.values())
        data = dict(zip(tasks.keys(), api_data))

        if not data.get("profile"): return {"error": "캐릭터 정보를 불러올 수 없습니다."}

        self.job_code = JOB_ID_TO_CODE.get(data["profile"]["jobId"])
        if not self.job_code: return {"error": "버퍼 직업군이 아닙니다."}
        
        # 2. 버프 강화(스위칭)용 장비 세트 구성
        main_buff_gear_set = data["current_gear"].copy() # 현재 장비를 기본으로
        buff_enhancement_items = data["buff_gear"].get("equipment", []) + data["buff_avatar"].get("avatar", []) + data["buff_creature"].get("creature", [])
        
        # 버프 강화 장비가 있으면 현재 장비를 오버라이드
        # (구현 간소화를 위해 슬롯ID 기반의 복잡한 교체 대신, 두 장비 목록을 합치는 것으로 대체)
        # 정확한 구현을 위해서는 각 아이템의 slotId를 비교하여 교체해야 합니다.
        main_buff_gear_set["equipment"] = data["buff_gear"].get("equipment", [])
        main_buff_gear_set["avatar"] = data["buff_avatar"].get("avatar", [])
        main_buff_gear_set["creature"] = data["buff_creature"].get("creature", [])


        # 3. 스탯 계산
        base_stats = {s["name"]: s["value"] for s in data["status"]["status"]}
        stats_for_main_buff = self._parse_stats_from_gear_set(main_buff_gear_set, base_stats)
        stats_for_current_gear = self._parse_stats_from_gear_set(data["current_gear"], base_stats)

        # 4. 스킬 레벨 확인 및 최종 버프력 계산
        final_buffs = {}
        skill_info = {s["name"]: s["level"] for s in data["skills"]["skill"]["style"]["active"]}
        
        job_skills = SKILL_NAMES[self.job_code]
        
        # 메인 버프 계산
        main_buff_lv = skill_info.get(job_skills["main"], 0) + stats_for_main_buff["skill_lv_bonuses"].get("main", 0)
        final_buffs["main"] = self._calculate_buff(job_skills["main"], main_buff_lv, stats_for_main_buff)
        
        # 1각, 3각, 오라 계산
        for buff_type in ["1a", "3a", "aura"]:
            skill_name = job_skills[buff_type]
            skill_level = skill_info.get(skill_name, 0) # 1각/3각 등은 현재 장비의 스탯 보너스를 받아야 함 (간략화)
            final_buffs[buff_type] = self._calculate_buff(skill_name, skill_level, stats_for_current_gear)
        
        return {
            "characterName": data["profile"]["characterName"],
            "jobName": data["profile"]["jobName"],
            "buffs": final_buffs
        }


# --- 스크립트 직접 실행을 위한 테스트 코드 ---
async def main():
    parser = argparse.ArgumentParser(description="D&F 버퍼 캐릭터 버프력 분석기 v2")
    # ... (기존 main 함수와 동일하게 유지)
    
if __name__ == "__main__":
    import argparse
    # ... (기존과 동일)