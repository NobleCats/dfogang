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



class BufferAnalyzer:
    def __init__(self, api_key, server, character_id):
        self.API_KEY = api_key
        self.BASE_URL = f"https://api.dfoneople.com/df/servers/{server}"
        self.CHARACTER_ID = character_id
        self.job_code = None
        self.item_details_cache = {}

    def _parse_stats_from_gear_set(self, gear_set, base_stats):
        """[리팩토링됨] 장비의 모든 정보를 종합하여 스탯, 버프력, 스킬 보너스를 계산합니다."""
        stats = { "Intelligence": base_stats.get("Intelligence", 0), "Spirit": base_stats.get("Spirit", 0), "Stamina": base_stats.get("Stamina", 0) }
        total_buff_power = 0
        skill_lv_bonuses = {"main": 0, "1a": 0, "3a": 0, "aura": 0}
        all_items = gear_set.get("equipment", [])
        if gear_set.get("avatar"): all_items.extend(gear_set.get("avatar", []))
        if gear_set.get("creature"): all_items.append(gear_set["creature"])
        
        job_skills = SKILL_NAMES[self.job_code]
        skill_name_to_type = {v: k for k, v in job_skills.items()}
        
        for item in all_items:
            if not item: continue
            
            # 기본 스탯과 버프력을 합산
            all_statuses = item.get("itemStatus", [])
            if item.get("enchant"): all_statuses.extend(item["enchant"].get("status", []))
            if item.get("tune"): all_statuses.extend(item["tune"].get("status", []))
            for stat in all_statuses:
                name, value = stat.get("name", ""), stat.get("value", 0)
                if "Buff Power" in name: total_buff_power += value
                elif "Intelligence" in name: stats["Intelligence"] += value
                elif "Spirit" in name: stats["Spirit"] += value
                elif "Stamina" in name: stats["Stamina"] += value
                elif "All Stats" in name: stats["Intelligence"] += value; stats["Spirit"] += value; stats["Stamina"] += value
            
            # 구조화된 인챈트 스킬 레벨 보너스 파싱
            if item.get("enchant"):
                for r_skill_group in item["enchant"].get("reinforceSkill", []):
                    for skill in r_skill_group.get("skills", []):
                        if skill.get("name") in skill_name_to_type:
                            skill_type = skill_name_to_type[skill["name"]]
                            skill_lv_bonuses[skill_type] += skill.get("value", 0)
            
            # 텍스트 기반 스킬 레벨 옵션 파싱
            all_text_sources = []
            if item.get("itemExplainDetail"): all_text_sources.append(item["itemExplainDetail"])
            for stat in all_statuses: all_text_sources.append(stat.get("name", ""))
            if item.get("fusionOption"):
                for opt in item["fusionOption"].get("options", []): all_text_sources.append(opt.get("explainDetail", ""))
            for text_block in all_text_sources:
                if not text_block: continue
                for line in text_block.split('\n'):
                    line_lower = line.lower()
                    # "Lv. X (Buff|Active) skill levels +Y" 또는 "Lv. X Skills +Y" 패턴
                    match = re.search(r"lv\.(\d+).*(?:buff|active)?\s*skill(?: levels)?\s*\+\s*(\d+)", line_lower)
                    if match:
                        lvl, bonus = int(match.group(1)), int(match.group(2));
                        if 25 <= lvl <= 35: skill_lv_bonuses["main"] += bonus
                        if 45 <= lvl <= 50: skill_lv_bonuses["1a"] += bonus
                        if 80 <= lvl <= 85: skill_lv_bonuses["aura"] += bonus
                        if 95 <= lvl <= 100: skill_lv_bonuses["3a"] += bonus
                        continue
                    # "Level X-Y All Skill +Z" 패턴
                    match = re.search(r"level\s*(\d+)-(\d+)\s*all skill\s*\+\s*(\d+)", line_lower)
                    if match:
                        start_lvl, end_lvl, bonus = int(match.group(1)), int(match.group(2)), int(match.group(3))
                        if start_lvl <= 30 <= end_lvl: skill_lv_bonuses["main"] += bonus
                        if start_lvl <= 50 <= end_lvl: skill_lv_bonuses["1a"] += bonus
                        if start_lvl <= 85 <= end_lvl: skill_lv_bonuses["aura"] += bonus
                        if start_lvl <= 100 <= end_lvl: skill_lv_bonuses["3a"] += bonus

        # 직업에 맞는 최종 적용 스탯 결정
        applicable_stat_value, applicable_stat_name = 0, ""
        if self.job_code in ["F_SADER", "ENCHANTRESS"]:
            applicable_stat_value, applicable_stat_name = stats["Intelligence"], "Intelligence"
        elif self.job_code == "MUSE":
            applicable_stat_value, applicable_stat_name = stats["Spirit"], "Spirit"
        elif self.job_code == "M_SADER":
            if stats["Stamina"] > stats["Spirit"]:
                applicable_stat_value, applicable_stat_name = stats["Stamina"], "Stamina"
            else:
                applicable_stat_value, applicable_stat_name = stats["Spirit"], "Spirit"
        return { "stat_value": applicable_stat_value, "stat_name": applicable_stat_name, "buff_power": total_buff_power, "skill_lv_bonuses": skill_lv_bonuses }

    def _calculate_buff(self, skill_name_key, skill_level, calculated_stats, first_awakening_buff=None):
        """[리팩토링됨] 모든 버프 스킬의 계산 로직을 통합 관리합니다."""
        if not self.job_code: return {}
        skill_name = SKILL_NAMES[self.job_code][skill_name_key]
        stat, buff_power = calculated_stats.get("stat_value", 0), calculated_stats.get("buff_power", 0)
        
        if skill_name_key == "3a":
            percent_increase = common_3a_table.get(skill_level, {}).get("percent", 0)
            if first_awakening_buff and 'stat_bonus' in first_awakening_buff:
                return {"stat_bonus": round(first_awakening_buff['stat_bonus'] * (percent_increase / 100))}
            else:
                return {"increase_percent": percent_increase} # 1각 정보가 없을 경우 대비

        if skill_name_key == "aura":
            table = msader_aura_table if self.job_code == "M_SADER" else common_aura_table
            return {"stat_bonus": table.get(skill_level, {}).get("stat", 0)}

        # 메인 버프와 1차 각성기 계산 로직 통합
        if skill_name_key in ["1a", "main"]:
            consts = FORMULA_CONSTANTS.get(skill_name)
            table = common_1a_table if skill_name_key == "1a" else BUFF_TABLES[self.job_code]
            coeffs = table.get(skill_level)
            if not coeffs or not consts: return {}
            
            multiplier = (((stat + consts["X"]) / (consts["c"] + 1)) * (buff_power + consts["Y"]) * consts["Z"])
            
            if skill_name_key == "1a":
                return {"stat_bonus": round(coeffs["stat"] * multiplier)}
            else: # "main"
                return {"stat_bonus": round(coeffs["stat"] * multiplier), "atk_bonus": round(coeffs["atk"] * multiplier)}
        
        return {}

    async def run_buff_power_analysis(self, session):
        """[리팩토링됨] API 호출부터 버프 계산까지의 전체 과정을 관리합니다."""
        endpoints = {
            "profile": f"/characters/{self.CHARACTER_ID}", "status": f"/characters/{self.CHARACTER_ID}/status", 
            "skills": f"/characters/{self.CHARACTER_ID}/skill/style", 
            "current_gear": f"/characters/{self.CHARACTER_ID}/equip/equipment", 
            "current_avatar": f"/characters/{self.CHARACTER_ID}/equip/avatar", 
            "current_creature": f"/characters/{self.CHARACTER_ID}/equip/creature", 
            "buff_gear": f"/characters/{self.CHARACTER_ID}/skill/buff/equip/equipment"
        }
        tasks = {name: fetch_json(session, f"{self.BASE_URL}{path}", self.API_KEY) for name, path in endpoints.items()}
        api_data = await asyncio.gather(*tasks.values())
        data = dict(zip(tasks.keys(), api_data))

        if not data.get("profile"): return {"error": "Can not load the character information."}
        self.job_code = JOB_ID_TO_CODE.get(data["profile"]["jobGrowId"])
        if not self.job_code: return {"error": "Not a sader."}

        # 버프 스위칭 장비와 현재 착용 장비를 구분하여 데이터셋 구성
        current_gear_by_slot = {item['slotId']: item for item in data["current_gear"].get("equipment", [])}
        for item in data["buff_gear"].get("equipment", []): current_gear_by_slot[item['slotId']] = item
        buff_gear_set = { "equipment": list(current_gear_by_slot.values()), "avatar": data.get("current_avatar", {}).get("avatar", []), "creature": data.get("current_creature", {}).get("creature") }
        current_gear_set = {"equipment": data["current_gear"].get("equipment",[]), "avatar": data["current_avatar"].get("avatar",[]), "creature": data.get("current_creature", {}).get("creature")}

        # 각 장비 세트에 대한 스탯 정보 파싱
        base_stats = {s["name"]: s["value"] for s in data["status"]["status"]}
        stats_for_main_buff = self._parse_stats_from_gear_set(buff_gear_set, base_stats)
        stats_for_current_gear = self._parse_stats_from_gear_set(current_gear_set, base_stats)

        # 최종 버프 계산
        final_buffs, skill_info, job_skills = {}, {s["name"]: s["level"] for s in data["skills"]["skill"]["style"]["active"]}, SKILL_NAMES[self.job_code]
        
        buff_configs = {
            "main": {"stats": stats_for_main_buff}, "1a": {"stats": stats_for_current_gear},
            "3a": {"stats": stats_for_current_gear}, "aura": {"stats": stats_for_current_gear}
        }
        for skill_key, config in buff_configs.items():
            level = skill_info.get(job_skills[skill_key], 0) + config["stats"]["skill_lv_bonuses"].get(skill_key, 0)
            additional_args = [final_buffs.get("1a")] if skill_key == "3a" else []
            result = self._calculate_buff(skill_key, level, config["stats"], *additional_args)
            if result: result["level"] = level
            final_buffs[skill_key] = result
        
        return {
            "characterName": data["profile"]["characterName"], "jobName": data["profile"]["jobName"],
            "buffs": final_buffs, "base_stat_info": {"name": stats_for_main_buff.get("stat_name"), "value": stats_for_main_buff.get("stat_value")}
        }