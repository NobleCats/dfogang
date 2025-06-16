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

class BufferAnalyzer:
    def __init__(self, api_key, server, character_id):
        self.API_KEY, self.BASE_URL, self.CHARACTER_ID = api_key, f"https://api.dfoneople.com/df/servers/{server}", character_id
        self.job_code, self.item_details_cache = None, {}

    def _parse_stats_from_gear_set(self, gear_set, base_stats, character_job_id, parsing_for=['main', '1a', '3a', 'aura']):
        
        print(f"\n{'='*20}\n[+] Parsing Stats for '{gear_set.get('type', 'Unknown')}' Gear (Target: {', '.join(parsing_for).upper()})\n{'='*20}")
        
        stats = { "Intelligence": base_stats.get("Intelligence", 0), "Spirit": base_stats.get("Spirit", 0), "Stamina": base_stats.get("Stamina", 0) }
        total_buff_power, skill_lv_bonuses = 0, {"main": 0, "1a": 0, "3a": 0, "aura": 0}
        
        print(f"[STAT_LOG] Source: Base Stats | INT: {stats['Intelligence']}, SPI: {stats['Spirit']}, STA: {stats['Stamina']}")
        
        all_items = gear_set.get("equipment", [])
        if gear_set.get("avatar"): all_items.extend(gear_set.get("avatar", []))
        if gear_set.get("creature") and gear_set["creature"]: all_items.append(gear_set["creature"])
        
        skill_name_to_type = {v.lower(): k for k, v in SKILL_NAMES[self.job_code].items()}
        
        print(f"\n--- Parsing For: {', '.join(parsing_for).upper()} ---")
        for item in all_items:
            if not item: continue
            item_name, item_slot = item.get("itemName", "Unknown Item"), item.get("slotName")
            full_item_details = self.item_details_cache.get(item.get("itemId"), {})

            # 칭호 하드코딩
            if item_slot == "Title":
                if full_item_details.get("fame", 0) >= 849 and '1a' in parsing_for:
                    skill_lv_bonuses["1a"] += 2; print(f"[AURA-LOG] '{item_name}' (Hardcoded Title Rule): +2 to 1a (from Fame >= 849)")
                if "Phantom City" in item_name:
                    if 'main' in parsing_for: skill_lv_bonuses["main"] += 1
                    if '1a' in parsing_for: skill_lv_bonuses["1a"] += 1; print(f"[AURA-LOG] '{item_name}' (Hardcoded Title Rule): +1 to 1a (from 'Phantom City' name)")
                    if 'aura' in parsing_for: skill_lv_bonuses["aura"] += 1; print(f"[AURA-LOG] '{item_name}' (Hardcoded Title Rule): +1 to aura (from 'Phantom City' name)")
            
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
                                    print(f"[AURA-LOG] '{item_name}' (RangeSkill): +{bonus} to aura (Lvl {min_lvl}-{max_lvl})")
                                if '3a' in parsing_for and min_lvl <= 100 <= max_lvl: skill_lv_bonuses["3a"] += bonus
            
    

            # Enchant reinforceSkill 파싱
            for r_skill_group in item.get("enchant", {}).get("reinforceSkill", []):
                for skill in r_skill_group.get("skills", []):
                    skill_name_lower = skill.get("name", "").lower()
                    if skill_name_lower in skill_name_to_type:
                        skill_type, bonus = skill_name_to_type[skill_name_lower], skill.get("value", 0)
                        if bonus > 0:
                            skill_lv_bonuses[skill_type] += bonus
                            if skill_type == 'aura': print(f"[AURA-LOG] '{item_name}' (Enchant): +{bonus} to aura ({skill['name']})")
            
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
                            if skill_type == 'aura': print(f"[AURA-LOG] '{item_name}' ({origin}): +{bonus} to aura")
                    elif match_level:
                        lvl, bonus = int(match_level.group(1)), int(match_level.group(2))
                        if 25 <= lvl <= 35: skill_lv_bonuses["main"] += bonus
                        if 45 <= lvl <= 50: skill_lv_bonuses["1a"] += bonus
                        if 80 <= lvl <= 85: skill_lv_bonuses["aura"] += bonus; print(f"[AURA-LOG] '{item_name}' ({origin}): +{bonus} to aura from Lvl text")
                    elif match_emblem:
                        skill_name = match_emblem.group(1).strip()
                        if skill_name in skill_name_to_type:
                            skill_type, bonus = skill_name_to_type[skill_name], 1
                            skill_lv_bonuses[skill_type] += bonus
                            if skill_type == 'aura': print(f"[AURA-LOG] '{item_name}' ({origin}): +{bonus} to aura")
            
                # 기본 스탯 및 버프력 합산
            for stat in item.get("itemStatus", []):
                name, value = stat.get("name", ""), stat.get("value", 0)
                if "Buff Power" in name: total_buff_power += value
                elif "All Stats" in name:
                    stats["Intelligence"] += value; stats["Spirit"] += value; stats["Stamina"] += value
                    print(f"[STAT_LOG] Item: '{item_name}' | Source: Item Base | Stat: All Stats (+{value}) | New Totals -> INT: {stats['Intelligence']}, SPI: {stats['Spirit']}, STA: {stats['Stamina']}")
                elif "Intelligence" in name:
                    stats["Intelligence"] += value
                    print(f"[STAT_LOG] Item: '{item_name}' | Source: Item Base | Stat: Intelligence (+{value}) | New Totals -> INT: {stats['Intelligence']}, SPI: {stats['Spirit']}, STA: {stats['Stamina']}")
                elif "Spirit" in name:
                    stats["Spirit"] += value
                    print(f"[STAT_LOG] Item: '{item_name}' | Source: Item Base | Stat: Spirit (+{value}) | New Totals -> INT: {stats['Intelligence']}, SPI: {stats['Spirit']}, STA: {stats['Stamina']}")
                elif "Stamina" in name:
                    stats["Stamina"] += value
                    print(f"[STAT_LOG] Item: '{item_name}' | Source: Item Base | Stat: Stamina (+{value}) | New Totals -> INT: {stats['Intelligence']}, SPI: {stats['Spirit']}, STA: {stats['Stamina']}")

            # 소스 2: 마법 부여 스탯 (enchant.status)
            for stat in item.get("enchant", {}).get("status", []):
                name, value = stat.get("name", ""), stat.get("value", 0)
                if "Buff Power" in name: total_buff_power += value
                elif "All Stats" in name:
                    stats["Intelligence"] += value; stats["Spirit"] += value; stats["Stamina"] += value
                    print(f"[STAT_LOG] Item: '{item_name}' | Source: Enchant | Stat: All Stats (+{value}) | New Totals -> INT: {stats['Intelligence']}, SPI: {stats['Spirit']}, STA: {stats['Stamina']}")
                elif "Intelligence" in name:
                    stats["Intelligence"] += value
                    print(f"[STAT_LOG] Item: '{item_name}' | Source: Enchant | Stat: Intelligence (+{value}) | New Totals -> INT: {stats['Intelligence']}, SPI: {stats['Spirit']}, STA: {stats['Stamina']}")
                elif "Spirit" in name:
                    stats["Spirit"] += value
                    print(f"[STAT_LOG] Item: '{item_name}' | Source: Enchant | Stat: Spirit (+{value}) | New Totals -> INT: {stats['Intelligence']}, SPI: {stats['Spirit']}, STA: {stats['Stamina']}")
                elif "Stamina" in name:
                    stats["Stamina"] += value
                    print(f"[STAT_LOG] Item: '{item_name}' | Source: Enchant | Stat: Stamina (+{value}) | New Totals -> INT: {stats['Intelligence']}, SPI: {stats['Spirit']}, STA: {stats['Stamina']}")
        
        
        print("--- Parsing Complete ---")
        
        applicable_stat_value, applicable_stat_name = 0, ""
        if self.job_code in ["F_SADER", "ENCHANTRESS"]: applicable_stat_value, applicable_stat_name = stats["Intelligence"], "Intelligence"
        elif self.job_code == "MUSE": applicable_stat_value, applicable_stat_name = stats["Spirit"], "Spirit"
        elif self.job_code == "M_SADER": applicable_stat_value, applicable_stat_name = (stats["Stamina"], "Stamina") if stats["Stamina"] > stats["Spirit"] else (stats["Spirit"], "Spirit")
        
        print(f"[*] Final Applicable Stat for '{gear_set.get('type', 'Unknown')}' Gear -> {applicable_stat_name}: {applicable_stat_value}")
        print(f"{'='*20}\n")

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
                print(f"[AURA-CALC] Final Stat Bonus (from Lv.{skill_level}): {stat_bonus}")
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
        endpoints = {"profile": f"/characters/{self.CHARACTER_ID}", "status": f"/characters/{self.CHARACTER_ID}/status", "skills": f"/characters/{self.CHARACTER_ID}/skill/style","current_equipment": f"/characters/{self.CHARACTER_ID}/equip/equipment", "current_avatar": f"/characters/{self.CHARACTER_ID}/equip/avatar", "current_creature": f"/characters/{self.CHARACTER_ID}/equip/creature", "buff_equipment": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/equipment", "buff_avatar": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/avatar", "buff_creature": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/creature"}
        tasks = {name: fetch_json(session, f"{self.BASE_URL}{path}", self.API_KEY) for name, path in endpoints.items()}
        api_data = await asyncio.gather(*tasks.values())
        data = dict(zip(tasks.keys(), api_data))

        profile = data.get("profile")
        if not profile: return {"error": "Can not load the character information."}
        character_job_id = profile.get("jobId")
        self.job_code = SADER_JOB_MAP.get(character_job_id, {}).get(profile.get("jobGrowId"))
        if not self.job_code: return {"error": "Not a sader."}

        # [수정] 기본 스탯 파싱 로직 변경
        base_stats = {}
        status_list = data.get("status", {}).get("status", [])
        if status_list:
            for s in status_list:
                stat_name = s.get("name")
                # 원하는 스탯의 첫 번째 값만 저장하여 덮어쓰기 방지
                if stat_name == "Intelligence" and "Intelligence" not in base_stats:
                    base_stats["Intelligence"] = s.get("value", 0)
                elif stat_name == "Spirit" and "Spirit" not in base_stats:
                    base_stats["Spirit"] = s.get("value", 0)
                # API의 'Vitality'를 내부적으로 사용하는 'Stamina'로 매핑
                elif stat_name == "Vitality" and "Stamina" not in base_stats:
                    base_stats["Stamina"] = s.get("value", 0)

        item_ids_to_fetch = set()
        gear_sources = [data.get(k, {}).get(v, []) for k, v in {"current_equipment": "equipment", "current_avatar": "avatar", "buff_equipment": "equipment", "buff_avatar": "avatar"}.items()]
        creature_sources = [data.get("current_creature", {}).get("creature"), data.get("buff_creature", {}).get("creature")]
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
        
        all_skills = data.get("skills", {}).get("skill", {}).get("style", {}).get("active", []) + \
                 data.get("skills", {}).get("skill", {}).get("style", {}).get("passive", [])
        skill_info = {s["name"]: s["level"] for s in all_skills}
        job_skills = SKILL_NAMES[self.job_code]
        final_buffs = {}

        current_gear_set = {"equipment": data.get("current_equipment", {}).get("equipment", []), "avatar": data.get("current_avatar", {}).get("avatar", []), "creature": data.get("current_creature", {}).get("creature"), "type": "Current"}
        stats_for_current_gear = self._parse_stats_from_gear_set(current_gear_set, base_stats, character_job_id, parsing_for=['1a', '3a', 'aura'])
    
        base_level_1a = skill_info.get(job_skills["1a"], 0)
        # ### [신규] 1차 각성기 스킬 레벨 +1 보정 ###
        if base_level_1a > 0:
            base_level_1a += 1
            
        bonus_level_1a = stats_for_current_gear["skill_lv_bonuses"].get("1a", 0)
        skill_level_1a = base_level_1a + bonus_level_1a
        final_buffs["1a"] = self._calculate_buff("1a", skill_level_1a, stats_for_current_gear)
        if final_buffs.get("1a"): final_buffs["1a"]["level"] = skill_level_1a

        skill_level_3a = skill_info.get(job_skills["3a"], 0) + stats_for_current_gear["skill_lv_bonuses"].get("3a", 0)
        final_buffs["3a"] = self._calculate_buff("3a", skill_level_3a, stats_for_current_gear, final_buffs.get("1a"))
        if final_buffs.get("3a"): final_buffs["3a"]["level"] = skill_level_3a
        
        print("\n--- Calculating Aura Buff ---")
        base_level_aura = skill_info.get(job_skills["aura"], 0)
        bonus_level_aura = stats_for_current_gear["skill_lv_bonuses"].get("aura", 0)
        skill_level_aura = base_level_aura + bonus_level_aura
        print(f"[AURA LOG] Base Level from API: {base_level_aura}")
        print(f"[AURA LOG] Bonus Level from Gear: {bonus_level_aura}")
        print(f"[AURA LOG] -> Final Skill Level: {skill_level_aura}")
        
        final_buffs["aura"] = self._calculate_buff("aura", skill_level_aura, stats_for_current_gear)
        if final_buffs.get("aura"): final_buffs["aura"]["level"] = skill_level_aura


        buff_skill_info = data.get("buff_equipment", {}).get("skill", {}).get("buff", {}).get("skillInfo", {})
        final_main_buff_level_from_api = buff_skill_info.get("option", {}).get("level")
        merged_equipment_by_slot = {item['slotId']: item for item in current_gear_set["equipment"] if item and 'slotId' in item}
        for item in data.get("buff_equipment", {}).get("equipment", []):
            if item and 'slotId' in item: merged_equipment_by_slot[item['slotId']] = item
        merged_avatar = data.get("buff_avatar", {}).get("avatar", []) or current_gear_set["avatar"]
        merged_creature = data.get("buff_creature", {}).get("creature") or current_gear_set["creature"]
        merged_buff_gear_set = {"equipment": list(merged_equipment_by_slot.values()), "avatar": merged_avatar, "creature": merged_creature, "type": "Buff"}
        stats_for_main_buff = self._parse_stats_from_gear_set(merged_buff_gear_set, base_stats, character_job_id, parsing_for=['main'])
    
        if final_main_buff_level_from_api is not None:
            main_buff_lv = final_main_buff_level_from_api
        else:
            main_buff_lv = skill_info.get(job_skills["main"], 0) + stats_for_main_buff["skill_lv_bonuses"].get("main", 0)
        final_buffs["main"] = self._calculate_buff("main", main_buff_lv, stats_for_main_buff)
        if final_buffs.get("main"): final_buffs["main"]["level"] = main_buff_lv

        return { "characterName": profile["characterName"], "jobName": profile["jobName"], "buffs": final_buffs }