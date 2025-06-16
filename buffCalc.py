import asyncio
import aiohttp
import re
import json
import os

# --- 유틸리티 함수 ---
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
SKILL_NAMES = {
    "M_SADER": {"main": "Divine Invocation", "1a": "Apocalypse", "3a": "Final Judgment", "aura": "Aura of Conviction"},
    "F_SADER": {"main": "Valor Blessing", "1a": "Crux of Victoria", "3a": "Laus di Angelus", "aura": "Pious Passion"},
    "ENCHANTRESS": {"main": "Forbidden Curse", "1a": "Marionette", "3a": "Curtain Call", "aura": "Petite Diablo"},
    "MUSE": {"main": "Lovely Tempo", "1a": "On the Stage", "3a": "Finale: Special Story", "aura": "Celebrity"},
}

JOB_ID_TO_CODE = {
    "ba2ae3598c3af10c26562e073bc92060": "M_SADER",
    "ba2ae3598c3af10c26562e073bc92060": "F_SADER",
    "5dff544828c42d8fc109f2f747d50c7f": "ENCHANTRESS",
    "ba2ae3598c3af10c26562e073bc92060": "MUSE",
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


FORMULA_CONSTANTS = {
    "Valor Blessing":  {"c": 665, "X": 4350, "Y": 3500, "Z": 0.000379},
    "Divine Invocation": {"c": 665, "X": 4350, "Y": 3500, "Z": 0.000379},
    "Forbidden Curse": {"c": 665, "X": 4350, "Y": 3500, "Z": 0.000379},
    "Lovely Tempo":    {"c": 665, "X": 4350, "Y": 3500, "Z": 0.000379},
    "Apocalypse":      {"c": 750, "X": 5250, "Y": 5000, "Z": 0.000025},
    "Crux of Victoria":{"c": 750, "X": 5250, "Y": 5000, "Z": 0.000025},
    "Marionette":      {"c": 750, "X": 5250, "Y": 5000, "Z": 0.000025},
    "On the Stage":    {"c": 750, "X": 5250, "Y": 5000, "Z": 0.000025},
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

    # buffCalc.py 파일의 _parse_stats_from_gear_set 함수를 아래 코드로 교체하세요.

    def _parse_stats_from_gear_set(self, gear_set, base_stats):
        stats = {
            "Intelligence": base_stats.get("Intelligence", 0),
            "Spirit": base_stats.get("Spirit", 0),
            "Stamina": base_stats.get("Stamina", 0)
        }
        total_buff_power = 0
        skill_lv_bonuses = {"main": 0, "1a": 0, "3a": 0, "aura": 0}

        all_items = gear_set.get("equipment", [])
        if gear_set.get("avatar"): all_items.extend(gear_set.get("avatar", []))
        if gear_set.get("creature"): all_items.append(gear_set["creature"])
        
        for item in all_items:
            if not item: continue
            
            all_statuses = item.get("itemStatus", [])
            if item.get("enchant"): all_statuses.extend(item["enchant"].get("status", []))
            if item.get("tune"): all_statuses.extend(item["tune"].get("status", []))
            
            for stat in all_statuses:
                name, value = stat.get("name", ""), stat.get("value", 0)
                if "Buff Power" in name: total_buff_power += value
                elif "Intelligence" in name: stats["Intelligence"] += value
                elif "Spirit" in name: stats["Spirit"] += value
                elif "Stamina" in name: stats["Stamina"] += value
                elif "All Stats" in name:
                    stats["Intelligence"] += value; stats["Spirit"] += value; stats["Stamina"] += value
            
            all_text_sources = []
            if item.get("itemExplainDetail"): all_text_sources.append(item["itemExplainDetail"])
            for stat in all_statuses: all_text_sources.append(stat.get("name", ""))
            if item.get("fusionOption"):
                for opt in item["fusionOption"].get("options", []):
                    all_text_sources.append(opt.get("explainDetail", ""))

            for text_block in all_text_sources:
                if not text_block: continue
                for line in text_block.split('\n'):
                    line_lower = line.lower()
                    
                    match = re.search(r"lv\.\s*(\d+)\s*(?:buff|active) skill levels\s*\+\s*(\d+)", line_lower)
                    if match:
                        lvl, bonus = int(match.group(1)), int(match.group(2));
                        if 25 <= lvl <= 35: skill_lv_bonuses["main"] += bonus
                        if 45 <= lvl <= 50: skill_lv_bonuses["1a"] += bonus
                        if 80 <= lvl <= 85: skill_lv_bonuses["aura"] += bonus
                        if 95 <= lvl <= 100: skill_lv_bonuses["3a"] += bonus
                        continue
                    
                    match = re.search(r"level\s*(\d+)-(\d+)\s*all skill\s*\+\s*(\d+)", line_lower)
                    if match:
                        start_lvl, end_lvl, bonus = int(match.group(1)), int(match.group(2)), int(match.group(3))
                        if start_lvl <= 30 <= end_lvl: skill_lv_bonuses["main"] += bonus
                        if start_lvl <= 50 <= end_lvl: skill_lv_bonuses["1a"] += bonus
                        if start_lvl <= 85 <= end_lvl: skill_lv_bonuses["aura"] += bonus
                        if start_lvl <= 100 <= end_lvl: skill_lv_bonuses["3a"] += bonus
                        continue
                    
                    match = re.search(r"lv\.(\d+)\s*skills\s*\+\s*(\d+)", line_lower)
                    if match:
                        lvl, bonus = int(match.group(1)), int(match.group(2))
                        if 25 <= lvl <= 35: skill_lv_bonuses["main"] += bonus
                        if 45 <= lvl <= 50: skill_lv_bonuses["1a"] += bonus
                        if 80 <= lvl <= 85: skill_lv_bonuses["aura"] += bonus
                        if 95 <= lvl <= 100: skill_lv_bonuses["3a"] += bonus

        applicable_stat_value = 0
        applicable_stat_name = ""
        if self.job_code in ["F_SADER", "ENCHANTRESS"]:
            applicable_stat_value = stats["Intelligence"]
            applicable_stat_name = "Intelligence"
        elif self.job_code == "MUSE":
            applicable_stat_value = stats["Spirit"]
            applicable_stat_name = "Spirit"
        elif self.job_code == "M_SADER":
            if stats["Stamina"] > stats["Spirit"]:
                applicable_stat_value = stats["Stamina"]
                applicable_stat_name = "Stamina"
            else:
                applicable_stat_value = stats["Spirit"]
                applicable_stat_name = "Spirit"
                
        return {
            "stat_value": applicable_stat_value, 
            "stat_name": applicable_stat_name, 
            "buff_power": total_buff_power, 
            "skill_lv_bonuses": skill_lv_bonuses
        }

    def _calculate_buff(self, skill_name_key, skill_level, calculated_stats, first_awakening_buff=None):
        if not self.job_code: return {}
        skill_name = SKILL_NAMES[self.job_code][skill_name_key]
        stat, buff_power = calculated_stats.get("stat_value", 0), calculated_stats.get("buff_power", 0)
        
        if skill_name_key == "3a":
            percent_increase = common_3a_table.get(skill_level, {}).get("percent", 0)
            if first_awakening_buff and 'stat_bonus' in first_awakening_buff:
                one_a_stat_bonus = first_awakening_buff['stat_bonus']
                three_a_stat_bonus = one_a_stat_bonus * (percent_increase / 100)
                return {"stat_bonus": round(three_a_stat_bonus)}
            else:
                return {"increase_percent": percent_increase}

        if skill_name_key == "aura":
            table = msader_aura_table if self.job_code == "M_SADER" else common_aura_table
            return {"stat_bonus": table.get(skill_level, {}).get("stat", 0)}

        if skill_name_key == "1a":
            coeffs = common_1a_table.get(skill_level)
            consts = FORMULA_CONSTANTS.get(skill_name)
            if not coeffs or not consts: return {}
            multiplier = (((stat + consts["X"]) / (consts["c"] + 1)) * (buff_power + consts["Y"]) * consts["Z"])
            stat_increase = coeffs["stat"] * multiplier
            return {"stat_bonus": round(stat_increase)}

        if skill_name_key == "main":
            coeffs = BUFF_TABLES[self.job_code].get(skill_level)
            consts = FORMULA_CONSTANTS.get(skill_name)
            if not coeffs or not consts: return {}
            multiplier = (((stat + consts["X"]) / (consts["c"] + 1)) * (buff_power + consts["Y"]) * consts["Z"])
            stat_bonus = coeffs["stat"] * multiplier
            atk_bonus = coeffs["atk"] * multiplier
            return {"stat_bonus": round(stat_bonus), "atk_bonus": round(atk_bonus)}
            
        return {}

    async def run_buff_power_analysis(self, session):
        """[개선됨] 최종 반환값에 계산에 사용된 기본 스탯 정보를 포함합니다."""
        endpoints = {"profile": f"/characters/{self.CHARACTER_ID}", "status": f"/characters/{self.CHARACTER_ID}/status", "skills": f"/characters/{self.CHARACTER_ID}/skill/style", "current_gear": f"/characters/{self.CHARACTER_ID}/equip/equipment", "current_avatar": f"/characters/{self.CHARACTER_ID}/equip/avatar", "current_creature": f"/characters/{self.CHARACTER_ID}/equip/creature", "buff_gear": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/equipment"}
        tasks = {name: fetch_json(session, f"{self.BASE_URL}{path}", self.API_KEY) for name, path in endpoints.items()}
        api_data = await asyncio.gather(*tasks.values())
        data = dict(zip(tasks.keys(), api_data))

        if not data.get("profile"): return {"error": "Can not load the character information."}
        self.job_code = JOB_ID_TO_CODE.get(data["profile"]["jobGrowId"])
        if not self.job_code: return {"error": "Not a sader."}

        current_gear_by_slot = {item['slotId']: item for item in data["current_gear"].get("equipment", [])}
        for item in data["buff_gear"].get("equipment", []):
            current_gear_by_slot[item['slotId']] = item
        
        buff_gear_set = { "equipment": list(current_gear_by_slot.values()), "avatar": data.get("current_avatar", {}).get("avatar", []), "creature": data.get("current_creature", {}).get("creature") }
        current_gear_set = {"equipment": data["current_gear"].get("equipment",[]), "avatar": data["current_avatar"].get("avatar",[]), "creature": data.get("current_creature", {}).get("creature")}

        base_stats = {s["name"]: s["value"] for s in data["status"]["status"]}
        stats_for_main_buff = self._parse_stats_from_gear_set(buff_gear_set, base_stats)
        stats_for_current_gear = self._parse_stats_from_gear_set(current_gear_set, base_stats)

        final_buffs = {}
        skill_info = {s["name"]: s["level"] for s in data["skills"]["skill"]["style"]["active"]}
        job_skills = SKILL_NAMES[self.job_code]
        
        main_buff_lv = skill_info.get(job_skills["main"], 0) + stats_for_main_buff["skill_lv_bonuses"].get("main", 0)
        final_buffs["main"] = self._calculate_buff("main", main_buff_lv, stats_for_main_buff)
        if final_buffs["main"]: final_buffs["main"]["level"] = main_buff_lv
        
        skill_level_1a = skill_info.get(job_skills["1a"], 0) + stats_for_current_gear["skill_lv_bonuses"].get("1a", 0)
        final_buffs["1a"] = self._calculate_buff("1a", skill_level_1a, stats_for_current_gear)
        if final_buffs["1a"]: final_buffs["1a"]["level"] = skill_level_1a

        skill_level_3a = skill_info.get(job_skills["3a"], 0) + stats_for_current_gear["skill_lv_bonuses"].get("3a", 0)
        final_buffs["3a"] = self._calculate_buff("3a", skill_level_3a, stats_for_current_gear, final_buffs["1a"])
        if final_buffs["3a"]: final_buffs["3a"]["level"] = skill_level_3a

        skill_level_aura = skill_info.get(job_skills["aura"], 0) + stats_for_current_gear["skill_lv_bonuses"].get("aura", 0)
        final_buffs["aura"] = self._calculate_buff("aura", skill_level_aura, stats_for_current_gear)
        if final_buffs["aura"]: final_buffs["aura"]["level"] = skill_level_aura
        
        # 계산에 사용된 스탯 정보를 요약해서 추가
        base_stat_info = {
            "name": stats_for_main_buff.get("stat_name"),
            "value": stats_for_main_buff.get("stat_value")
        }
        
        return {
            "characterName": data["profile"]["characterName"],
            "jobName": data["profile"]["jobName"],
            "buffs": final_buffs,
            "base_stat_info": base_stat_info
        }