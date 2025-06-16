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
            print(f"API FAILED (TRY: {attempt + 1}/{retries}): {url}, ERROR: {e}")
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
        self.character_job_id = None # Store character_job_id for _get_item_specific_stats

    def _parse_stats_from_gear_set(self, gear_set, base_stats, character_job_id, parsing_for=['main', '1a', '3a', 'aura']):
        """[최종] 어떤 버프를 위해 파싱하는지(parsing_for)에 따라 필요한 스킬 옵션만 검사합니다."""
        # Initialize stats with base_stats provided
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
                                if 'aura' in parsing_for and min_lvl <= 48 <= max_lvl: # [수정] 오라 레벨 48로 변경
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
        return { "stat_value": applicable_stat_value, "stat_name": applicable_stat_name, "buff_power": total_buff_power, "skill_lv_bonuses": skill_lv_bonuses }

    def _calculate_buff(self, skill_name_key, skill_level, calculated_stats, first_awakening_buff=None):
        if not self.job_code: return {}
        skill_name, (stat, buff_power) = SKILL_NAMES[self.job_code][skill_name_key], (calculated_stats.get("stat_value", 0), calculated_stats.get("buff_power", 0))
        base_result = {
            "applied_stat_name": calculated_stats.get("stat_name"),
            "applied_stat_value": calculated_stats.get("stat_value")
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

    def _get_item_specific_stats(self, item):
        """
        주어진 단일 아이템에서 직접적으로 부여되는 스탯 (지능, 정신력, 체력), 버프력,
        그리고 메인 버프 관련 스킬 레벨 보너스만 추출합니다.
        (itemStatus, enchant status, itemBuff explain, reinforceSkill, emblem)
        """
        stats = {"Intelligence": 0, "Spirit": 0, "Vitality": 0}
        total_buff_power = 0
        skill_lv_bonuses = {"main": 0, "1a": 0, "3a": 0, "aura": 0} # All possible keys initialized

        if not item:
            return {"stats": stats, "buff_power": total_buff_power, "skill_lv_bonuses": skill_lv_bonuses}

        full_item_details = self.item_details_cache.get(item.get("itemId"), {})
        item_name, item_slot = item.get("itemName", "Unknown Item"), item.get("slotName")
        skill_name_to_type = {v.lower(): k for k, v in SKILL_NAMES[self.job_code].items()}

        # 1. 기본 스탯 및 버프력 합산 (itemStatus, enchant status)
        for stat in item.get("itemStatus", []) + item.get("enchant", {}).get("status", []):
            name, value = stat.get("name", ""), stat.get("value", 0)
            if "Buff Power" in name:
                total_buff_power += value
            elif "Intelligence" in name:
                stats["Intelligence"] += value
            elif "Spirit" in name:
                stats["Spirit"] += value
            elif "Vitality" in name:
                stats["Vitality"] += value
            elif "All Stats" in name:
                stats["Intelligence"] += value
                stats["Spirit"] += value
                stats["Vitality"] += value

        # 2. 칭호 하드코딩
        if item_slot == "Title":
            if full_item_details.get("fame", 0) >= 849: # '1a' is 2 levels for specific title
                skill_lv_bonuses["1a"] += 2
            if "Phantom City" in item_name:
                skill_lv_bonuses["main"] += 1
                skill_lv_bonuses["1a"] += 1
                skill_lv_bonuses["aura"] += 1

        # 3. reinforceSkill 파싱 (아이템 자체 및 itemBuff 내 reinforceSkill)
        # Note: self.character_job_id must be set before calling this function
        for r_skill_source in [full_item_details.get("itemReinforceSkill", []), full_item_details.get("itemBuff", {}).get("reinforceSkill", [])]:
            for r_skill_group in r_skill_source:
                if r_skill_group.get("jobId") is None or r_skill_group.get("jobId") == self.character_job_id:
                    for range_info in r_skill_group.get("levelRange", []):
                        min_lvl, max_lvl, bonus = range_info.get("minLevel", 0), range_info.get("maxLevel", 0), range_info.get("value", 0)
                        if bonus > 0:
                            if min_lvl <= 30 <= max_lvl: skill_lv_bonuses["main"] += bonus
                            if min_lvl <= 50 <= max_lvl: skill_lv_bonuses["1a"] += bonus
                            if min_lvl <= 48 <= max_lvl: skill_lv_bonuses["aura"] += bonus
                            if min_lvl <= 100 <= max_lvl: skill_lv_bonuses["3a"] += bonus

        # 4. Enchant reinforceSkill 파싱
        for r_skill_group in item.get("enchant", {}).get("reinforceSkill", []):
            for skill in r_skill_group.get("skills", []):
                skill_name_lower = skill.get("name", "").lower()
                if skill_name_lower in skill_name_to_type:
                    skill_type, bonus = skill_name_to_type[skill_name_lower], skill.get("value", 0)
                    if bonus > 0:
                        skill_lv_bonuses[skill_type] += bonus

        # 5. 텍스트 기반 옵션 파싱 (OptionAbility, ItemBuff Explain, Emblem)
        text_sources = {"OptionAbility": item.get("optionAbility", ""), "ItemBuff Explain": full_item_details.get("itemBuff", {}).get("explain", "")}
        for emblem in item.get("emblems") or []: text_sources[f"Emblem({emblem.get('itemName')})"] = emblem.get("itemName", "")

        for origin, text_block in text_sources.items():
            if not text_block: continue
            for line in text_block.split('\n'):
                line_lower = line.lower().strip()
                if not line_lower: continue

                # Buff Power from text
                match_buff_power = re.search(r"buff power\s*\+\s*(\d+)", line_lower)
                if match_buff_power:
                    total_buff_power += int(match_buff_power.group(1))

                match_name = re.search(r"(.+?)\s*skill lv\s*\+\s*(\d+)", line_lower)
                match_level = re.search(r"lv\.\s*(\d+).*?skill(?: levels)?\s*\+\s*(\d+)", line_lower)
                match_emblem = re.search(r"platinum emblem\s*\[(.+)\]", line_lower)
                if match_name:
                    skill_name, bonus = match_name.group(1).strip(), int(match_name.group(2))
                    if skill_name in skill_name_to_type:
                        skill_lv_bonuses[skill_name_to_type[skill_name]] += bonus # Use the mapped skill type
                elif match_level:
                    lvl, bonus = int(match_level.group(1)), int(match_level.group(2))
                    if 25 <= lvl <= 35: skill_lv_bonuses["main"] += bonus
                    if 45 <= lvl <= 50: skill_lv_bonuses["1a"] += bonus
                    if 80 <= lvl <= 85: skill_lv_bonuses["aura"] += bonus # Aura is level 48, but this is a general text parse
                elif match_emblem:
                    skill_name = match_emblem.group(1).strip()
                    if skill_name in skill_name_to_type:
                        skill_lv_bonuses[skill_name_to_type[skill_name]] += 1

        return {"stats": stats, "buff_power": total_buff_power, "skill_lv_bonuses": skill_lv_bonuses}


    async def run_buff_power_analysis(self, session):
        endpoints = {
            "profile": f"/characters/{self.CHARACTER_ID}",
            "status": f"/characters/{self.CHARACTER_ID}/status",
            "skills": f"/characters/{self.CHARACTER_ID}/skill/style",
            "current_equipment": f"/characters/{self.CHARACTER_ID}/equip/equipment",
            "current_avatar": f"/characters/{self.CHARACTER_ID}/equip/avatar",
            "current_creature": f"/characters/{self.CHARACTER_ID}/equip/creature",
            "buff_equipment": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/equipment",
            "buff_avatar": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/avatar",
            "buff_creature": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/creature"
        }
        tasks = {name: fetch_json(session, f"{self.BASE_URL}{path}", self.API_KEY) for name, path in endpoints.items()}
        api_data = await asyncio.gather(*tasks.values())
        data = dict(zip(tasks.keys(), api_data))

        profile = data.get("profile")
        if not profile: return {"error": "Can not load the character information."}
        character_job_id = profile.get("jobId")
        self.job_code = SADER_JOB_MAP.get(character_job_id, {}).get(profile.get("jobGrowId"))
        self.character_job_id = character_job_id # Store for use in _get_item_specific_stats
        if not self.job_code: return {"error": "Not a sader."}

        item_ids_to_fetch = set()
        gear_sources = [
            data.get("current_equipment", {}).get("equipment", []),
            data.get("current_avatar", {}).get("avatar", []),
            # CORRECTED PATHS for buff equipment/avatar/creature
            data.get("buff_equipment", {}).get("skill", {}).get("buff", {}).get("equipment", []), # CORRECTED
            data.get("buff_avatar", {}).get("skill", {}).get("buff", {}).get("avatar", [])       # CORRECTED
        ]
        # Creature is directly under skill.buff, not skill.buff.creature.creature (like equipment/avatar)
        # So we need to handle it separately.
        buff_creature_from_api = data.get("buff_creature", {}).get("skill", {}).get("buff", {}).get("creature") # CORRECTED

        creature_sources = [
            data.get("current_creature", {}).get("creature"),
            buff_creature_from_api # Use the correctly retrieved buff creature
        ]

        for source in gear_sources:
            for item in source:
                if item and item.get("itemId"): item_ids_to_fetch.add(item["itemId"])
        for creature in creature_sources:
            if creature and creature.get("itemId"):
                item_ids_to_fetch.add(creature["itemId"])
                for artifact in creature.get("artifact", []):
                    if artifact and artifact.get("itemId"): item_ids_to_fetch.add(artifact["itemId"])

        item_tasks = [fetch_json(session, f"https://api.dfoneople.com/df/items/{item_id}", self.API_KEY) for item_id in item_ids_to_fetch]
        self.item_details_cache = {res['itemId']: res for res in await asyncio.gather(*item_tasks) if res and 'itemId' in res}


        if "status" not in data or not data["status"]:
            print(f"ERROR: 'status' data is missing or empty. Full data received: {data}")
            return {"error": "Character status data is not available."}

        # 1. "최종 스탯" (Final Stats) - from /status endpoint
        base_stats_from_status_api = {}
        if data.get("status") and data["status"].get("status"):
            for s in data["status"]["status"]:
                name = s.get("name")
                value = s.get("value", 0)
                # Only include relevant stats (Intelligence, Spirit, Vitality)
                if name in ["Intelligence", "Spirit", "Vitality"]:
                    if name in base_stats_from_status_api:
                        base_stats_from_status_api[name] = max(base_stats_from_status_api[name], value)
                    else:
                        base_stats_from_status_api[name] = value

        print(f"DEBUG: Base Stats from Status API: {base_stats_from_status_api}")

        all_skills = data.get("skills", {}).get("skill", {}).get("style", {}).get("active", []) + \
                     data.get("skills", {}).get("skill", {}).get("style", {}).get("passive", [])
        skill_info = {s["name"]: s["level"] for s in all_skills}
        job_skills = SKILL_NAMES[self.job_code]
        final_buffs = {}

        # For 1a, 3a, Aura, use base_stats_from_status_api directly as the starting point for stats
        current_gear_set_for_1a_3a_aura = {
            "equipment": data.get("current_equipment", {}).get("equipment", []),
            "avatar": data.get("current_avatar", {}).get("avatar", []),
            "creature": data.get("current_creature", {}).get("creature"),
            "type": "Current"
        }
        # Parsing for skill_lv_bonuses and buff_power from current gear for 1a, 3a, aura
        parsed_stats_from_current_gear_only = self._parse_stats_from_gear_set(
            current_gear_set_for_1a_3a_aura,
            {"Intelligence": 0, "Spirit": 0, "Vitality": 0}, # Pass 0 for base stats as they will be added later
            character_job_id,
            parsing_for=['1a', '3a', 'aura']
        )

        # Combine base_stats_from_status_api with the buff power and skill level bonuses from current gear
        stats_for_1a_3a_aura = {
            "Intelligence": base_stats_from_status_api.get("Intelligence", 0),
            "Spirit": base_stats_from_status_api.get("Spirit", 0),
            "Vitality": base_stats_from_status_api.get("Vitality", 0),
            "buff_power": parsed_stats_from_current_gear_only["buff_power"],
            "skill_lv_bonuses": parsed_stats_from_current_gear_only["skill_lv_bonuses"]
        }
        
        applicable_stat_value_1a_3a_aura = 0
        applicable_stat_name_1a_3a_aura = ""
        if self.job_code in ["F_SADER", "ENCHANTRESS"]:
            applicable_stat_value_1a_3a_aura = stats_for_1a_3a_aura["Intelligence"]
            applicable_stat_name_1a_3a_aura = "Intelligence"
        elif self.job_code == "MUSE":
            applicable_stat_value_1a_3a_aura = stats_for_1a_3a_aura["Spirit"]
            applicable_stat_name_1a_3a_aura = "Spirit"
        elif self.job_code == "M_SADER":
            if stats_for_1a_3a_aura["Vitality"] > stats_for_1a_3a_aura["Spirit"]:
                applicable_stat_value_1a_3a_aura = stats_for_1a_3a_aura["Vitality"]
                applicable_stat_name_1a_3a_aura = "Vitality"
            else:
                applicable_stat_value_1a_3a_aura = stats_for_1a_3a_aura["Spirit"]
                applicable_stat_name_1a_3a_aura = "Spirit"

        calculated_stats_for_1a_3a_aura = {
            "stat_value": applicable_stat_value_1a_3a_aura,
            "stat_name": applicable_stat_name_1a_3a_aura,
            "buff_power": stats_for_1a_3a_aura["buff_power"],
            "skill_lv_bonuses": stats_for_1a_3a_aura["skill_lv_bonuses"]
        }

        base_level_1a = skill_info.get(job_skills["1a"], 0)
        if base_level_1a > 0: # 1차 각성기 스킬 레벨 +1 보정
            base_level_1a += 1

        bonus_level_1a = calculated_stats_for_1a_3a_aura["skill_lv_bonuses"].get("1a", 0)
        skill_level_1a = base_level_1a + bonus_level_1a
        final_buffs["1a"] = self._calculate_buff("1a", skill_level_1a, calculated_stats_for_1a_3a_aura)
        if final_buffs.get("1a"): final_buffs["1a"]["level"] = skill_level_1a

        skill_level_3a = skill_info.get(job_skills["3a"], 0) + calculated_stats_for_1a_3a_aura["skill_lv_bonuses"].get("3a", 0)
        final_buffs["3a"] = self._calculate_buff("3a", skill_level_3a, calculated_stats_for_1a_3a_aura, final_buffs.get("1a"))
        if final_buffs.get("3a"): final_buffs["3a"]["level"] = skill_level_3a

        base_level_aura = skill_info.get(job_skills["aura"], 0)
        bonus_level_aura = calculated_stats_for_1a_3a_aura["skill_lv_bonuses"].get("aura", 0)
        skill_level_aura = base_level_aura + bonus_level_aura

        final_buffs["aura"] = self._calculate_buff("aura", skill_level_aura, calculated_stats_for_1a_3a_aura)
        if final_buffs.get("aura"): final_buffs["aura"]["level"] = skill_level_aura

        # --- Main Buff Calculation ---
        print("\n--- Main Buff Calculation Details ---")

        # 1. Record all buff enhancement gear by slot (equipment, avatar, creature) - CORRECTED PATHS
        buff_equipment_raw = data.get("buff_equipment", {}).get("skill", {}).get("buff", {}).get("equipment", [])
        buff_avatar_raw = data.get("buff_avatar", {}).get("skill", {}).get("buff", {}).get("avatar", [])
        buff_creature_raw = data.get("buff_creature", {}).get("skill", {}).get("buff", {}).get("creature") # Creature is direct, not in a list

        print(f"DEBUG: Raw buff_equipment from API (Corrected Path): {json.dumps(buff_equipment_raw, indent=2)}")
        print(f"DEBUG: Raw buff_avatar from API (Corrected Path): {json.dumps(buff_avatar_raw, indent=2)}")
        print(f"DEBUG: Raw buff_creature from API (Corrected Path): {json.dumps(buff_creature_raw, indent=2)}")


        buff_gear_by_slot = {item['slotId']: item for item in buff_equipment_raw if item and 'slotId' in item}
        buff_avatar_by_slot = {item['slotId']: item for item in buff_avatar_raw if item and 'slotId' in item}
        
        # 2. Record all currently equipped gear by slot
        current_gear_by_slot = {item['slotId']: item for item in data.get("current_equipment", {}).get("equipment", []) if item and 'slotId' in item}
        current_avatar_by_slot = {item['slotId']: item for item in data.get("current_avatar", {}).get("avatar", []) if item and 'slotId' in item}
        current_creature = data.get("current_creature", {}).get("creature")

        # Initialize total differences
        total_stat_diffs = {"Intelligence": 0, "Spirit": 0, "Vitality": 0}
        total_buff_power_diff = 0
        total_main_skill_lv_bonuses_diff = 0

        # Calculate differences for equipment
        # Iterate only through the slots that have buff enhancement equipment
        for slot_id, buff_item in buff_gear_by_slot.items():
            current_item = current_gear_by_slot.get(slot_id)

            buff_item_stats = self._get_item_specific_stats(buff_item)
            current_item_stats = self._get_item_specific_stats(current_item) # current_item could be None

            item_name_buff = buff_item.get("itemName", "없음")
            item_name_current = current_item.get("itemName", "없음") if current_item else "없음"

            has_diff = False
            for stat_name in ["Intelligence", "Spirit", "Vitality"]:
                diff = buff_item_stats["stats"][stat_name] - current_item_stats["stats"][stat_name]
                if diff != 0:
                    has_diff = True
                    break
            if not has_diff: # Only check buff_power and skill_lv_bonuses if no stat diff
                buff_power_diff = buff_item_stats["buff_power"] - current_item_stats["buff_power"]
                if buff_power_diff != 0:
                    has_diff = True
                else:
                    main_skill_lv_diff = buff_item_stats["skill_lv_bonuses"]["main"] - current_item_stats["skill_lv_bonuses"]["main"]
                    if main_skill_lv_diff != 0:
                        has_diff = True

            if has_diff:
                print(f"\n--- Equipment Slot: {slot_id} ({buff_item.get('slotName', 'Unknown Slot')}) ---")
                print(f"  버프 강화 장비 ({item_name_buff}):")
                print(f"    스탯: {buff_item_stats['stats']}, 버프력: {buff_item_stats['buff_power']}, 메인 버프 스킬 레벨: {buff_item_stats['skill_lv_bonuses']['main']}")
                print(f"  현재 장착 장비 ({item_name_current}):")
                print(f"    스탯: {current_item_stats['stats']}, 버프력: {current_item_stats['buff_power']}, 메인 버프 스킬 레벨: {current_item_stats['skill_lv_bonuses']['main']}")

            for stat_name in ["Intelligence", "Spirit", "Vitality"]:
                diff = buff_item_stats["stats"][stat_name] - current_item_stats["stats"][stat_name]
                if diff != 0:
                    total_stat_diffs[stat_name] += diff
                    print(f"    [{stat_name}] 차이: {diff} (누적: {total_stat_diffs[stat_name]})")

            buff_power_diff = buff_item_stats["buff_power"] - current_item_stats["buff_power"]
            if buff_power_diff != 0:
                total_buff_power_diff += buff_power_diff
                print(f"    [버프력] 차이: {buff_power_diff} (누적: {total_buff_power_diff})")

            main_skill_lv_diff = buff_item_stats["skill_lv_bonuses"]["main"] - current_item_stats["skill_lv_bonuses"]["main"]
            if main_skill_lv_diff != 0:
                total_main_skill_lv_bonuses_diff += main_skill_lv_diff
                print(f"    [메인 버프 스킬 레벨] 차이: {main_skill_lv_diff} (누적: {total_main_skill_lv_bonuses_diff})")


        # Calculate differences for avatar
        # Iterate only through the slots that have buff enhancement avatar
        for slot_id, buff_item in buff_avatar_by_slot.items():
            current_item = current_avatar_by_slot.get(slot_id)

            buff_item_stats = self._get_item_specific_stats(buff_item)
            current_item_stats = self._get_item_specific_stats(current_item) # current_item could be None

            item_name_buff = buff_item.get("itemName", "없음")
            item_name_current = current_item.get("itemName", "없음") if current_item else "없음"
            
            has_diff = False
            for stat_name in ["Intelligence", "Spirit", "Vitality"]:
                diff = buff_item_stats["stats"][stat_name] - current_item_stats["stats"][stat_name]
                if diff != 0:
                    has_diff = True
                    break
            if not has_diff:
                buff_power_diff = buff_item_stats["buff_power"] - current_item_stats["buff_power"]
                if buff_power_diff != 0:
                    has_diff = True
                else:
                    main_skill_lv_diff = buff_item_stats["skill_lv_bonuses"]["main"] - current_item_stats["skill_lv_bonuses"]["main"]
                    if main_skill_lv_diff != 0:
                        has_diff = True

            if has_diff:
                print(f"\n--- Avatar Slot: {slot_id} ({buff_item.get('slotName', 'Unknown Slot')}) ---")
                print(f"  버프 강화 아바타 ({item_name_buff}):")
                print(f"    스탯: {buff_item_stats['stats']}, 버프력: {buff_item_stats['buff_power']}, 메인 버프 스킬 레벨: {buff_item_stats['skill_lv_bonuses']['main']}")
                print(f"  현재 장착 아바타 ({item_name_current}):")
                print(f"    스탯: {current_item_stats['stats']}, 버프력: {current_item_stats['buff_power']}, 메인 버프 스킬 레벨: {current_item_stats['skill_lv_bonuses']['main']}")

            for stat_name in ["Intelligence", "Spirit", "Vitality"]:
                diff = buff_item_stats["stats"][stat_name] - current_item_stats["stats"][stat_name]
                if diff != 0:
                    total_stat_diffs[stat_name] += diff
                    print(f"    [{stat_name}] 차이: {diff} (누적: {total_stat_diffs[stat_name]})")

            buff_power_diff = buff_item_stats["buff_power"] - current_item_stats["buff_power"]
            if buff_power_diff != 0:
                total_buff_power_diff += buff_power_diff
                print(f"    [버프력] 차이: {buff_power_diff} (누적: {total_buff_power_diff})")

            main_skill_lv_diff = buff_item_stats["skill_lv_bonuses"]["main"] - current_item_stats["skill_lv_bonuses"]["main"]
            if main_skill_lv_diff != 0:
                total_main_skill_lv_bonuses_diff += main_skill_lv_diff
                print(f"    [메인 버프 스킬 레벨] 차이: {main_skill_lv_diff} (누적: {total_main_skill_lv_bonuses_diff})")

        # Calculate differences for creature
        print("\n--- Creature Slot ---")
        
        # Only proceed if there's a buff creature.
        if buff_creature_raw: # Check if the buff_creature_raw is not None
            buff_creature_stats = self._get_item_specific_stats(buff_creature_raw)
            current_creature_stats = self._get_item_specific_stats(current_creature) # current_creature could be None

            item_name_buff = buff_creature_raw.get("itemName", "없음")
            item_name_current = current_creature.get("itemName", "없음") if current_creature else "없음"
            
            has_diff = False
            for stat_name in ["Intelligence", "Spirit", "Vitality"]:
                diff = buff_creature_stats["stats"][stat_name] - current_creature_stats["stats"][stat_name]
                if diff != 0:
                    has_diff = True
                    break
            if not has_diff:
                buff_power_diff = buff_creature_stats["buff_power"] - current_creature_stats["buff_power"]
                if buff_power_diff != 0:
                    has_diff = True
                else:
                    main_skill_lv_diff = buff_creature_stats["skill_lv_bonuses"]["main"] - current_creature_stats["skill_lv_bonuses"]["main"]
                    if main_skill_lv_diff != 0:
                        has_diff = True

            if has_diff:
                print(f"  버프 강화 크리쳐 ({item_name_buff}):")
                print(f"    스탯: {buff_creature_stats['stats']}, 버프력: {buff_creature_stats['buff_power']}, 메인 버프 스킬 레벨: {buff_creature_stats['skill_lv_bonuses']['main']}")
                print(f"  현재 장착 크리쳐 ({item_name_current}):")
                print(f"    스탯: {current_creature_stats['stats']}, 버프력: {current_creature_stats['buff_power']}, 메인 버프 스킬 레벨: {current_creature_stats['skill_lv_bonuses']['main']}")

            for stat_name in ["Intelligence", "Spirit", "Vitality"]:
                diff = buff_creature_stats["stats"][stat_name] - current_creature_stats["stats"][stat_name]
                if diff != 0:
                    total_stat_diffs[stat_name] += diff
                    print(f"    [{stat_name}] 차이: {diff} (누적: {total_stat_diffs[stat_name]})")

            buff_power_diff = buff_creature_stats["buff_power"] - current_creature_stats["buff_power"]
            if buff_power_diff != 0:
                total_buff_power_diff += buff_power_diff
                print(f"    [버프력] 차이: {buff_power_diff} (누적: {total_buff_power_diff})")

            main_skill_lv_diff = buff_creature_stats["skill_lv_bonuses"]["main"] - current_creature_stats["skill_lv_bonuses"]["main"]
            if main_skill_lv_diff != 0:
                total_main_skill_lv_bonuses_diff += main_skill_lv_diff
                print(f"    [메인 버프 스킬 레벨] 차이: {main_skill_lv_diff} (누적: {total_main_skill_lv_bonuses_diff})")
        else:
            print("  버프 강화 크리쳐 없음. 차이 계산 생략.")

        # 4. Add the differences to the base_stats_from_status_api
        final_main_buff_stats_for_calculation = {
            "Intelligence": base_stats_from_status_api.get("Intelligence", 0) + total_stat_diffs["Intelligence"],
            "Spirit": base_stats_from_status_api.get("Spirit", 0) + total_stat_diffs["Spirit"],
            "Vitality": base_stats_from_status_api.get("Vitality", 0) + total_stat_diffs["Vitality"],
            "buff_power": total_buff_power_diff, # This is the NET buff power from buff gear compared to current
            "skill_lv_bonuses": {"main": total_main_skill_lv_bonuses_diff}
        }

        print("\n--- Final Main Buff Stats After Calculation ---")
        print(f"  기본 스탯 (API): {base_stats_from_status_api}")
        print(f"  장비/아바타/크리쳐 스탯/버프력/스킬 레벨 보너스 총 차이: {total_stat_diffs}, 버프력 차이: {total_buff_power_diff}, 메인 스킬 레벨 차이: {total_main_skill_lv_bonuses_diff}")
        print(f"  메인 버프 최종 스탯 (적용 전): {final_main_buff_stats_for_calculation}")


        # Determine the applicable stat for main buff based on combined stats
        applicable_stat_value_main_buff = 0
        applicable_stat_name_main_buff = ""
        if self.job_code in ["F_SADER", "ENCHANTRESS"]:
            applicable_stat_value_main_buff = final_main_buff_stats_for_calculation["Intelligence"]
            applicable_stat_name_main_buff = "Intelligence"
        elif self.job_code == "MUSE":
            applicable_stat_value_main_buff = final_main_buff_stats_for_calculation["Spirit"]
            applicable_stat_name_main_buff = "Spirit"
        elif self.job_code == "M_SADER":
            if final_main_buff_stats_for_calculation["Vitality"] > final_main_buff_stats_for_calculation["Spirit"]:
                applicable_stat_value_main_buff = final_main_buff_stats_for_calculation["Vitality"]
                applicable_stat_name_main_buff = "Vitality"
            else:
                applicable_stat_value_main_buff = final_main_buff_stats_for_calculation["Spirit"]
                applicable_stat_name_main_buff = "Spirit"

        calculated_stats_for_main_buff = {
            "stat_value": applicable_stat_value_main_buff,
            "stat_name": applicable_stat_name_main_buff,
            "buff_power": final_main_buff_stats_for_calculation["buff_power"],
            "skill_lv_bonuses": final_main_buff_stats_for_calculation["skill_lv_bonuses"]
        }
        print(f"  메인 버프 최종 스탯 (계산에 사용): {calculated_stats_for_main_buff}")


        buff_skill_info = data.get("buff_equipment", {}).get("skill", {}).get("buff", {}).get("skillInfo", {})
        final_main_buff_level_from_api = buff_skill_info.get("option", {}).get("level")

        if final_main_buff_level_from_api is not None:
            main_buff_lv = final_main_buff_level_from_api
            print(f"  API에서 가져온 메인 버프 스킬 레벨: {main_buff_lv}")
        else:
            main_buff_lv = skill_info.get(job_skills["main"], 0) + calculated_stats_for_main_buff["skill_lv_bonuses"].get("main", 0)
            print(f"  기본 메인 버프 스킬 레벨: {skill_info.get(job_skills['main'], 0)}")
            print(f"  메인 버프 스킬 레벨 보너스 (장비 차이): {calculated_stats_for_main_buff['skill_lv_bonuses'].get('main', 0)}")
            print(f"  계산된 메인 버프 스킬 레벨: {main_buff_lv}")

        final_buffs["main"] = self._calculate_buff("main", main_buff_lv, calculated_stats_for_main_buff)
        if final_buffs.get("main"): final_buffs["main"]["level"] = main_buff_lv
        return {
            "characterName": profile["characterName"],
            "jobName": profile["jobName"],
            "buffs": final_buffs
        }