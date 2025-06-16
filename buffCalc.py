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

        all_items_to_process = []
        
        # Original items from the gear_set (which might be current_equipment, avatar, creature, or buff_enhancement_equipment)
        all_items_to_process.extend(gear_set.get("equipment", []))
        if gear_set.get("avatar"): all_items_to_process.extend(gear_set.get("avatar", []))
        
        # Creature handling (can be list or single dict)
        creature_data = gear_set.get("creature")
        if isinstance(creature_data, dict):
            all_items_to_process.append(creature_data)
        elif isinstance(creature_data, list):
            all_items_to_process.extend(creature_data)

        skill_name_to_type = {v.lower(): k for k, v in SKILL_NAMES[self.job_code].items()}

        print(f"DEBUG: Parsing gear set of type: {gear_set.get('type', 'Unknown')}")

        for item in all_items_to_process:
            if not item: continue
            item_name, item_slot = item.get("itemName", "Unknown Item"), item.get("slotName")
            item_id = item.get("itemId")
            full_item_details = self.item_details_cache.get(item_id, {})

            print(f"  DEBUG: Processing item: {item_name} (Slot: {item_slot}, ID: {item_id})")
            if not full_item_details:
                print(f"    DEBUG: No full_item_details found in cache for {item_name} (ID: {item_id}). This means item details API was not fetched or failed.")

            # --- Start parsing from full_item_details (if available in cache) ---
            
            # 칭호 하드코딩 (full_item_details에서 fame 확인)
            if item_slot == "Title":
                if full_item_details.get("fame", 0) >= 849 and '1a' in parsing_for:
                    skill_lv_bonuses["1a"] += 2
                if "Phantom City" in item_name:
                    if 'main' in parsing_for: skill_lv_bonuses["main"] += 1
                    if '1a' in parsing_for: skill_lv_bonuses["1a"] += 1
                    if 'aura' in parsing_for: skill_lv_bonuses["aura"] += 1

            # 모든 reinforceSkill 파싱 (full_item_details에서)
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

            # 텍스트 기반 옵션 파싱 (full_item_details와 item에서)
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

            # --- Start parsing stats from full_item_details AND item's enchant ---
            stats_to_process = []
            if full_item_details.get("itemStatus"):
                stats_to_process.extend(full_item_details.get("itemStatus", []))
            
            # Prioritize item.enchant as it contains the character-specific enchant
            if item.get("enchant", {}).get("status"):
                stats_to_process.extend(item.get("enchant", {}).get("status", []))
            elif full_item_details.get("enchant", {}).get("status"):
                stats_to_process.extend(full_item_details.get("enchant", {}).get("status", []))

            # Add any buff power from full_item_details as well
            if full_item_details.get("itemBuff", {}).get("buffPower"):
                try:
                    total_buff_power += int(full_item_details["itemBuff"]["buffPower"])
                    print(f"    DEBUG: Parsed Buff Power from full_item_details for {item_name}: {full_item_details['itemBuff']['buffPower']} (Source: Item Buff)")
                except ValueError:
                    print(f"    DEBUG: Could not convert Buff Power to int for {item_name}: {full_item_details['itemBuff']['buffPower']}")


            for stat_entry in stats_to_process:
                name = stat_entry.get("name", "")
                value_raw = stat_entry.get("value", 0)

                # Convert value to integer, handling potential '%'
                parsed_value = 0
                if isinstance(value_raw, str):
                    numeric_match = re.search(r'(\d+)', value_raw)
                    if numeric_match:
                        parsed_value = int(numeric_match.group(1))
                    else:
                        continue
                else:
                    parsed_value = int(value_raw) # Ensure it's an integer

                # Only add relevant stats
                if "Buff Power" in name:
                    total_buff_power += parsed_value
                    print(f"    DEBUG: Parsed Buff Power for {item_name}: {name}: {parsed_value} (Source: {'Item Status' if stat_entry in full_item_details.get('itemStatus', []) else 'Enchant Status'})")
                elif "Intelligence" in name: stats["Intelligence"] += parsed_value
                elif "Spirit" in name: stats["Spirit"] += parsed_value
                elif "Vitality" in name: stats["Vitality"] += parsed_value
                elif "All Stats" in name:
                    stats["Intelligence"] += parsed_value
                    stats["Spirit"] += parsed_value
                    stats["Vitality"] += parsed_value
                
                print(f"    DEBUG: Parsed stat for {item_name}: {name}: {parsed_value} (Source: {'Item Status' if stat_entry in full_item_details.get('itemStatus', []) else 'Enchant Status'})")


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
            "buff_equip_equipment": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/equipment"
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
        temp_current_creature = data.get("current_creature", {}).get("creature")
        current_creature = []
        if isinstance(temp_current_creature, list):
            current_creature.extend(temp_current_creature)
        elif isinstance(temp_current_creature, dict):
            current_creature.append(temp_current_creature)

        gear_sources = [
            current_equipment_data,
            current_avatar_data,
            current_creature
        ]

        # Also collect item IDs from buff enhancement equipment
        buff_equip_data = data.get("buff_equip_equipment", {}).get("skill", {}).get("buff", {})
        buff_enhancement_equipment = buff_equip_data.get("equipment", [])
        gear_sources.append(buff_enhancement_equipment)

        # DEBUG: Log Item IDs from buff enhancement equipment
        buff_enhancement_item_ids = [item.get("itemId") for item in buff_enhancement_equipment if item.get("itemId")]
        print(f"DEBUG: Item IDs found in Buff Enhancement Equipment: {buff_enhancement_item_ids}")


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

        # Determine the applicable stat name and value based on character's job (consolidated logic)
        # MOVED THIS BLOCK AFTER base_stats_from_status_api IS POPULATED
        applicable_stat_name = ""
        applicable_stat_value = 0 # Initialize here to ensure it's always set

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
        # No need for an else here, as "Not a sader" check handles unrecognised jobs.
        # This ensures applicable_stat_name and applicable_stat_value are always set by this point.


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

        # 버프 강화 장비 세트 구성
        buff_enhancement_gear_set = {
            "equipment": buff_enhancement_equipment,
            "type": "Buff Enhancement"
        }

        # 현재 장비 세트 파싱 (스킬 레벨 보너스와 장비 자체 스탯 포함)
        parsed_stats_from_current_gear = self._parse_stats_from_gear_set(
            current_gear_set_for_calculation,
            {"Intelligence": 0, "Spirit": 0, "Vitality": 0},
            character_job_id,
            parsing_for=['main', '1a', '3a', 'aura']
        )

        # 버프 강화 장비 세트 파싱
        parsed_stats_from_buff_enhancement_gear = self._parse_stats_from_gear_set(
            buff_enhancement_gear_set,
            {"Intelligence": 0, "Spirit": 0, "Vitality": 0},
            character_job_id,
            parsing_for=['main']
        )

        # 버프 강화 장비에서 파싱된 스탯 출력
        print("\n--- Buff Enhancement Equipment Stats (Parsed from Item Details) ---")
        print(f"Intelligence: {parsed_stats_from_buff_enhancement_gear['stats_breakdown']['Intelligence']}")
        print(f"Spirit: {parsed_stats_from_buff_enhancement_gear['stats_breakdown']['Spirit']}")
        print(f"Vitality: {parsed_stats_from_buff_enhancement_gear['stats_breakdown']['Vitality']}")
        print(f"Buff Power from Buff Enhancement Gear: {parsed_stats_from_buff_enhancement_gear['buff_power']}")
        print(f"Skill Level Bonuses from Buff Enhancement Gear: {parsed_stats_from_buff_enhancement_gear['skill_lv_bonuses']}")
        print("-------------------------------------------------------------------\n")

        # --- 현재 장착 장비와 버프 강화 장비 슬롯 비교 및 스탯 추출 ---
        buff_enh_item_stats_sum = {"Intelligence": 0, "Spirit": 0, "Vitality": 0}
        current_item_stats_sum = {"Intelligence": 0, "Spirit": 0, "Vitality": 0}
        
        buff_enh_buff_power_amp = 0
        current_buff_power_amp = 0

        print("\n--- Current Equipment Stats (Matching Buff Enhancement Slots) ---")
        for buff_enh_item in buff_enhancement_equipment:
            buff_enh_slot_name = buff_enh_item.get("slotName")
            buff_enh_item_name = buff_enh_item.get("itemName")
            
            # Sum stats from buff enhancement gear (both itemStatus and enchant status)
            buff_enh_full_item_details = self.item_details_cache.get(buff_enh_item.get("itemId"), {})
            
            buff_enh_stats_to_process = []
            if buff_enh_full_item_details.get("itemStatus"):
                buff_enh_stats_to_process.extend(buff_enh_full_item_details.get("itemStatus", []))
            if buff_enh_item.get("enchant", {}).get("status"):
                buff_enh_stats_to_process.extend(buff_enh_item.get("enchant", {}).get("status", []))
            elif buff_enh_full_item_details.get("enchant", {}).get("status"):
                buff_enh_stats_to_process.extend(buff_enh_full_item_details.get("enchant", {}).get("status", []))

            for stat_entry in buff_enh_stats_to_process:
                name = stat_entry.get("name", "")
                value_raw = stat_entry.get("value", 0)
                parsed_value = 0
                if isinstance(value_raw, str):
                    numeric_match = re.search(r'(\d+)', value_raw)
                    if numeric_match:
                        parsed_value = int(numeric_match.group(1))
                else:
                    parsed_value = int(value_raw)

                if "Intelligence" in name: buff_enh_item_stats_sum["Intelligence"] += parsed_value
                elif "Spirit" in name: buff_enh_item_stats_sum["Spirit"] += parsed_value
                elif "Vitality" in name: buff_enh_item_stats_sum["Vitality"] += parsed_value
                elif "All Stats" in name:
                    buff_enh_item_stats_sum["Intelligence"] += parsed_value
                    buff_enh_item_stats_sum["Spirit"] += parsed_value
                    buff_enh_item_stats_sum["Vitality"] += parsed_value
                elif "Buff Power Amp." in name:
                    buff_enh_buff_power_amp += parsed_value


            found_match = False
            for current_item in current_equipment_data:
                if current_item.get("slotName") == buff_enh_slot_name:
                    found_match = True
                    current_item_name = current_item.get("itemName")
                    current_item_id = current_item.get("itemId")
                    
                    print(f"Matching Slot: {buff_enh_slot_name} (Buff Enhancement: {buff_enh_item_name} | Current: {current_item_name})")
                    
                    # 3. 해당 장비의 인챈트 스탯 출력 및 합산
                    print(f"  Current Equipment's Enchant Stats for '{current_item_name}':")
                    current_enchant_status = current_item.get("enchant", {}).get("status", [])
                    if current_enchant_status:
                        for stat_entry in current_enchant_status:
                            name = stat_entry.get("name", "")
                            value_raw = stat_entry.get("value", 0)
                            parsed_value = 0
                            if isinstance(value_raw, str):
                                numeric_match = re.search(r'(\d+)', value_raw)
                                if numeric_match:
                                    parsed_value = int(numeric_match.group(1))
                            else:
                                parsed_value = int(value_raw)
                            print(f"    - {name}: {parsed_value}")
                            # Sum current item's enchant stats
                            if "Intelligence" in name: current_item_stats_sum["Intelligence"] += parsed_value
                            elif "Spirit" in name: current_item_stats_sum["Spirit"] += parsed_value
                            elif "Vitality" in name: current_item_stats_sum["Vitality"] += parsed_value
                            elif "All Stats" in name:
                                current_item_stats_sum["Intelligence"] += parsed_value
                                current_item_stats_sum["Spirit"] += parsed_value
                                current_item_stats_sum["Vitality"] += parsed_value
                            elif "Buff Power Amp." in name:
                                current_buff_power_amp += parsed_value
                    else:
                        print("    No enchant stats found.")

                    # 4. 해당 장비의 itemId로 검색하여, 장비 자체의 스탯 또한 출력 및 합산
                    print(f"  Current Equipment's Base Item Stats for '{current_item_name}':")
                    current_full_item_details = self.item_details_cache.get(current_item_id, {})
                    current_item_status = current_full_item_details.get("itemStatus", [])
                    if current_item_status:
                        for stat_entry in current_item_status:
                            name = stat_entry.get("name", "")
                            value_raw = stat_entry.get("value", 0)
                            parsed_value = 0
                            if isinstance(value_raw, str):
                                numeric_match = re.search(r'(\d+)', value_raw)
                                if numeric_match:
                                    parsed_value = int(numeric_match.group(1))
                            else:
                                parsed_value = int(value_raw)
                            print(f"    - {name}: {parsed_value}")
                            # Sum current item's base stats
                            if "Intelligence" in name: current_item_stats_sum["Intelligence"] += parsed_value
                            elif "Spirit" in name: current_item_stats_sum["Spirit"] += parsed_value
                            elif "Vitality" in name: current_item_stats_sum["Vitality"] += parsed_value
                            elif "All Stats" in name:
                                current_item_stats_sum["Intelligence"] += parsed_value
                                current_item_stats_sum["Spirit"] += parsed_value
                                current_item_stats_sum["Vitality"] += parsed_value
                            elif "Buff Power Amp." in name:
                                current_buff_power_amp += parsed_value
                    else:
                        print("    No base item stats found (or not fetched).")
                    break
            
            if not found_match:
                print(f"No matching current equipment found for Buff Enhancement Slot: {buff_enh_slot_name} ({buff_enh_item_name})")
        print("-------------------------------------------------------------------\n")

        # --- 메인 버프 계산을 위한 스탯 및 Buff Power Amp. 조정 (수정된 로직) ---
        adjusted_main_buff_stat_value = base_stats_from_status_api.get(applicable_stat_name, 0)
        adjusted_buff_power_amp_for_main = buff_power_amp_from_status_api

        # 1. 현재 장착 중인 동일 부위 장비가 제공하는 스탯/Amp.를 빼고
        adjusted_main_buff_stat_value -= current_item_stats_sum.get(applicable_stat_name, 0)
        adjusted_buff_power_amp_for_main -= current_buff_power_amp

        # 2. 버프 강화에 등록된 장비가 제공하는 스탯/Amp.를 더합니다.
        adjusted_main_buff_stat_value += buff_enh_item_stats_sum.get(applicable_stat_name, 0)
        adjusted_buff_power_amp_for_main += buff_enh_buff_power_amp

        # DEBUG: Log adjusted values
        print(f"DEBUG: Original Buff Power Amp. from status API: {buff_power_amp_from_status_api}")
        print(f"DEBUG: Buff Enhancement Gear Buff Power Amp. (sum): {buff_enh_buff_power_amp}")
        print(f"DEBUG: Current Matching Gear Buff Power Amp. (sum): {current_buff_power_amp}")
        print(f"DEBUG: Adjusted Buff Power Amp. for main buff calculation: {adjusted_buff_power_amp_for_main}")

        # Recalculate final buff power using adjusted Buff Power Amp. for main buff only
        adjusted_final_calculated_buff_power_for_main = buff_power_from_status_api * (1 + adjusted_buff_power_amp_for_main * 0.01)
        print(f"DEBUG: Adjusted Final calculated Buff Power for main buff: {adjusted_final_calculated_buff_power_for_main}")


        # For other buffs (1a, 3a, aura), use the original values from status API + current gear bonuses
        # applicable_stat_value here refers to the ORIGINAL stat from status API
        calculated_stats_for_other_buffs = {
            "stat_value": base_stats_from_status_api.get(applicable_stat_name, 0),
            "stat_name": applicable_stat_name,
            "buff_power": final_calculated_buff_power,
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


        print(f"DEBUG: Final calculated stats used for buffs (Overall Character Stats):")
        print(f"  Applied Stat Name: {applicable_stat_name}")
        print(f"  Applied Stat Value: {base_stats_from_status_api.get(applicable_stat_name, 0)}")
        print(f"  Total Buff Power: {final_calculated_buff_power}")
        print(f"  Skill Level Bonuses (from Current Gear): {calculated_stats_for_other_buffs['skill_lv_bonuses']}")


        return {
            "characterName": profile["characterName"],
            "jobName": profile["jobName"],
            "buffs": final_buffs,
            "buff_enhancement_stats": parsed_stats_from_buff_enhancement_gear["stats_breakdown"],
            "buff_enhancement_skill_lv_bonuses": parsed_stats_from_buff_enhancement_gear["skill_lv_bonuses"],
            "adjusted_main_buff_calculation_values": {
                "adjusted_stat_value": adjusted_main_buff_stat_value,
                "adjusted_buff_power": adjusted_final_calculated_buff_power_for_main
            }
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