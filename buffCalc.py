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
        """[최종] 어떤 버프를 위해 파싱하는지(parsing_for)에 따라 필요한 스킬 옵션만 검사합니다."""
        stats = { "Intelligence": base_stats.get("Intelligence", 0), "Spirit": base_stats.get("Spirit", 0), "Stamina": base_stats.get("Stamina", 0) }
        total_buff_power, skill_lv_bonuses = 0, {"main": 0, "1a": 0, "3a": 0, "aura": 0}
        
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
            for stat in item.get("itemStatus", []) + item.get("enchant", {}).get("status", []):
                name, value = stat.get("name", ""), stat.get("value", 0)
                if "Buff Power" in name: total_buff_power += value
                elif "Intelligence" in name: stats["Intelligence"] += value
                elif "Spirit" in name: stats["Spirit"] += value
                elif "Stamina" in name: stats["Stamina"] += value
                elif "All Stats" in name: stats["Intelligence"] += value; stats["Spirit"] += value; stats["Stamina"] += value
        
        print("--- Parsing Complete ---")
        
        applicable_stat_value, applicable_stat_name = 0, ""
        if self.job_code in ["F_SADER", "ENCHANTRESS"]: applicable_stat_value, applicable_stat_name = stats["Intelligence"], "Intelligence"
        elif self.job_code == "MUSE": applicable_stat_value, applicable_stat_name = stats["Spirit"], "Spirit"
        elif self.job_code == "M_SADER": applicable_stat_value, applicable_stat_name = (stats["Stamina"], "Stamina") if stats["Stamina"] > stats["Spirit"] else (stats["Spirit"], "Spirit")
        return { "stat_value": applicable_stat_value, "stat_name": applicable_stat_name, "buff_power": total_buff_power, "skill_lv_bonuses": skill_lv_bonuses }

    def _calculate_buff(self, skill_name_key, skill_level, calculated_stats, first_awakening_buff=None):
        if not self.job_code: return {}
        skill_name, (stat, buff_power) = SKILL_NAMES[self.job_code][skill_name_key], (calculated_stats.get("stat_value", 0), calculated_stats.get("buff_power", 0))
        
        if skill_name_key == "aura":
            table = msader_aura_table if self.job_code == "M_SADER" else common_aura_table
            stat_bonus = table.get(skill_level, {}).get("stat", 0)
            print(f"[AURA-CALC] Final Stat Bonus (from Lv.{skill_level}): {stat_bonus}")
            return {"stat_bonus": stat_bonus}
        if skill_name_key == "1a":
            consts, table = FORMULA_CONSTANTS.get(skill_name), common_1a_table
            coeffs = table.get(skill_level)
            if not coeffs or not consts: return {}
            multiplier = (((stat + consts["X"]) / (consts["c"] + 1)) * (buff_power + consts["Y"]) * consts["Z"])
            return {"stat_bonus": round(coeffs["stat"] * multiplier)}
        if skill_name_key == "3a":
            percent_increase = common_3a_table.get(skill_level, {}).get("percent", 0)
            return {"stat_bonus": round(first_awakening_buff['stat_bonus'] * (percent_increase / 100))} if first_awakening_buff and 'stat_bonus' in first_awakening_buff else {"increase_percent": percent_increase}
        if skill_name_key == "main":
            consts, table = FORMULA_CONSTANTS.get(skill_name), BUFF_TABLES[self.job_code]
            coeffs = table.get(skill_level)
            if not coeffs or not consts: return {}
            multiplier = (((stat + consts["X"]) / (consts["c"] + 1)) * (buff_power + consts["Y"]) * consts["Z"])
            return {"stat_bonus": round(coeffs["stat"] * multiplier), "atk_bonus": round(coeffs["atk"] * multiplier)}
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
        
        # 기본 스탯, 스킬 정보 로드
        base_stats = {s["name"]: s["value"] for s in data["status"]["status"]}
        skill_info = {s["name"]: s["level"] for s in data["skills"]["skill"]["style"]["active"]}
        job_skills = SKILL_NAMES[self.job_code]
        final_buffs = {}

        # 2. 각성기/오라에 사용할 순수 스탯 값 결정
        applicable_stat_name = ""
        if self.job_code in ["F_SADER", "ENCHANTRESS"]: applicable_stat_name = "Intelligence"
        elif self.job_code == "MUSE": applicable_stat_name = "Spirit"
        elif self.job_code == "M_SADER": # 남크루는 스태미나/정신력 중 높은 쪽을 따름
            applicable_stat_name = "Stamina" if base_stats.get("Stamina", 0) > base_stats.get("Spirit", 0) else "Spirit"
        
        raw_stat_for_awakenings = base_stats.get(applicable_stat_name, 0)

        # 3. '현재 착용 장비'에서 보너스 레벨과 '버프력'만 파싱
        current_gear_set = {"equipment": data.get("current_equipment", {}).get("equipment", []), "avatar": data.get("current_avatar", {}).get("avatar", []), "creature": data.get("current_creature", {}).get("creature"), "type": "Current"}
        stats_for_current_gear = self._parse_stats_from_gear_set(current_gear_set, base_stats, character_job_id)
        # 각성기 계산용 스탯 객체 생성
        awakening_calc_stats = {"stat_value": raw_stat_for_awakenings, "buff_power": stats_for_current_gear["buff_power"], "stat_name": applicable_stat_name}

        # 1a, 3a, Aura 계산
        for skill_key in ["1a", "3a", "aura"]:
            base_level = skill_info.get(job_skills[skill_key], 0)
            # 1a +1 보정
            if skill_key == "1a" and base_level > 0: base_level += 1
            bonus_level = stats_for_current_gear["skill_lv_bonuses"].get(skill_key, 0)
            final_level = base_level + bonus_level
            
            # 계산 실행
            additional_args = [final_buffs.get("1a")] if skill_key == "3a" else []
            result = self._calculate_buff(skill_key, final_level, awakening_calc_stats, *additional_args)
            if result:
                result["level"] = final_level
                result["applied_stat_name"] = applicable_stat_name
                result["applied_stat_value"] = raw_stat_for_awakenings
            final_buffs[skill_key] = result
            
        # 4. '버프 강화 정보' 덮어쓰기 후 메인 버프 계산
        merged_equipment_by_slot = {item['slotId']: item for item in current_gear_set["equipment"] if item and 'slotId' in item}
        for item in data.get("buff_equipment", {}).get("equipment", []):
            if item and 'slotId' in item: merged_equipment_by_slot[item['slotId']] = item
        merged_avatar = data.get("buff_avatar", {}).get("avatar", []) or current_gear_set["avatar"]
        merged_creature = data.get("buff_creature", {}).get("creature") or current_gear_set["creature"]
        
        merged_buff_gear_set = {"equipment": list(merged_equipment_by_slot.values()), "avatar": merged_avatar, "creature": merged_creature, "type": "Buff"}
        stats_for_main_buff = self._parse_stats_from_gear_set(merged_buff_gear_set, base_stats, character_job_id)
        
        final_main_buff_level_from_api = data.get("buff_equipment", {}).get("skill", {}).get("buff", {}).get("skillInfo", {}).get("option", {}).get("level")
        main_buff_lv = final_main_buff_level_from_api or (skill_info.get(job_skills["main"], 0) + stats_for_main_buff["skill_lv_bonuses"].get("main", 0))
        
        final_buffs["main"] = self._calculate_buff("main", main_buff_lv, stats_for_main_buff)
        if final_buffs.get("main"):
            final_buffs["main"]["level"] = main_buff_lv
            final_buffs["main"]["applied_stat_name"] = stats_for_main_buff.get("stat_name")
            final_buffs["main"]["applied_stat_value"] = stats_for_main_buff.get("stat_value")

        return { "characterName": profile["characterName"], "jobName": profile["jobName"], "buffs": final_buffs }