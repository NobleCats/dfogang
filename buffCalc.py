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
    "2ae47d662a9b18848c5e314966762bd7": {"ba2ae3598c3af10c26562e073bc92060": "F_SADER"},
    "fc067d0781f1d01ef8f0b215440bac6d": {"5dff544828c42d8fc109f2f747d50c7f": "ENCHANTRESS"},
    "dbbdf2dd28072b26f22b77454d665f21": {"ba2ae3598c3af10c26562e073bc92060": "MUSE"},
}
FORMULA_CONSTANTS = {
    "Valor Blessing":  {"c": 665, "X": 4350, "Y": 3500, "Z": 0.000379}, "Divine Invocation": {"c": 665, "X": 4350, "Y": 3500, "Z": 0.000379},
    "Forbidden Curse": {"c": 665, "X": 4350, "Y": 3500, "Z": 0.000379}, "Lovely Tempo":    {"c": 665, "X": 4350, "Y": 3500, "Z": 0.000379},
    "Apocalypse":      {"c": 750, "X": 5250, "Y": 5000, "Z": 0.000025}, "Crux of Victoria":{"c": 750, "X": 5250, "Y": 5000, "Z": 0.000025},
    "Marionette":      {"c": 750, "X": 5250, "Y": 5000, "Z": 0.000025}, "On the Stage":    {"c": 750, "X": 5250, "Y": 5000, "Z": 0.000025},
}

