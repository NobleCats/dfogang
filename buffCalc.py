import asyncio
import aiohttp
import re
import json
import os
from buff_tables import (
    BUFF_TABLES, common_1a_table, common_3a_table,
    msader_aura_table, common_aura_table
)

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
            if attempt < retries - 1: await asyncio.sleep(0.5)
            else: return None
    return None

# --- 상수 정의 ---
SKILL_NAMES = {
    "M_SADER": {"main": "Divine Invocation", "1a": "Apocalypse", "3a": "Final Judgment", "aura": "Aura of Conviction"},
    "F_SADER": {"main": "Valor Blessing", "1a": "Crux of Victoria", "3a": "Laus di Angelus", "aura": "Pious Passion"},
    "ENCHANTRESS": {"main": "Forbidden Curse", "1a": "Marionette", "3a": "Curtain Call", "aura": "Petite Diablo"},
    "MUSE": {"main": "Lovely Tempo", "1a": "On the Stage", "3a": "Finale: Special Story", "aura": "Celebrity"},
}
SADER_JOB_MAP = {
    "92d1c40f5e486e3aa4fae8db283d1fd3": {"ba2ae3598c3af10c26562e073bc92060": "M_SADER"},
    "2ae47d662a9b18848c5e314966765bd7": {"ba2ae3598c3af10c26562e073bc92060": "F_SADER"},
    "fc067d0781f1d01ef8f0b215440bac6d": {"5dff544828c42d8fc109f2f747d50c7f": "ENCHANTRESS"},
    "dbbdf2dd28072b26f22b77454d665f21": {"ba2ae3598c3af10c26562e073bc92060": "MUSE"},
}
FORMULA_CONSTANTS = {
    "Valor Blessing":  {"c": 665, "X": 4350, "Y": 3500, "Z": 0.000379}, "Divine Invocation": {"c": 665, "X": 4350, "Y": 3500, "Z": 0.000379},
    "Forbidden Curse": {"c": 665, "X": 4350, "Y": 3500, "Z": 0.000379}, "Lovely Tempo":    {"c": 665, "X": 4350, "Y": 3500, "Z": 0.000379},
    "Apocalypse":      {"c": 750, "X": 5250, "Y": 5000, "Z": 0.000025}, "Crux of Victoria":{"c": 750, "X": 5250, "Y": 5000, "Z": 0.000025},
    "Marionette":      {"c": 750, "X": 5250, "Y": 5000, "Z": 0.000025}, "On the Stage":    {"c": 750, "X": 5250, "Y": 5000, "Z": 0.000025},
}

def _get_stats_from_single_item(item_obj, item_details_cache):
    """단일 아이템(장비, 아바타, 크리쳐 등)의 스탯 및 버프력 기여도를 계산합니다."""
    if not item_obj or not item_obj.get("itemId"):
        return {"Intelligence": 0, "Spirit": 0, "Stamina": 0, "Buff Power": 0}

    item_id = item_obj.get("itemId")
    item_details = item_details_cache.get(item_id, {})
    item_stats_to_sum = []

    item_stats_to_sum.extend(item_obj.get("itemStatus", []))
    if not item_obj.get("itemStatus"): item_stats_to_sum.extend(item_details.get("itemStatus", []))
    item_stats_to_sum.extend(item_obj.get("enchant", {}).get("status", []))
    
    # emblem 리스트가 None일 경우를 대비하여 'or []' 추가
    for emblem in item_obj.get("emblems") or []:
        if not emblem: continue
        emblem_details = item_details_cache.get(emblem.get("itemId"), {})
        if emblem_details:
            item_stats_to_sum.extend(emblem_details.get("itemStatus", []))

    item_contribution = {"Intelligence": 0, "Spirit": 0, "Stamina": 0, "Buff Power": 0}
    for stat in item_stats_to_sum:
        name = stat.get("name", "")
        
        # [핵심 수정] value를 안전하게 정수(int)로 변환합니다.
        try:
            value = int(stat.get("value", 0))
        except (ValueError, TypeError):
            # 만약 값이 숫자로 변환될 수 없는 문자열이면, 해당 스탯은 건너뜁니다.
            continue
        
        # 이제 value는 항상 정수이므로 안전하게 계산 가능합니다.
        if "Buff Power" in name: item_contribution["Buff Power"] += value
        elif "All Stats" in name:
            item_contribution["Intelligence"] += value
            item_contribution["Spirit"] += value
            item_contribution["Stamina"] += value
        elif "Intelligence" in name: item_contribution["Intelligence"] += value
        elif "Spirit" in name: item_contribution["Spirit"] += value
        elif "Vitality" in name: item_contribution["Stamina"] += value
        


