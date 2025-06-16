import asyncio
import aiohttp
import re
import json
import os
import argparse

# Assume buff_tables.py exists in the same directory or is importable
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
# FORMULA_CONSTANTS는 더 이상 공식에 직접 사용되지 않지만, 다른 곳에서 참조될 수 있으므로 유지
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
        """
        주어진 장비 세트에서 스탯, 버프 파워, 스킬 레벨 보너스를 파싱합니다.
        이는 상태 API의 기본값을 제외한 순수 장비로 인한 스탯을 계산합니다.
        """
        stats = {
            "Intelligence": base_stats.get("Intelligence", 0),
            "Spirit": base_stats.get("Spirit", 0),
            "Vitality": base_stats.get("Vitality", 0)
        }
        total_buff_power, skill_lv_bonuses = 0, {"main": 0, "1a": 0, "3a": 0, "aura": 0}

        all_items_to_process = []
        all_items_to_process.extend(gear_set.get("equipment", []))
        if gear_set.get("avatar"): all_items_to_process.extend(gear_set.get("avatar", []))
        
        creature_data = gear_set.get("creature")
        if isinstance(creature_data, dict):
            all_items_to_process.append(creature_data)
        elif isinstance(creature_data, list):
            all_items_to_process.extend(creature_data)

        skill_name_to_type = {v.lower(): k for k, v in SKILL_NAMES[self.job_code].items()}

        for item in all_items_to_process:
            if not item: continue
            item_name, item_slot = item.get("itemName", "Unknown Item"), item.get("slotName")
            item_id = item.get("itemId")
            full_item_details = self.item_details_cache.get(item_id, {})

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
            
            emblems_list = item.get("emblems")
            if emblems_list is not None:
                for emblem_data in emblems_list:
                    emblem_item_id = emblem_data.get("itemId")
                    if emblem_item_id:
                        emblem_details = self.item_details_cache.get(emblem_item_id, {})
                        item_status_for_emblem = emblem_details.get("itemStatus") # Get itemStatus
                        if item_status_for_emblem: # Check for itemStatus existence
                            for stat_entry in item_status_for_emblem:
                                name = stat_entry.get("name", "")
                                value_raw = stat_entry.get("value", 0)
                                parsed_value = 0
                                if isinstance(value_raw, str):
                                    numeric_match = re.search(r'(\d+)', value_raw)
                                    if numeric_match:
                                        parsed_value = int(numeric_match.group(1))
                                else:
                                    parsed_value = int(value_raw)

                                if "Intelligence" in name: stats["Intelligence"] += parsed_value
                                elif "Spirit" in name: stats["Spirit"] += parsed_value
                                elif "Vitality" in name: stats["Vitality"] += parsed_value
                                elif "All Stats" in name:
                                    stats["Intelligence"] += parsed_value
                                    stats["Spirit"] += parsed_value
                                    stats["Vitality"] += parsed_value
                                elif "Buff Power" in name: # Buff Power can be on emblems
                                    total_buff_power += parsed_value


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
            stats_to_process = []
            if full_item_details.get("itemStatus"):
                stats_to_process.extend(full_item_details.get("itemStatus", []))
            
            if item.get("enchant", {}).get("status"):
                stats_to_process.extend(item.get("enchant", {}).get("status", []))
            elif full_item_details.get("enchant", {}).get("status"):
                stats_to_process.extend(full_item_details.get("enchant", {}).get("status", []))

            if full_item_details.get("itemBuff", {}).get("buffPower"):
                try:
                    total_buff_power += int(full_item_details["itemBuff"]["buffPower"])
                except ValueError:
                    pass

            for stat_entry in stats_to_process:
                name = stat_entry.get("name", "")
                value_raw = stat_entry.get("value", 0)

                parsed_value = 0
                if isinstance(value_raw, str):
                    numeric_match = re.search(r'(\d+)', value_raw)
                    if numeric_match:
                        parsed_value = int(numeric_match.group(1))
                    else:
                        continue
                else:
                    parsed_value = int(value_raw)

                if "Buff Power" in name:
                    total_buff_power += parsed_value
                elif "Intelligence" in name: stats["Intelligence"] += parsed_value
                elif "Spirit" in name: stats["Spirit"] += parsed_value
                elif "Vitality" in name: stats["Vitality"] += parsed_value
                elif "All Stats" in name:
                    stats["Intelligence"] += parsed_value
                    stats["Spirit"] += parsed_value
                    stats["Vitality"] += parsed_value
                

        applicable_stat_value, applicable_stat_name = 0, ""
        if self.job_code in ["F_SADER", "ENCHANTRESS"]: applicable_stat_value, applicable_stat_name = stats["Intelligence"], "Intelligence"
        elif self.job_code == "MUSE": applicable_stat_value, applicable_stat_name = stats["Spirit"], "Spirit"
        elif self.job_code == "M_SADER": applicable_stat_value, applicable_stat_name = (stats["Vitality"], "Vitality") if stats["Vitality"] > stats["Spirit"] else (stats["Spirit"], "Spirit")

        return { "stat_value": applicable_stat_value, "stat_name": applicable_stat_name, "buff_power": total_buff_power, "skill_lv_bonuses": skill_lv_bonuses, "stats_breakdown": stats }


    def _calculate_buff(self, skill_name_key, skill_level, calculated_stats, first_awakening_buff=None, aura_stat_bonus=0):
        if not self.job_code: return {}
        skill_name, (stat, buff_power) = SKILL_NAMES[self.job_code][skill_name_key], (calculated_stats.get("stat_value", 0), calculated_stats.get("buff_power", 0))

        # Apply aura_stat_bonus to the stat value for main, 1a, and 3a buffs
        if skill_name_key in ["main", "1a", "3a"]:
            stat += aura_stat_bonus

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
            # New formula for 1a: c * (stat / 750 + 1) + c * ((stat + 5250) / 750 + 1) * (buffpower + 5000) * 0.000025
            table = common_1a_table
            coeffs = table.get(skill_level)
            if not coeffs: return {} 

            c_val = coeffs["stat"] # c는 stat에 대해 진행
            
            stat_bonus_calc = c_val * (stat / 750 + 1) + c_val * ((stat + 5250) / 750 + 1) * (buff_power + 5000) * 0.000025
            
            base_result.update({"stat_bonus": round(stat_bonus_calc)})
            return base_result
        if skill_name_key == "3a":
            # New formula for 3a: 1a 결과에 3a의 퍼센트값을 곱합니다.
            percent_increase = common_3a_table.get(skill_level, {}).get("percent", 0)
            base_result.update({"increase_percent": percent_increase})
            if first_awakening_buff and 'stat_bonus' in first_awakening_buff:
                base_result["stat_bonus"] = round(first_awakening_buff['stat_bonus'] * (percent_increase / 100))
            return base_result
        if skill_name_key == "main":
            # New formula for main: c * (stat / 665 + 1) + c * ((stat + 4350) / 665 + 1) * (buffpower + 3500) * 0.000379
            table = BUFF_TABLES[self.job_code]
            coeffs = table.get(skill_level)
            if not coeffs: return {}

            # stat에 대해 진행
            c_stat = coeffs["stat"]
            stat_bonus_calc = c_stat * (stat / 665 + 1) + c_stat * ((stat + 4350) / 665 + 1) * (buff_power + 3500) * 0.000379
            
            # atk에 대해 진행
            c_atk = coeffs["atk"]
            atk_bonus_calc = c_atk * (stat / 665 + 1) + c_atk * ((stat + 4350) / 665 + 1) * (buff_power + 3500) * 0.000379
            
            base_result.update({
                "stat_bonus": round(stat_bonus_calc),
                "atk_bonus": round(atk_bonus_calc)
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
            "buff_equip_equipment": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/equipment",
            "buff_equip_creature": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/creature",
            "buff_equip_avatar": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/avatar"
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

        # Collect item IDs from current equipment, avatar, creature
        current_equipment_data = data.get("current_equipment", {}).get("equipment", [])
        current_avatar_data = data.get("current_avatar", {}).get("avatar", [])
        
        # Ensure current_creature is always a list for consistency in gear_sources
        temp_current_creature = data.get("current_creature", {}).get("creature")
        current_creature = []
        if isinstance(temp_current_creature, list):
            current_creature.extend(temp_current_creature)
        elif isinstance(temp_current_creature, dict):
            current_creature.append(temp_current_creature)

        # Initialize gear_sources_for_fetching with all known lists, ensuring they are lists (even empty)
        gear_sources_for_fetching = []
        gear_sources_for_fetching.append(current_equipment_data)
        gear_sources_for_fetching.append(current_avatar_data)
        gear_sources_for_fetching.append(current_creature) # Now guaranteed to be a list

        # Also collect item IDs from buff enhancement equipment
        buff_equip_data = data.get("buff_equip_equipment", {}).get("skill", {}).get("buff", {})
        buff_enhancement_equipment = buff_equip_data.get("equipment", [])
        gear_sources_for_fetching.append(buff_enhancement_equipment)

        # Collect item IDs from buff enhancement creature
        buff_equip_creature_data = data.get("buff_equip_creature", {}).get("skill", {}).get("buff", {})
        buff_enhancement_creature = buff_equip_creature_data.get("creature")
        # Ensure buff_enhancement_creature is a list for consistency
        buff_enh_creature_list = []
        if isinstance(buff_enhancement_creature, dict):
            buff_enh_creature_list.append(buff_enhancement_creature)
        elif isinstance(buff_enhancement_creature, list):
            buff_enh_creature_list.extend(buff_enhancement_creature)
        gear_sources_for_fetching.append(buff_enh_creature_list)

        # Collect item IDs from buff enhancement avatar
        buff_equip_avatar_data = data.get("buff_equip_avatar", {}).get("skill", {}).get("buff", {})
        buff_enhancement_avatars = buff_equip_avatar_data.get("avatar", [])
        gear_sources_for_fetching.append(buff_enhancement_avatars)


        for source_list in gear_sources_for_fetching:
            if not isinstance(source_list, (list, tuple)):
                continue 

            for item in source_list:
                if not isinstance(item, dict): # Ensure item is a dictionary
                    continue

                if item.get("itemId"):
                    item_ids_to_fetch.add(item["itemId"])
                    artifacts = item.get("artifact")
                    if artifacts is not None:
                        if isinstance(artifacts, list):
                            for artifact in artifacts:
                                if isinstance(artifact, dict) and artifact.get("itemId"): item_ids_to_fetch.add(artifact["itemId"])
                        elif isinstance(artifacts, dict):
                            if artifacts.get("itemId"): item_ids_to_fetch.add(artifacts["itemId"])

                    emblems = item.get("emblems")
                    if emblems is not None:
                        if isinstance(emblems, list):
                            for emblem in emblems:
                                if isinstance(emblem, dict) and emblem.get("itemId"): item_ids_to_fetch.add(emblem["itemId"])
        
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

        # Original stats from Status API (important for base values)
        # Removed all initial DEBUG prints here.


        # Determine the applicable stat name and value based on character's job
        applicable_stat_name = ""
        applicable_stat_value = 0 

        if self.job_code == "F_SADER" or self.job_code == "ENCHANTRESS":
            applicable_stat_name = "Intelligence"
            applicable_stat_value = base_stats_from_status_api.get("Intelligence", 0)
        elif self.job_code == "MUSE":
            applicable_stat_name = "Spirit"
            applicable_stat_value = base_stats_from_status_api.get("Spirit", 0)
        elif self.job_code == "M_SADER":
            if base_stats_from_status_api.get("Vitality", 0) > base_stats_from_status_api.get("Spirit", 0):
                applicable_stat_name = "Vitality"
                applicable_stat_value = base_stats_from_status_api.get("Vitality", 0)
            else:
                applicable_stat_name = "Spirit"
                applicable_stat_value = base_stats_from_status_api.get("Spirit", 0)


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

        # 버프 강화 장비 세트 구성 (파싱에 사용될 뿐, 스탯 합산은 아래에서 직접 수행)
        buff_enhancement_gear_set = {
            "equipment": buff_enhancement_equipment,
            "type": "Buff Enhancement"
        }

        # 현재 장비 세트 파싱 (스킬 레벨 보너스만, 스탯은 status API와 아래 조정 로직 활용)
        parsed_stats_from_current_gear = self._parse_stats_from_gear_set(
            current_gear_set_for_calculation,
            {"Intelligence": 0, "Spirit": 0, "Vitality": 0}, # base_stats 0으로 넘겨서 순수 장비 스탯만 파싱
            character_job_id,
            parsing_for=['main', '1a', '3a', 'aura']
        )

        # 버프 강화 장비 세트 파싱 (스킬 레벨 보너스만)
        parsed_stats_from_buff_enhancement_gear = self._parse_stats_from_gear_set(
            buff_enhancement_gear_set,
            {"Intelligence": 0, "Spirit": 0, "Vitality": 0},
            character_job_id,
            parsing_for=['main']
        )


        # --- 메인 버프 계산을 위한 스탯 및 Buff Power Amp. 조정 ---
        # 초기값은 status API에서 가져온 캐릭터의 전체 스탯
        adjusted_main_buff_stat_value = applicable_stat_value
        adjusted_buff_power_amp_for_main = buff_power_amp_from_status_api
        adjusted_buff_power_from_status_api_for_main = buff_power_from_status_api

        # --- 장비(Equipment) 스탯 조정 ---
        current_equipment_by_slot = {item.get("slotName"): item for item in current_equipment_data if item.get("slotName")}

        for buff_enh_item in buff_enhancement_equipment:
            buff_enh_slot_name = buff_enh_item.get("slotName")
            
            if buff_enh_slot_name and buff_enh_slot_name in current_equipment_by_slot:
                current_matching_item = current_equipment_by_slot[buff_enh_slot_name]

                # 현재 장착 중인 장비 (해당 슬롯)의 스탯/Amp.를 뺍니다.
                current_item_subtract_stat = 0
                current_item_subtract_amp = 0
                current_full_item_details = self.item_details_cache.get(current_matching_item.get("itemId"), {})
                stats_to_process = []
                if current_full_item_details.get("itemStatus"): stats_to_process.extend(current_full_item_details.get("itemStatus", []))
                if current_matching_item.get("enchant", {}).get("status"): stats_to_process.extend(current_matching_item.get("enchant", {}).get("status", []))
                elif current_full_item_details.get("enchant", {}).get("status"): stats_to_process.extend(current_full_item_details.get("enchant", {}).get("status", []))

                for stat_entry in stats_to_process:
                    name = stat_entry.get("name", "")
                    value_raw = stat_entry.get("value", 0)
                    parsed_value = 0
                    if isinstance(value_raw, str):
                        numeric_match = re.search(r'(\d+)', value_raw)
                        if numeric_match: parsed_value = int(numeric_match.group(1))
                        else: continue
                    else: parsed_value = int(value_raw)

                    if name == applicable_stat_name or name == "All Stats": current_item_subtract_stat += parsed_value
                    elif "Buff Power Amp." in name: current_item_subtract_amp += parsed_value
                
                adjusted_main_buff_stat_value -= current_item_subtract_stat
                adjusted_buff_power_amp_for_main -= current_item_subtract_amp


                # 버프 강화 장비 (해당 슬롯)의 스탯/Amp.를 더합니다.
                buff_enh_item_add_stat = 0
                buff_enh_item_add_amp = 0
                buff_enh_full_item_details = self.item_details_cache.get(buff_enh_item.get("itemId"), {})
                stats_to_process = []
                if buff_enh_full_item_details.get("itemStatus"): stats_to_process.extend(buff_enh_full_item_details.get("itemStatus", []))
                if buff_enh_item.get("enchant", {}).get("status"): stats_to_process.extend(buff_enh_item.get("enchant", {}).get("status", []))
                elif buff_enh_full_item_details.get("enchant", {}).get("status"): stats_to_process.extend(buff_enh_full_item_details.get("enchant", {}).get("status", []))

                for stat_entry in stats_to_process:
                    name = stat_entry.get("name", "")
                    value_raw = stat_entry.get("value", 0)
                    parsed_value = 0
                    if isinstance(value_raw, str):
                        numeric_match = re.search(r'(\d+)', value_raw)
                        if numeric_match: parsed_value = int(numeric_match.group(1))
                        else: continue
                    else: parsed_value = int(value_raw)
                    
                    if name == applicable_stat_name or name == "All Stats": buff_enh_item_add_stat += parsed_value
                    elif "Buff Power Amp." in name: buff_enh_item_add_amp += parsed_value

                adjusted_main_buff_stat_value += buff_enh_item_add_stat
                adjusted_buff_power_amp_for_main += buff_enh_item_add_amp


        # --- 크리처 스탯 조정 (버프 강화 크리처가 있을 때만 적용) ---
        if buff_enh_creature_list: # Check if the list contains any creature
            # 현재 장착 중인 크리처 스탯 및 버프 파워를 합산 (뺄 값)
            current_creature_subtract_stat = 0
            current_creature_subtract_amp = 0
            current_creature_subtract_bp = 0
            if current_creature: # current_creature is already a list guaranteed from above
                creature_id = current_creature[0].get("itemId")
                full_item_details = self.item_details_cache.get(creature_id, {})
                stats_to_process = []
                if full_item_details.get("itemStatus"): stats_to_process.extend(full_item_details.get("itemStatus", []))
                if current_creature[0].get("enchant", {}).get("status"): stats_to_process.extend(current_creature[0].get("enchant", {}).get("status", []))
                elif full_item_details.get("enchant", {}).get("status"): stats_to_process.extend(full_item_details.get("enchant", {}).get("status", []))

                for stat_entry in stats_to_process:
                    name = stat_entry.get("name", "")
                    value_raw = stat_entry.get("value", 0)
                    parsed_value = 0
                    if isinstance(value_raw, str):
                        numeric_match = re.search(r'(\d+)', value_raw)
                        if numeric_match: parsed_value = int(numeric_match.group(1))
                        else: continue
                    else: parsed_value = int(value_raw)
                    
                    if name == applicable_stat_name or name == "All Stats": current_creature_subtract_stat += parsed_value
                    elif "Buff Power" in name: current_creature_subtract_bp += parsed_value
                    elif "Buff Power Amp." in name: current_creature_subtract_amp += parsed_value
            
            adjusted_main_buff_stat_value -= current_creature_subtract_stat
            adjusted_buff_power_amp_for_main -= current_creature_subtract_amp
            adjusted_buff_power_from_status_api_for_main -= current_creature_subtract_bp


            # 버프 강화 크리처 스탯 및 버프 파워를 합산 (더할 값)
            buff_enh_creature_add_stat = 0
            buff_enh_creature_add_amp = 0
            buff_enh_creature_add_bp = 0
            processed_buff_enh_creature = buff_enh_creature_list[0]
            if processed_buff_enh_creature:
                creature_id = processed_buff_enh_creature.get("itemId")
                full_item_details = self.item_details_cache.get(creature_id, {})
                stats_to_process = []
                if full_item_details.get("itemStatus"): stats_to_process.extend(full_item_details.get("itemStatus", []))
                if processed_buff_enh_creature.get("enchant", {}).get("status"): stats_to_process.extend(processed_buff_enh_creature.get("enchant", {}).get("status", []))
                elif full_item_details.get("enchant", {}).get("status"): stats_to_process.extend(full_item_details.get("enchant", {}).get("status", []))

                for stat_entry in stats_to_process:
                    name = stat_entry.get("name", "")
                    value_raw = stat_entry.get("value", 0)
                    parsed_value = 0
                    if isinstance(value_raw, str):
                        numeric_match = re.search(r'(\d+)', value_raw)
                        if numeric_match: parsed_value = int(numeric_match.group(1))
                        else: continue
                    else: parsed_value = int(value_raw)
                    
                    if name == applicable_stat_name or name == "All Stats": buff_enh_creature_add_stat += parsed_value
                    elif "Buff Power" in name: buff_enh_creature_add_bp += parsed_value
                    elif "Buff Power Amp." in name: buff_enh_creature_add_amp += parsed_value

            adjusted_main_buff_stat_value += buff_enh_creature_add_stat
            adjusted_buff_power_amp_for_main += buff_enh_creature_add_amp
            adjusted_buff_power_from_status_api_for_main += buff_enh_creature_add_bp


        # --- 아바타 엠블렘 스탯 조정 (버프 강화 아바타의 특정 슬롯이 현재 장착 아바타와 일치할 경우에만 적용) ---
        current_avatar_by_slot = {item.get("slotName"): item for item in current_avatar_data if item.get("slotName")}

        for buff_enh_avatar in buff_enhancement_avatars:
            buff_enh_slot_name = buff_enh_avatar.get("slotName")
            
            if buff_enh_slot_name and buff_enh_slot_name in current_avatar_by_slot:
                current_matching_avatar = current_avatar_by_slot[buff_enh_slot_name]

                # 현재 장착 중인 아바타 (해당 슬롯)의 엠블렘 스탯을 뺍니다.
                emblems_to_subtract = current_matching_avatar.get("emblems")
                if emblems_to_subtract is not None:
                    current_avatar_sub_stat = 0
                    for emblem_data in emblems_to_subtract:
                        emblem_id = emblem_data.get("itemId")
                        if emblem_id:
                            emblem_details = self.item_details_cache.get(emblem_id, {})
                            item_status_for_emblem = emblem_details.get("itemStatus")
                            if item_status_for_emblem:
                                for stat_entry in item_status_for_emblem:
                                    name = stat_entry.get("name", "")
                                    value_raw = stat_entry.get("value", 0)
                                    parsed_value = 0
                                    if isinstance(value_raw, str):
                                        numeric_match = re.search(r'(\d+)', value_raw)
                                        if numeric_match: parsed_value = int(numeric_match.group(1))
                                        else: continue
                                    else: parsed_value = int(value_raw)

                                    if name == applicable_stat_name or name == "All Stats": current_avatar_sub_stat += parsed_value
                    adjusted_main_buff_stat_value -= current_avatar_sub_stat


                # 버프 강화 아바타 (해당 슬롯)의 엠블렘 스탯을 더합니다.
                emblems_to_add = buff_enh_avatar.get("emblems")
                if emblems_to_add is not None:
                    buff_enh_avatar_add_stat = 0
                    for emblem_data in emblems_to_add:
                        emblem_id = emblem_data.get("itemId")
                        if emblem_id:
                            emblem_details = self.item_details_cache.get(emblem_id, {})
                            item_status_for_emblem = emblem_details.get("itemStatus")
                            if item_status_for_emblem:
                                for stat_entry in item_status_for_emblem:
                                    name = stat_entry.get("name", "")
                                    value_raw = stat_entry.get("value", 0)
                                    parsed_value = 0
                                    if isinstance(value_raw, str):
                                        numeric_match = re.search(r'(\d+)', value_raw)
                                        if numeric_match: parsed_value = int(numeric_match.group(1))
                                        else: continue
                                    else: parsed_value = int(value_raw)

                                    if name == applicable_stat_name or name == "All Stats": buff_enh_avatar_add_stat += parsed_value
                    adjusted_main_buff_stat_value += buff_enh_avatar_add_stat


        # Final values for logging before returning
        adjusted_final_calculated_buff_power_for_main = adjusted_buff_power_from_status_api_for_main * (1 + adjusted_buff_power_amp_for_main * 0.01)


        # For other buffs (1a, 3a, aura), use the original values from status API + current gear bonuses
        calculated_stats_for_other_buffs = {
            "stat_value": applicable_stat_value,
            "stat_name": applicable_stat_name,
            "buff_power": (buff_power_from_status_api * (1 + buff_power_amp_from_status_api * 0.01)), # Original full buff power
            "skill_lv_bonuses": {
                "main": 0,
                "1a": parsed_stats_from_current_gear["skill_lv_bonuses"].get("1a", 0),
                "3a": parsed_stats_from_current_gear["skill_lv_bonuses"].get("3a", 0),
                "aura": parsed_stats_from_current_gear["skill_lv_bonuses"].get("aura", 0),
            }
        }

        # Main buff calculation will use the adjusted values
        calculated_stats_for_main_buff = {
            "stat_value": adjusted_main_buff_stat_value,
            "stat_name": applicable_stat_name,
            "buff_power": adjusted_final_calculated_buff_power_for_main,
            "skill_lv_bonuses": {
                "main": 0,
                "1a": parsed_stats_from_current_gear["skill_lv_bonuses"].get("1a", 0),
                "3a": parsed_stats_from_current_gear["skill_lv_bonuses"].get("3a", 0),
                "aura": parsed_stats_from_current_gear["skill_lv_bonuses"].get("aura", 0),
            }
        }

        # Calculate Aura first (using calculated_stats_for_other_buffs)
        base_level_aura = skill_info.get(job_skills["aura"], 0)
        bonus_level_aura = calculated_stats_for_other_buffs["skill_lv_bonuses"].get("aura", 0)
        skill_level_aura = base_level_aura + bonus_level_aura

        final_buffs["aura"] = self._calculate_buff("aura", skill_level_aura, calculated_stats_for_other_buffs)
        if final_buffs.get("aura"): final_buffs["aura"]["level"] = skill_level_aura

        aura_stat_bonus_value = final_buffs["aura"].get("stat_bonus", 0)

        # Calculate 1a (using calculated_stats_for_other_buffs)
        base_level_1a = skill_info.get(job_skills["1a"], 0)
        if base_level_1a > 0:
            base_level_1a += 1

        bonus_level_1a = calculated_stats_for_other_buffs["skill_lv_bonuses"].get("1a", 0)
        skill_level_1a = base_level_1a + bonus_level_1a
        final_buffs["1a"] = self._calculate_buff("1a", skill_level_1a, calculated_stats_for_other_buffs, aura_stat_bonus=aura_stat_bonus_value)
        if final_buffs.get("1a"): final_buffs["1a"]["level"] = skill_level_1a

        # Calculate 3a (using calculated_stats_for_other_buffs)
        skill_level_3a = skill_info.get(job_skills["3a"], 0) + calculated_stats_for_other_buffs["skill_lv_bonuses"].get("3a", 0)
        final_buffs["3a"] = self._calculate_buff("3a", skill_level_3a, calculated_stats_for_other_buffs, final_buffs.get("1a"), aura_stat_bonus=aura_stat_bonus_value)
        if final_buffs.get("3a"): final_buffs["3a"]["level"] = skill_level_3a

        # Fetch main buff level directly from buff_equip_equipment API
        main_buff_equip_data = data.get("buff_equip_equipment")
        main_buff_lv = 0
        if main_buff_equip_data and main_buff_equip_data.get("skill") and \
           main_buff_equip_data["skill"].get("buff") and \
           main_buff_equip_data["skill"]["buff"].get("skillInfo") and \
           main_buff_equip_data["skill"]["buff"]["skillInfo"].get("option"):
            main_buff_lv = main_buff_equip_data["skill"]["buff"]["skillInfo"]["option"].get("level", 0)

        final_buffs["main"] = self._calculate_buff("main", main_buff_lv, calculated_stats_for_main_buff, aura_stat_bonus=aura_stat_bonus_value)
        if final_buffs.get("main"): final_buffs["main"]["level"] = main_buff_lv


        return {
            "buffs": final_buffs
        }

async def main():
    parser = argparse.ArgumentParser(description="Calculate DFO character buff power.")
    parser.add_argument("--api_key_file", default="DFO_API_KEY", help="Path to the file containing your DFO API key. Defaults to 'DFO_API_KEY' in the current directory.")
    parser.add_argument("--server", required=True, help="DFO server ID (e.g., 'anton', 'bakal', 'diregie').")
    parser.add_argument("--character_id", required=True, help="DFO character ID.")
    args = parser.parse_args()

    # Read API key from file
    api_key = None
    try:
        with open(args.api_key_file, 'r') as f:
            api_key = f.read().strip()
    except FileNotFoundError:
        print(f"Error: API key file '{args.api_key_file}' not found.")
        print("Please ensure the file exists and contains your API key.")
        return
    except Exception as e:
        print(f"Error reading API key from file: {e}")
        return

    if not api_key:
        print(f"Error: API key not found in file '{args.api_key_file}'.")
        print("Please ensure the file is not empty.")
        return

    server = args.server
    character_id = args.character_id

    analyzer = BufferAnalyzer(api_key, server, character_id)

    async with aiohttp.ClientSession() as session:
        result = await analyzer.run_buff_power_analysis(session)
        print(json.dumps(result, indent=4, ensure_ascii=False))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}")