class BufferAnalyzer:
    def __init__(self, api_key, server, character_id):
        self.API_KEY, self.BASE_URL, self.CHARACTER_ID = api_key, f"https://api.dfoneople.com/df/servers/{server}", character_id
        self.job_code, self.item_details_cache = None, {}
        self.character_job_id = None

    def _parse_stats_from_gear_set(self, gear_set, base_stats, character_job_id, parsing_for=['main', '1a', '3a', 'aura']):
        """[최종] 어떤 버프를 위해 파싱하는지(parsing_for)에 따라 필요한 스킬 옵션만 검사합니다."""
        stats = {
            "Intelligence": base_stats.get("Intelligence", 0),
            "Spirit": base_stats.get("Spirit", 0),
            "Vitality": base_stats.get("Vitality", 0)
        }
        total_buff_power, skill_lv_bonuses = 0, {"main": 0, "1a": 0, "3a": 0, "aura": 0}

        all_items = gear_set.get("equipment", [])
        if gear_set.get("avatar"): all_items.extend(gear_set.get("avatar", []))
        if gear_set.get("creature") and gear_set["creature"]: all_items.append(gear_set["creature"])

        skill_name_to_type = {v.lower(): k for k, v in SKILL_NAMES[self.job_code].items()}

        for item in all_items:
            if not item: continue
            item_name, item_slot = item.get("itemName", "Unknown Item"), item.get("slotName")
            full_item_details = self.item_details_cache.get(item.get("itemId"), {})

            # 칭호 하드코딩
            if item_slot == "Title":
                if full_item_details.get("fame", 0) >= 849 and '1a' in parsing_for:
                    skill_lv_bonuses["1a"] += 2
                if "Phantom City" in item_name:
                    if 'main' in parsing_for: skill_lv_bonuses["main"] += 1
                    if '1a' in parsing_for: skill_lv_bonuses["1a"] += 1
                    if 'aura' in parsing_for: skill_lv_bonuses["aura"] += 1

            # 모든 reinforceSkill 파싱
            for r_skill_source in [full_item_details.get("itemReinforceSkill", []), full_item_details.get("itemBuff", {}).get("reinforceSkill", [])]:
                for r_skill_group in r_skill_source:
                    if r_skill_group.get("jobId") is None or r_skill_group.get("jobId") == character_job_id:
                        for range_info in r_skill_group.get("levelRange", []):
                            min_lvl, max_lvl, bonus = range_info.get("minLevel", 0), range_info.get("maxLevel", 0), range_info.get("value", 0)
                            if bonus > 0:
                                if 'main' in parsing_for and min_lvl <= 30 <= max_lvl: skill_lv_bonuses["main"] += bonus
                                if '1a' in parsing_for and min_lvl <= 50 <= max_lvl: skill_lv_bonuses["1a"] += bonus
                                if 'aura' in parsing_for and min_lvl <= 48 <= max_lvl:
                                    skill_lv_bonuses["aura"] += bonus
                                if '3a' in parsing_for and min_lvl <= 100 <= max_lvl: skill_lv_bonuses["3a"] += bonus


            # Enchant reinforceSkill 파싱
            for r_skill_group in item.get("enchant", {}).get("reinforceSkill", []):
                for skill in r_skill_group.get("skills", []):
                    skill_name_lower = skill.get("name", "").lower()
                    if skill_name_lower in skill_name_to_type:
                        skill_type, bonus = skill_name_to_type[skill_name_lower], skill.get("value", 0)
                        if bonus > 0:
                            skill_lv_bonuses[skill_type] += bonus

            # 텍스트 기반 옵션 파싱
            text_sources = {"OptionAbility": item.get("optionAbility", ""), "ItemBuff Explain": full_item_details.get("itemBuff", {}).get("explain", "")}
            for emblem in item.get("emblems") or []: text_sources[f"Emblem({emblem.get('itemName')})"] = emblem.get("itemName", "")
            for origin, text_block in text_sources.items():
                if not text_block: continue
                for line in text_block.split('\n'):
                    line_lower = line.lower().strip()
                    if not line_lower: continue
                    match_name = re.search(r"(.+?)\s*skill lv\s*\+\s*(\d+)", line_lower)
                    match_level = re.search(r"lv\.\s*(\d+).*?skill(?: levels)?\s*\+\s*(\d+)", line_lower)
                    match_emblem = re.search(r"platinum emblem\s*\[(.+)\]", line_lower)
                    if match_name:
                        skill_name, bonus = match_name.group(1).strip(), int(match_name.group(2))
                        if skill_name in skill_name_to_type:
                            skill_type = skill_name_to_type[skill_name]
                            skill_lv_bonuses[skill_type] += bonus
                    elif match_level:
                        lvl, bonus = int(match_level.group(1)), int(match_level.group(2))
                        if 25 <= lvl <= 35: skill_lv_bonuses["main"] += bonus
                        if 45 <= lvl <= 50: skill_lv_bonuses["1a"] += bonus
                        if 80 <= lvl <= 85: skill_lv_bonuses["aura"] += bonus
                    elif match_emblem:
                        skill_name = match_emblem.group(1).strip()
                        if skill_name in skill_name_to_type:
                            skill_type, bonus = skill_name_to_type[skill_name], 1
                            skill_lv_bonuses[skill_type] += bonus

                # 기본 스탯 및 버프력 합산
            for stat in item.get("itemStatus", []) + item.get("enchant", {}).get("status", []):
                name, value = stat.get("name", ""), stat.get("value", 0)
                if "Buff Power" in name: total_buff_power += value
                elif "Intelligence" in name: stats["Intelligence"] += value
                elif "Spirit" in name: stats["Spirit"] += value
                elif "Vitality" in name: stats["Vitality"] += value
                elif "All Stats" in name: stats["Intelligence"] += value; stats["Spirit"] += value; stats["Vitality"] += value


        applicable_stat_value, applicable_stat_name = 0, ""
        if self.job_code in ["F_SADER", "ENCHANTRESS"]: applicable_stat_value, applicable_stat_name = stats["Intelligence"], "Intelligence"
        elif self.job_code == "MUSE": applicable_stat_value, applicable_stat_name = stats["Spirit"], "Spirit"
        elif self.job_code == "M_SADER": applicable_stat_value, applicable_stat_name = (stats["Vitality"], "Vitality") if stats["Vitality"] > stats["Spirit"] else (stats["Spirit"], "Spirit")

        # Include the full stats dictionary for detailed breakdown
        return { "stat_value": applicable_stat_value, "stat_name": applicable_stat_name, "buff_power": total_buff_power, "skill_lv_bonuses": skill_lv_bonuses, "stats_breakdown": stats }


    def _calculate_buff(self, skill_name_key, skill_level, calculated_stats, first_awakening_buff=None, aura_stat_bonus=0):
        if not self.job_code: return {}
        skill_name, (stat, buff_power) = SKILL_NAMES[self.job_code][skill_name_key], (calculated_stats.get("stat_value", 0), calculated_stats.get("buff_power", 0))

        # Apply aura_stat_bonus to the stat value for main, 1a, and 3a buffs
        if skill_name_key in ["main", "1a", "3a"]:
            print(f"DEBUG: Buff '{skill_name_key}' - Initial stat: {stat}, Aura stat bonus: {aura_stat_bonus}")
            stat += aura_stat_bonus
            print(f"DEBUG: Buff '{skill_name_key}' - Stat after adding aura bonus: {stat}")

        base_result = {
            "applied_stat_name": calculated_stats.get("stat_name"),
            "applied_stat_value": stat
        }

        if skill_name_key == "aura":
                table = msader_aura_table if self.job_code == "M_SADER" else common_aura_table
                stat_bonus = table.get(skill_level, {}).get("stat", 0)
                base_result.update({"stat_bonus": stat_bonus})
                return base_result
        if skill_name_key == "1a":
            consts, table = FORMULA_CONSTANTS.get(skill_name), common_1a_table
            coeffs = table.get(skill_level)
            if not coeffs or not consts: return {}
            multiplier = (((stat + consts["X"]) / (consts["c"] + 1)) * (buff_power + consts["Y"]) * consts["Z"])
            base_result.update({"stat_bonus": round(coeffs["stat"] * multiplier)})
            return base_result
        if skill_name_key == "3a":
            percent_increase = common_3a_table.get(skill_level, {}).get("percent", 0)
            base_result.update({"increase_percent": percent_increase})
            if first_awakening_buff and 'stat_bonus' in first_awakening_buff:
                base_result["stat_bonus"] = round(first_awakening_buff['stat_bonus'] * (percent_increase / 100))
            return base_result
        if skill_name_key == "main":
            consts, table = FORMULA_CONSTANTS.get(skill_name), BUFF_TABLES[self.job_code]
            coeffs = table.get(skill_level)
            if not coeffs or not consts: return {}
            multiplier = (((stat + consts["X"]) / (consts["c"] + 1)) * (buff_power + consts["Y"]) * consts["Z"])
            base_result.update({
                "stat_bonus": round(coeffs["stat"] * multiplier),
                "atk_bonus": round(coeffs["atk"] * multiplier)
            })
            return base_result
        return {}

    async def run_buff_power_analysis(self, session):
        endpoints = {
            "profile": f"/characters/{self.CHARACTER_ID}",
            "status": f"/characters/{self.CHARACTER_ID}/status",
            "skills": f"/characters/{self.CHARACTER_ID}/skill/style",
            "current_equipment": f"/characters/{self.CHARACTER_ID}/equip/equipment",
            "current_avatar": f"/characters/{self.CHARACTER_ID}/equip/avatar",
            "current_creature": f"/characters/{self.CHARACTER_ID}/equip/creature",
            "buff_equip_equipment": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/equipment" # Added new endpoint
        }
        tasks = {name: fetch_json(session, f"{self.BASE_URL}{path}", self.API_KEY) for name, path in endpoints.items()}
        api_data = await asyncio.gather(*tasks.values())
        data = dict(zip(tasks.keys(), api_data))

        profile = data.get("profile")
        if not profile: return {"error": "Can not load the character information."}
        character_job_id = profile.get("jobId")
        self.job_code = SADER_JOB_MAP.get(character_job_id, {}).get(profile.get("jobGrowId"))
        self.character_job_id = character_job_id
        if not self.job_code: return {"error": "Not a sader."}

        item_ids_to_fetch = set()

        current_equipment_data = data.get("current_equipment", {}).get("equipment", [])
        current_avatar_data = data.get("current_avatar", {}).get("avatar", [])

        temp_current_creature = data.get("current_creature", {}).get("creature")
        current_creature = None
        if isinstance(temp_current_creature, list) and temp_current_creature:
            current_creature = temp_current_creature[0]
        elif isinstance(temp_current_creature, dict):
            current_creature = temp_current_creature

        if current_creature is None:
            current_creature = []
        elif isinstance(current_creature, dict):
            current_creature = [current_creature]

        gear_sources = [
            current_equipment_data,
            current_avatar_data,
            current_creature
        ]

        for source in gear_sources:
            for item in source:
                if isinstance(item, dict) and item.get("itemId"):
                    item_ids_to_fetch.add(item["itemId"])
                    for artifact in item.get("artifact", []):
                        if isinstance(artifact, dict) and artifact.get("itemId"): item_ids_to_fetch.add(artifact["itemId"])

        item_tasks = [fetch_json(session, f"https://api.dfoneople.com/df/items/{item_id}", self.API_KEY) for item_id in item_ids_to_fetch]
        self.item_details_cache = {res['itemId']: res for res in await asyncio.gather(*item_tasks) if res and 'itemId' in res}


        if "status" not in data or not data["status"]:
            return {"error": "Character status data is not available."}

        base_stats_from_status_api = {}
        buff_power_from_status_api = 0
        buff_power_amp_from_status_api = 0

        if data.get("status") and data["status"].get("status"):
            for s in data["status"]["status"]:
                name = s.get("name")
                value = s.get("value", 0)
                if name in ["Intelligence", "Spirit", "Vitality"]:
                    if name in base_stats_from_status_api:
                        base_stats_from_status_api[name] = max(base_stats_from_status_api[name], value)
                    else:
                        base_stats_from_status_api[name] = value
                elif name == "Buff Power":
                    buff_power_from_status_api = value
                elif name == "Buff Power Amp.":
                    buff_power_amp_from_status_api = value

        # status API에서 받아온 직후의 스탯 값 로깅
        print(f"DEBUG: Base stats received from status API (includes equipment stats): {base_stats_from_status_api}")
        print(f"DEBUG: Buff Power from status API: {buff_power_from_status_api}")
        print(f"DEBUG: Buff Power Amp. from status API: {buff_power_amp_from_status_api}")

        # Calculate final buff power using the formula
        final_calculated_buff_power = buff_power_from_status_api * (1 + buff_power_amp_from_status_api * 0.01)
        print(f"DEBUG: Final calculated Buff Power: {final_calculated_buff_power}")


        all_skills = data.get("skills", {}).get("skill", {}).get("style", {}).get("active", []) + \
                     data.get("skills", {}).get("skill", {}).get("style", {}).get("passive", [])
        skill_info = {s["name"]: s["level"] for s in all_skills}
        job_skills = SKILL_NAMES[self.job_code]
        final_buffs = {}

        current_gear_set_for_calculation = {
            "equipment": current_equipment_data,
            "avatar": current_avatar_data,
            "creature": current_creature[0] if current_creature else None,
            "type": "Current"
        }

        # _parse_stats_from_gear_set는 스킬 레벨 보너스만 파싱하도록 변경
        # base_stats와 buff_power는 0으로 넘겨서 순수 장비 스탯만 계산
        # 그리고 _parse_stats_from_gear_set 내에서 total_buff_power 로직을 제거해야 합니다.
        # 즉, _parse_stats_from_gear_set는 오직 skill_lv_bonuses와 stats_breakdown (장비 자체의 스탯)만 반환하도록 합니다.
        parsed_stats_from_current_gear = self._parse_stats_from_gear_set(
            current_gear_set_for_calculation,
            {"Intelligence": 0, "Spirit": 0, "Vitality": 0}, # Pass 0 for base stats as status API provides combined stats
            character_job_id,
            parsing_for=['main', '1a', '3a', 'aura']
        )

        # Determine the applicable stat for all buffs based on base_stats_from_status_api
        applicable_stat_value = 0
        applicable_stat_name = ""
        if self.job_code in ["F_SADER", "ENCHANTRESS"]:
            applicable_stat_value = base_stats_from_status_api.get("Intelligence", 0)
            applicable_stat_name = "Intelligence"
        elif self.job_code == "MUSE":
            applicable_stat_value = base_stats_from_status_api.get("Spirit", 0)
            applicable_stat_name = "Spirit"
        elif self.job_code == "M_SADER":
            if base_stats_from_status_api.get("Vitality", 0) > base_stats_from_status_api.get("Spirit", 0):
                applicable_stat_value = base_stats_from_status_api.get("Vitality", 0)
                applicable_stat_name = "Vitality"
            else:
                applicable_stat_value = base_stats_from_status_api.get("Spirit", 0)
                applicable_stat_name = "Spirit"

        calculated_stats_for_all_buffs = {
            "stat_value": applicable_stat_value,
            "stat_name": applicable_stat_name,
            "buff_power": final_calculated_buff_power, # Use the calculated buff power
            "skill_lv_bonuses": parsed_stats_from_current_gear["skill_lv_bonuses"] # This already accumulates skill level bonuses from all gear
        }

        # Calculate Aura first
        base_level_aura = skill_info.get(job_skills["aura"], 0)
        bonus_level_aura = calculated_stats_for_all_buffs["skill_lv_bonuses"].get("aura", 0)
        skill_level_aura = base_level_aura + bonus_level_aura

        final_buffs["aura"] = self._calculate_buff("aura", skill_level_aura, calculated_stats_for_all_buffs)
        if final_buffs.get("aura"): final_buffs["aura"]["level"] = skill_level_aura

        aura_stat_bonus_value = final_buffs["aura"].get("stat_bonus", 0)

        base_level_1a = skill_info.get(job_skills["1a"], 0)
        if base_level_1a > 0:
            base_level_1a += 1

        bonus_level_1a = calculated_stats_for_all_buffs["skill_lv_bonuses"].get("1a", 0)
        skill_level_1a = base_level_1a + bonus_level_1a
        final_buffs["1a"] = self._calculate_buff("1a", skill_level_1a, calculated_stats_for_all_buffs, aura_stat_bonus=aura_stat_bonus_value)
        if final_buffs.get("1a"): final_buffs["1a"]["level"] = skill_level_1a

        skill_level_3a = skill_info.get(job_skills["3a"], 0) + calculated_stats_for_all_buffs["skill_lv_bonuses"].get("3a", 0)
        final_buffs["3a"] = self._calculate_buff("3a", skill_level_3a, calculated_stats_for_all_buffs, final_buffs.get("1a"), aura_stat_bonus=aura_stat_bonus_value)
        if final_buffs.get("3a"): final_buffs["3a"]["level"] = skill_level_3a

        # Fetch main buff level directly from buff_equip_equipment API
        main_buff_equip_data = data.get("buff_equip_equipment")
        main_buff_lv = 0
        if main_buff_equip_data and main_buff_equip_data.get("skill") and \
           main_buff_equip_data["skill"].get("buff") and \
           main_buff_equip_data["skill"]["buff"].get("skillInfo") and \
           main_buff_equip_data["skill"]["buff"]["skillInfo"].get("option"):
            main_buff_lv = main_buff_equip_data["skill"]["buff"]["skillInfo"]["option"].get("level", 0)

        final_buffs["main"] = self._calculate_buff("main", main_buff_lv, calculated_stats_for_all_buffs, aura_stat_bonus=aura_stat_bonus_value)
        if final_buffs.get("main"): final_buffs["main"]["level"] = main_buff_lv


        print(f"DEBUG: Final calculated stats used for buffs:")
        print(f"  Applied Stat Name: {calculated_stats_for_all_buffs['stat_name']}")
        print(f"  Applied Stat Value: {calculated_stats_for_all_buffs['stat_value']}")
        print(f"  Total Buff Power: {calculated_stats_for_all_buffs['buff_power']}")
        print(f"  Skill Level Bonuses: {calculated_stats_for_all_buffs['skill_lv_bonuses']}")

        return {
            "characterName": profile["characterName"],
            "jobName": profile["jobName"],
            "buffs": final_buffs
        }