class BufferAnalyzer:
    def __init__(self, api_key, server, character_id):
        self.API_KEY, self.BASE_URL, self.CHARACTER_ID = api_key, f"https://api.dfoneople.com/df/servers/{server}", character_id
        self.job_code, self.item_details_cache = None, {}

    def _parse_skill_lv_bonuses(self, gear_set, character_job_id, parsing_for):
        skill_lv_bonuses = {"main": 0, "1a": 0, "3a": 0, "aura": 0}
        all_items = (gear_set.get("equipment") or []) + (gear_set.get("avatar") or [])
        if gear_set.get("creature"): all_items.append(gear_set.get("creature"))

        skill_name_to_type = {v.lower(): k for k, v in SKILL_NAMES[self.job_code].items()}

        for item in all_items:
            if not item: continue
            item_name, item_slot = item.get("itemName", "Unknown Item"), item.get("slotName")
            full_item_details = self.item_details_cache.get(item.get("itemId"), {})

            if item_slot == "Title":
                if full_item_details.get("fame", 0) >= 849 and '1a' in parsing_for: skill_lv_bonuses["1a"] += 2
                if "Phantom City" in item_name:
                    if 'main' in parsing_for: skill_lv_bonuses["main"] += 1
                    if '1a' in parsing_for: skill_lv_bonuses["1a"] += 1
                    if 'aura' in parsing_for: skill_lv_bonuses["aura"] += 1

            for r_skill_source in [full_item_details.get("itemReinforceSkill", []), full_item_details.get("itemBuff", {}).get("reinforceSkill", [])]:
                if not r_skill_source: continue
                for r_skill_group in r_skill_source:
                    if r_skill_group.get("jobId") is None or r_skill_group.get("jobId") == character_job_id:
                        for range_info in r_skill_group.get("levelRange", []):
                            min_lvl, max_lvl, bonus = range_info.get("minLevel", 0), range_info.get("maxLevel", 0), range_info.get("value", 0)
                            if bonus > 0:
                                if 'main' in parsing_for and min_lvl <= 30 <= max_lvl: skill_lv_bonuses["main"] += bonus
                                if '1a' in parsing_for and min_lvl <= 50 <= max_lvl: skill_lv_bonuses["1a"] += bonus
                                if 'aura' in parsing_for and min_lvl <= 48 <= max_lvl: skill_lv_bonuses["aura"] += bonus
                                if '3a' in parsing_for and min_lvl <= 100 <= max_lvl: skill_lv_bonuses["3a"] += bonus
        return skill_lv_bonuses

    def _calculate_buff(self, skill_name_key, skill_level, calculated_stats, first_awakening_buff=None):
        if not self.job_code: return {}
        skill_name, (stat, buff_power) = SKILL_NAMES[self.job_code][skill_name_key], (calculated_stats.get("stat_value", 0), calculated_stats.get("buff_power", 0))
        base_result = {"applied_stat_name": calculated_stats.get("stat_name"), "applied_stat_value": calculated_stats.get("stat_value")}

        if skill_name_key == "aura":
            table = msader_aura_table if self.job_code == "M_SADER" else common_aura_table
            base_result.update({"stat_bonus": table.get(skill_level, {}).get("stat", 0)})
        elif skill_name_key == "1a":
            consts, table = FORMULA_CONSTANTS.get(skill_name), common_1a_table
            coeffs = table.get(skill_level)
            if coeffs and consts:
                multiplier = (((stat + consts["X"]) / (consts["c"] + 1)) * (buff_power + consts["Y"]) * consts["Z"])
                base_result.update({"stat_bonus": round(coeffs["stat"] * multiplier)})
        elif skill_name_key == "3a":
            percent_increase = common_3a_table.get(skill_level, {}).get("percent", 0)
            base_result.update({"increase_percent": percent_increase})
            if first_awakening_buff and 'stat_bonus' in first_awakening_buff:
                base_result["stat_bonus"] = round(first_awakening_buff['stat_bonus'] * (percent_increase / 100))
        elif skill_name_key == "main":
            consts, table = FORMULA_CONSTANTS.get(skill_name), BUFF_TABLES[self.job_code]
            coeffs = table.get(skill_level)
            if coeffs and consts:
                multiplier = (((stat + consts["X"]) / (consts["c"] + 1)) * (buff_power + consts["Y"]) * consts["Z"])
                base_result.update({"stat_bonus": round(coeffs["stat"] * multiplier), "atk_bonus": round(coeffs["atk"] * multiplier)})
        return base_result

    # [수정] run_buff_power_analysis 함수에 NoneType 방어 코드 추가
    async def run_buff_power_analysis(self, session):
        endpoints = {
            "profile": f"/characters/{self.CHARACTER_ID}", "status": f"/characters/{self.CHARACTER_ID}/status",
            "skills": f"/characters/{self.CHARACTER_ID}/skill/style",
            "current_equipment": f"/characters/{self.CHARACTER_ID}/equip/equipment", "current_avatar": f"/characters/{self.CHARACTER_ID}/equip/avatar", "current_creature": f"/characters/{self.CHARACTER_ID}/equip/creature",
            "buff_equipment": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/equipment", "buff_avatar": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/avatar", "buff_creature": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/creature"
        }
        tasks = {name: fetch_json(session, f"{self.BASE_URL}{path}", self.API_KEY) for name, path in endpoints.items()}
        api_data = await asyncio.gather(*tasks.values())
        data = dict(zip(tasks.keys(), api_data))

        profile = data.get("profile")
        if not profile: return {"error": "Can not load the character information."}
        character_job_id = profile.get("jobId")
        self.job_code = SADER_JOB_MAP.get(character_job_id, {}).get(profile.get("jobGrowId"))
        if not self.job_code: return {"error": "Not a sader."}

        item_ids_to_fetch = set()
        sources_to_cache = [
            data.get("current_equipment", {}).get("equipment"), data.get("buff_equipment", {}).get("equipment"),
            data.get("current_avatar", {}).get("avatar"), data.get("buff_avatar", {}).get("avatar")
        ]
        creature_list = [data.get("current_creature", {}).get("creature"), data.get("buff_creature", {}).get("creature")]
        if creature_list[0]: sources_to_cache.append([creature_list[0]])
        if creature_list[1]: sources_to_cache.append([creature_list[1]])

        for source in sources_to_cache:
            if not source: continue
            for item in source:
                if not item: continue
                if item.get("itemId"): item_ids_to_fetch.add(item["itemId"])
                for emblem in item.get("emblems") or []:
                    if emblem and emblem.get("itemId"): item_ids_to_fetch.add(emblem["itemId"])
                for artifact in item.get("artifact") or []:
                    if artifact and artifact.get("itemId"): item_ids_to_fetch.add(artifact["itemId"])

        item_tasks = [fetch_json(session, f"https://api.dfoneople.com/df/items/{item_id}", self.API_KEY) for item_id in item_ids_to_fetch]
        self.item_details_cache = {res['itemId']: res for res in await asyncio.gather(*item_tasks) if res and 'itemId' in res}

        total_char_stats = {"Intelligence": 0, "Spirit": 0, "Stamina": 0, "Buff Power": 0}
        status_list = data.get("status", {}).get("status", [])
        if status_list:
            known_stats = set()
            for s in status_list:
                name, value = s.get("name"), s.get("value", 0)
                if name == "Intelligence" and name not in known_stats: total_char_stats["Intelligence"] = value; known_stats.add(name)
                elif name == "Spirit" and name not in known_stats: total_char_stats["Spirit"] = value; known_stats.add(name)
                elif name == "Vitality" and "Stamina" not in known_stats: total_char_stats["Stamina"] = value; known_stats.add("Stamina")
                elif name == "Buff Power" and name not in known_stats: total_char_stats["Buff Power"] = value; known_stats.add(name)

        final_buffs = {}
        job_skills = SKILL_NAMES[self.job_code]
        all_skills_active = data.get("skills", {}).get("skill", {}).get("style", {}).get("active", [])
        skill_info = {s["name"]: s["level"] for s in all_skills_active if s} if all_skills_active else {}
        
        current_gear_set = {"equipment": data.get("current_equipment", {}).get("equipment"), "avatar": data.get("current_avatar", {}).get("avatar"), "creature": data.get("current_creature", {}).get("creature")}
        current_skill_bonuses = self._parse_skill_lv_bonuses(current_gear_set, character_job_id, ['1a', '3a', 'aura'])
        
        applicable_stat_name = next((n for n, jc in {"Intelligence": ["F_SADER", "ENCHANTRESS"], "Spirit": ["MUSE"], "Stamina": ["M_SADER"]}.items() if self.job_code in jc), "Unknown")
        if self.job_code == "M_SADER" and total_char_stats.get("Stamina", 0) < total_char_stats.get("Spirit", 0): applicable_stat_name = "Spirit"
        stats_for_current_gear = {"stat_value": total_char_stats.get(applicable_stat_name, 0), "stat_name": applicable_stat_name, "buff_power": total_char_stats.get("Buff Power", 0)}

        base_level_1a = skill_info.get(job_skills["1a"], 0); skill_level_1a = (base_level_1a + 1 if base_level_1a > 0 else 0) + current_skill_bonuses.get("1a", 0)
        final_buffs["1a"] = self._calculate_buff("1a", skill_level_1a, stats_for_current_gear)
        if final_buffs.get("1a"): final_buffs["1a"]["level"] = skill_level_1a
        
        # --- 스탯 보정 로직 ---
        adjusted_stats = total_char_stats.copy()
        current_eq = {item['slotId']: item for item in data.get("current_equipment", {}).get("equipment", []) if item}
        buff_eq = {item['slotId']: item for item in data.get("buff_equipment", {}).get("equipment", []) if item}
        
        for slot in set(current_eq.keys()) | set(buff_eq.keys()):
            curr_item, buff_item = current_eq.get(slot), buff_eq.get(slot)
            if (curr_item or buff_item) and (not curr_item or not buff_item or curr_item.get('itemId') != buff_item.get('itemId')):
                old_stats = _get_stats_from_single_item(curr_item, self.item_details_cache)
                new_stats = _get_stats_from_single_item(buff_item, self.item_details_cache)
                
                # [핵심 수정] 헬퍼 함수가 None을 반환하더라도 안전하게 처리합니다.
                if old_stats is None: old_stats = {}
                if new_stats is None: new_stats = {}
                
                for key in adjusted_stats:
                    adjusted_stats[key] = adjusted_stats.get(key, 0) - old_stats.get(key, 0) + new_stats.get(key, 0)
        
        current_avatar = data.get("current_avatar", {}).get("avatar") or []
        for item in current_avatar:
            stats_to_subtract = _get_stats_from_single_item(item, self.item_details_cache)
            if not stats_to_subtract: continue # 안전장치
            for key, value in stats_to_subtract.items(): adjusted_stats[key] -= value
        
        buff_avatar = data.get("buff_avatar", {}).get("avatar") or []
        for item in buff_avatar:
            stats_to_add = _get_stats_from_single_item(item, self.item_details_cache)
            if not stats_to_add: continue # 안전장치
            for key, value in stats_to_add.items(): adjusted_stats[key] += value

        # --- 최종 버프 계산 ---
        applicable_stat_name_main = next((n for n, jc in {"Intelligence": ["F_SADER", "ENCHANTRESS"], "Spirit": ["MUSE"], "Stamina": ["M_SADER"]}.items() if self.job_code in jc), "Unknown")
        if self.job_code == "M_SADER" and adjusted_stats.get("Stamina", 0) < adjusted_stats.get("Spirit", 0): applicable_stat_name_main = "Spirit"
        stats_for_main_buff = {"stat_value": adjusted_stats.get(applicable_stat_name_main, 0), "stat_name": applicable_stat_name_main, "buff_power": adjusted_stats.get("Buff Power", 0)}
        
        merged_buff_gear_set = {"equipment": list(buff_eq.values()), "avatar": data.get("buff_avatar", {}).get("avatar", []), "creature": data.get("buff_creature", {}).get("creature")}
        main_buff_skill_bonuses = self._parse_skill_lv_bonuses(merged_buff_gear_set, character_job_id, ['main'])
        
        main_buff_lv_api = data.get("buff_equipment", {}).get("skill", {}).get("buff", {}).get("skillInfo", {}).get("option", {}).get("level")
        main_buff_lv = main_buff_lv_api if main_buff_lv_api is not None else skill_info.get(job_skills["main"], 0) + main_buff_skill_bonuses.get("main", 0)
        
        final_buffs["main"] = self._calculate_buff("main", main_buff_lv, stats_for_main_buff)
        if final_buffs.get("main"): final_buffs["main"]["level"] = main_buff_lv
        
        return {"characterName": profile["characterName"], "jobName": profile["jobName"], "buffs": final_buffs}
