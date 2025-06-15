import asyncio
import aiohttp
import re
import math
import time
import argparse
import json
import os

# --- 유틸리티 함수 ---
async def fetch_json(session, url, api_key):
    """주어진 URL로 비동기 GET 요청을 보내고 JSON 응답을 반환합니다."""
    # URL에 이미 API 키가 있는지 확인하고, 없으면 추가합니다.
    if 'apikey=' not in url:
        # [FIXED] URL에 '?'가 있는지 여부에 따라 올바른 구분자를 사용합니다.
        separator = '?' if '?' not in url else '&'
        url += f"{separator}apikey={api_key}"
        
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()
    except aiohttp.ClientError as e:
        print(f"API 요청 실패: {url}, 오류: {e}")
        return None

# --- 메인 분석 클래스 ---
class CharacterAnalyzer:
    """
    Dungeon & Fighter 캐릭터의 스탯을 비동기적으로 분석하여 DPS를 계산합니다.
    이 클래스는 독립적으로 작동하며, 외부 API로부터 모든 데이터를 가져와 처리합니다.
    """
    def __init__(self, api_key, server, character_id, cleansing_cdr=True, weapon_cdr=True, average_set_dmg=False):
        self.API_KEY = api_key
        self.BASE_URL = f"https://api.dfoneople.com/df/servers/{server}"
        self.SERVER = server
        self.CHARACTER_ID = character_id
        
        # 계산 옵션
        self.CLEANSING_CDR = cleansing_cdr
        self.WEAPON_CDR = weapon_cdr
        self.AVERAGE_SET_DMG = average_set_dmg
        
        # 데이터 캐시 및 상수
        self.item_details_cache = {}
        self.ELEMENT_KEYWORDS = {"fire": "Fire", "water": "Water", "light": "Light", "shadow": "Shadow", "all elemental": "All"}
        
        # 분석 전 스탯 초기화
        self._reset_stats()

    def _reset_stats(self):
        """계산에 사용될 모든 스탯을 초기 상태로 리셋합니다."""
        self.overall_dmg_mul = 1.0
        self.cd_reduction_mul = 1.0
        self.damage_value_sum = 0.0
        self.cd_recovery_sum = 0.0
        self.elemental_dmg_sum = {"Fire": 13.0, "Water": 13.0, "Light": 13.0, "Shadow": 13.0, "All": 0.0}

    # --- 원본 코드의 모든 계산 및 파싱 함수 (클래스 메소드로 변환) ---
    def overall_dmg_calc(self, overall_dmg, source="unknown"):
        if overall_dmg == 0: return
        self.overall_dmg_mul *= (1 + overall_dmg * 0.01)
        
    def cooldown_reduction_calc(self, cooldown_reduction, source="unknown"):
        if cooldown_reduction == 0: return
        self.cd_reduction_mul *= (1 - cooldown_reduction / 100)

    def is_paradise_set(self, set_name): return "paradise" in set_name.lower() or "gold" in set_name.lower()
    def is_cleansing_set(self, set_name): return "cleansing" in set_name.lower()
    def is_ethereal_set(self, set_name): return "ethereal" in set_name.lower()
    def is_dragon_set(self, set_name): return "dragon" in set_name.lower()
    def is_serendipity_set(self, set_name): return "serendipity" in set_name.lower()
    def is_pack_set(self, set_name): return "pack" in set_name.lower()

    def engrave_cal(self, option=None):
        if not isinstance(option, list): return 0
        for entry in option:
            if not isinstance(entry, dict): continue
            engraves = entry.get("engrave")
            if isinstance(engraves, dict): engraves = [engraves]
            elif engraves is None: engraves = []
            for engrave in engraves:
                color, value = engrave.get("color", ""), engrave.get("value", 0)
                if "gold" in color:
                    if value == 1: return 0.3
                    elif value == 2: return 0.5
                    elif value == 3: return 1.5
        return 0

    def reinforce_calc(self, reinforce, amplificationName, slotName, source=""):
        base_overall_dmg, under15, over15, total_overall_dmg = 0.2, 0.3, 0.2, 0
        if amplificationName is None:
            if slotName in ["Earrings", "Weapon"] and reinforce >= 12:
                total_overall_dmg += base_overall_dmg * 2 + under15 * min(2, (reinforce - 12))
                total_overall_dmg += over15 * max(0, (reinforce - 15))
        elif reinforce >= 10:
            total_overall_dmg += base_overall_dmg + base_overall_dmg * min(1, (reinforce - 10))
            total_overall_dmg += under15 * max(0, min(2, (reinforce - 11)))
            total_overall_dmg += over15 * max(0, (reinforce - 13))
        self.overall_dmg_calc(total_overall_dmg, source)
    
    def parse_explain_detail(self, text, source="unknown", reinforce=None, option=None):
        lines = text.lower().split("\n")
        if "[FUSION_LEG]" in source: option = None
        for line in lines:
            current_ovarall_dmg = 0
            if "sensory satisfaction" in line and reinforce is not None:
                bonus = min(max(reinforce - 10, 0), 2)
                self.overall_dmg_calc(bonus, source); return
            match = re.search(r"(\d+(?:\.\d+)?)% chance.*?skill atk\. \+(\d+(?:\.\d+)?)%", line)
            if match:
                chance, bonus = float(match.group(1)) / 100, float(match.group(2))
                current_ovarall_dmg = self.engrave_cal(option); current_ovarall_dmg += (chance * bonus)
            match = re.search(r"(\d+(?:\.\d+)?)% chance.*?reset.*cooldown", line)
            if match:
                chance = float(match.group(1)) / 100
                current_ovarall_dmg = self.engrave_cal(option); current_ovarall_dmg += ((1 / (1 - chance)) - 1) * 100
            match = re.search(r"overall damage[^\n\d]*\+([\d.]+)%", line)
            if match:
                val = float(match.group(1)); current_ovarall_dmg = self.engrave_cal(option); current_ovarall_dmg += val
            match = re.search(r"damage value\s*\+([\d.]+)", line)
            if match: self.damage_value_sum += float(match.group(1))
            match = re.search(r"cooldown recovery\s*\+([\d.]+)%", line)
            if match: self.cd_recovery_sum += float(match.group(1))
            match = re.search(r"cooldown reduction\s*\+([\d.]+)%", line)
            if match: self.cooldown_reduction_calc(float(match.group(1)), source)
            match = re.search(r"skill cooldown\s*\-([\d.]+)%", line)
            if match: self.cooldown_reduction_calc(float(match.group(1)), source)
            for key, element in self.ELEMENT_KEYWORDS.items():
                if key in line:
                    match = re.search(r"\+([\d.]+)", line)
                    if match: self.elemental_dmg_sum[element] += float(match.group(1))
            self.overall_dmg_calc(current_ovarall_dmg, source)

    def parse_stat_entry(self, stat, source=None):
        name = stat.get("name", "").lower()
        try: value = float(str(stat["value"]).replace('%', '').replace(',', '').strip())
        except (ValueError, TypeError, KeyError): return
        if "damage value" in name: self.damage_value_sum += value
        elif "cooldown reduction" in name: self.cooldown_reduction_calc(value, source)
        elif "cooldown recovery" in name: self.cd_recovery_sum += value
        elif "overall damage" in name: self.overall_dmg_calc(value, source)
        else:
            for key, element in self.ELEMENT_KEYWORDS.items():
                if key in name: self.elemental_dmg_sum[element] += value

    def parse_explain(self, explain, source=None):
        explain_txt = explain.lower()
        if "overall damage" in explain_txt:
            match = re.search(r"overall damage\s*\+([\d.]+)%", explain_txt)
            if match: self.overall_dmg_calc(float(match.group(1)), source)
        elif "damage value" in explain_txt:
            match = re.search(r"damage value\s*\+([\d.]+)", explain_txt)
            if match: self.damage_value_sum += float(match.group(1))
        elif "cooldown reduction" in explain_txt:
            match = re.search(r"cooldown reduction\s*\+([\d.]+)%", explain_txt)
            if match: self.cooldown_reduction_calc(float(match.group(1)), source)
        elif "cooldown recovery" in explain_txt:
            match = re.search(r"cooldown recovery\s*\+([\d.]+)%", explain_txt)
            if match: self.cd_recovery_sum += float(match.group(1))
        else:
            for key, element in self.ELEMENT_KEYWORDS.items():
                if key in explain_txt:
                    match = re.search(rf"{key}[^+]*\+([\d.]+)", explain_txt)
                    if match: self.elemental_dmg_sum[element] += float(match.group(1))

    def parse_item_stats_from_cache(self, item_id):
        res = self.item_details_cache.get(item_id)
        if not res: return
        item_name = res.get("itemName", item_id)
        stats = res.get("itemStatus", [])
        if "skill cooldown" in res.get("itemBuff", {}).get("explain", "").lower():
            stats = [s for s in stats if s.get("name") != "Skill Cooldown Reduction"]
        for stat in stats: self.parse_stat_entry(stat, source=f"[ITEM] {item_name}")
        detail = res.get("itemExplainDetail", "")
        if detail: self.parse_explain_detail(detail, source=f"[ITEM_DETAIL] {item_name}")

    def parse_fusion_options_from_cache(self, item):
        upgrade_info = item.get("upgradeInfo", {})
        item_name = item.get("itemName", "Unknown")
        options = item.get("fusionOption", {}).get("options", [])
        if "eternal fragment" in upgrade_info.get("itemName", "").lower():
            for opt in options:
                detail = opt.get("explainDetail", "") or opt.get("explain", "")
                if detail: self.parse_explain_detail(detail, source=f"[FUSION_LEG] {item_name}", option=options)
            return
        fusion_item_id = upgrade_info.get("itemId")
        if not fusion_item_id: return
        res = self.item_details_cache.get(fusion_item_id)
        if not res: return
        fusion_options = res.get("fusionOption", {}).get("options", [])
        for opt in fusion_options:
            detail = opt.get("explainDetail", "") or opt.get("explain", "")
            if detail:
                self.parse_explain_detail(detail, source=f"[FUSIONSTONE] {upgrade_info.get('itemName', 'Unknown')}", 
                                          reinforce=item.get("reinforce"), option=options)

    def parse_creature_item_from_cache(self, item_id, source="unknown"):
        res = self.item_details_cache.get(item_id)
        if not res: return
        for stat in res.get("itemStatus", []): self.parse_stat_entry(stat, source=source)
            
    def analyze_setitem(self, res):
        setItemInfoList = res.get("setItemInfo", [])
        if not setItemInfoList: return
        setItemInfo = setItemInfoList[0]; setItemName = setItemInfo.get("setItemName"); setItemRarityName = setItemInfo.get("setItemRarityName")
        setItemStat = setItemInfo.get("active", {}).get("status", [])
        if self.AVERAGE_SET_DMG:
            parts = setItemRarityName.strip().split()
            values = {
                "Unique":   [48.5, 68.3, 88.1, 107.9, 127.7],
                "Legendary": [184.6, 204.4, 224.2, 244.0, 263.8],
                "Epic":     [318.4, 338.2, 358.0, 377.8, 397.6],
                "Primeval": 447.4
            }
            if len(parts) == 2:
                rarity = parts[0]  # Unique, Legendary, Epic 등
                step = parts[1]    # I, II, III, IV, V
                step_map = {"I": 0, "II": 1, "III": 2, "IV": 3, "V": 4}
                index = step_map.get(step.upper())
                self.overall_dmg_calc(values[rarity][index], source="[AVERAGE SET]")
            elif len(parts) == 1:
                self.overall_dmg_calc(values["Primeval"], source="[AVERAGE SET]")
            return
        if self.is_paradise_set(setItemName):
            reinforce_acc, reinforce_total, overall_damage = 0, 0, 0
            for item in res.get("equipment", []):
                if "weapon" in item.get("slotName").lower(): continue
                if any(x in item.get("slotName").lower() for x in ["ring", "bracelet", "necklace"]): reinforce_acc += item.get("reinforce", 0)
                reinforce_total += item.get("reinforce", 0)
            if "unique" in setItemRarityName.lower(): max_reinforce_acc_stack = 7
            elif "legendary" in setItemRarityName.lower(): max_reinforce_acc_stack = 12
            else: max_reinforce_acc_stack, max_reinforce_total_stack = 12, 2
            reinforce_acc_overall_damage = min(math.floor(reinforce_acc / 3), max_reinforce_acc_stack)
            reinforce_total_overall_damage = min(math.floor((reinforce_total - 110) / 11), max_reinforce_total_stack) * 2
            self.overall_dmg_calc(reinforce_acc_overall_damage, setItemName); self.overall_dmg_calc(reinforce_total_overall_damage, setItemName); self.overall_dmg_calc(overall_damage, setItemName)
            setItemStat = [s for s in setItemStat if s.get("name") != "Skill Cooldown Reduction"]
        elif self.is_cleansing_set(setItemName):
            overall_damage = 0
            if any(x in setItemRarityName.lower() for x in ["legendary", "epic", "primeval"]):
                if self.CLEANSING_CDR:
                    for stat in setItemStat:
                        if stat.get("name") == "Skill Cooldown Reduction": stat["value"] = "55%"; break
                else:
                    overall_damage = 17.5
                    for stat in setItemStat:
                        if stat.get("name") == "Skill Cooldown Reduction": stat["value"] = "30%"; break
            self.overall_dmg_calc(overall_damage, setItemName)
        elif self.is_ethereal_set(setItemName):
            orb_map = {"unique": 1, "legendary": 2, "epic": 3, "primeval": 4}; orb_count = 0
            for key, val in orb_map.items():
                if key in setItemRarityName.lower(): orb_count = val; break
            self.overall_dmg_calc(10 * orb_count, setItemName)
        elif self.is_dragon_set(setItemName):
            overall_damage = 0
            if "epic" in setItemRarityName.lower(): overall_damage = 1.5
            elif "primeval" in setItemRarityName.lower(): overall_damage = 3
            self.overall_dmg_calc(overall_damage, setItemName)
        elif self.is_serendipity_set(setItemName):
            overall_damage, elemental_dmg = 0, 0; expected_overall_damage = []; dmg_map = {"short": 1.5, "long": 4, "random": 3, "all": 10}
            if "unique" in setItemRarityName.lower(): overall_damage = 3; expected_overall_damage.append(dmg_map["long"])
            elif "legendary" in setItemRarityName.lower(): overall_damage, elemental_dmg = 3, 33; expected_overall_damage.extend([dmg_map["short"], dmg_map["long"]])
            elif "epic" in setItemRarityName.lower(): overall_damage, elemental_dmg = 3, 33; expected_overall_damage.extend([dmg_map["long"], dmg_map["all"]])
            elif "primeval" in setItemRarityName.lower(): overall_damage, elemental_dmg = 3, 33; expected_overall_damage.extend([dmg_map["long"], dmg_map["random"], dmg_map["all"]])
            self.elemental_dmg_sum["All"] += elemental_dmg
            total_expected_overall_dmg = math.prod([1 + x / 100 for x in expected_overall_damage])
            self.overall_dmg_calc(overall_damage, setItemName)
            self.overall_dmg_calc((total_expected_overall_dmg-1)*100, setItemName) 
        elif self.is_pack_set(setItemName):
            dmg_map = {"unique": 5, "legendary": 6, "epic": 7, "primeval": 8}; overall_damage = 0
            for key, val in dmg_map.items():
                if key in setItemRarityName.lower(): overall_damage = val; break
            self.overall_dmg_calc(overall_damage, setItemName)
        for stat in setItemStat: self.parse_stat_entry(stat, source=f"[SET OPTION] {setItemName}")

    def analyze_character_equipment(self, res):
        if not res: return
        for item in res.get("equipment", []):
            if item.get("slotName") == "Secondary Weapon": continue
            if item.get("itemId"): self.parse_item_stats_from_cache(item["itemId"])
            self.parse_fusion_options_from_cache(item)
            for stat in item.get("tune", {}).get("status", []): self.parse_stat_entry(stat, source=f"[TUNE] {item.get('itemName')}")
            for stat in item.get("enchant", {}).get("status", []): self.parse_stat_entry(stat, source=f"[ENCHANT] {item.get('itemName')}")
            self.parse_explain(item.get("enchant", {}).get("explain", ""), source=f"[ENCHANT] {item.get('itemName')}")
            self.reinforce_calc(item.get("reinforce"), item.get("amplificationName"), item.get("slotName"), source="[REINFORCE]")
        self.analyze_setitem(res)

    def analyze_aura_avatar(self, res):
        if not res: return
        for avatar in res.get("avatar", []):
            if avatar.get("slotName") == "Aura Avatar" and avatar.get("itemId"): self.parse_item_stats_from_cache(avatar["itemId"])

    def analyze_creature(self, res):
        if not res: return
        creature = res.get("creature", {})
        if creature.get("itemId"): self.parse_creature_item_from_cache(creature["itemId"], source=f"[CREATURE] {creature.get('itemName')}")
        for artifact in creature.get("artifact", []):
            if artifact.get("itemId"): self.parse_creature_item_from_cache(artifact["itemId"], source=f"[ARTIFACT] {artifact.get('itemName')}")

    def analyze_insignia(self, res):
        if not res: return
        flag = res.get("flag", {})
        if flag.get("itemId"): self.parse_creature_item_from_cache(flag["itemId"], source=f"[INSIGNIA] {flag.get('itemName')}")
        for gem in flag.get("gems", []):
            if gem.get("itemId"): self.parse_creature_item_from_cache(gem["itemId"], source=f"[INSIGNIA GEM] {gem.get('itemName')}")
            
    def get_final_dps(self, status_res):
        if not status_res: return {"error": "캐릭터 상태 정보를 가져올 수 없습니다."}
        status = status_res.get("status", [])
        atk_amp = next((s["value"] for s in status if s["name"] == "Atk. Amp."), 0.0)
        all_value = self.elemental_dmg_sum.get("All", 0.0)
        if all_value:
            for element in ["Fire", "Water", "Light", "Shadow"]: self.elemental_dmg_sum[element] += all_value
        max_elemental_value = max((v for k, v in self.elemental_dmg_sum.items() if k != "All"), default=13.0)
        elemental_multiplier = 1.05 + 0.0045 * max_elemental_value
        final_damage_value = self.damage_value_sum * (1 + atk_amp / 100)
        final_damage = final_damage_value * self.overall_dmg_mul * elemental_multiplier
        effective_cooldown_multiplier = self.cd_reduction_mul * (100 / (100 + self.cd_recovery_sum if self.cd_recovery_sum > 0 else 100))
        final_cooldown_reduction_percent = (1 - effective_cooldown_multiplier) * 100
        dps = final_damage / effective_cooldown_multiplier if effective_cooldown_multiplier > 0 else 0
        return {
            "finalDamage": round(final_damage),
            "cooldownReduction": round(final_cooldown_reduction_percent, 2),
            "dps": round(dps / 1000)
        }

    async def run_analysis(self, session):
        """캐릭터 분석을 실행하고 최종 DPS 결과를 반환하는 메인 메소드."""
        self._reset_stats()
        endpoints = ["equip/equipment", "equip/avatar", "equip/creature", "equip/flag", "status"]
        tasks = [fetch_json(session, f"{self.BASE_URL}/characters/{self.CHARACTER_ID}/{ep}", self.API_KEY) for ep in endpoints]
        responses = await asyncio.gather(*tasks)
        char_data = dict(zip(["equipment", "avatar", "creature", "flag", "status"], responses))

        if not char_data.get("equipment"): return {"error": "장비 정보를 불러올 수 없습니다."}

        item_ids_to_fetch = set()
        if char_data["equipment"]:
            for item in char_data["equipment"].get("equipment", []):
                if item.get("itemId"): item_ids_to_fetch.add(item["itemId"])
                if item.get("upgradeInfo", {}).get("itemId"): item_ids_to_fetch.add(item["upgradeInfo"]["itemId"])
        if char_data["avatar"]:
            for avatar in char_data["avatar"].get("avatar", []):
                if avatar.get("slotName") == "Aura Avatar" and avatar.get("itemId"): item_ids_to_fetch.add(avatar["itemId"])
        if char_data["creature"] and char_data["creature"].get("creature"):
            creature = char_data["creature"]["creature"]
            if creature.get("itemId"): item_ids_to_fetch.add(creature["itemId"])
            for artifact in creature.get("artifact", []):
                if artifact.get("itemId"): item_ids_to_fetch.add(artifact["itemId"])
        if char_data["flag"] and char_data["flag"].get("flag"):
            flag = char_data["flag"]["flag"]
            if flag.get("itemId"): item_ids_to_fetch.add(flag["itemId"])
            for gem in flag.get("gems", []):
                if gem.get("itemId"): item_ids_to_fetch.add(gem["itemId"])

        item_tasks = [fetch_json(session, f"https://api.dfoneople.com/df/items/{item_id}", self.API_KEY) for item_id in item_ids_to_fetch]
        item_responses = await asyncio.gather(*item_tasks)
        self.item_details_cache = {res['itemId']: res for res in item_responses if res and 'itemId' in res}

        self.analyze_character_equipment(char_data["equipment"])
        self.analyze_aura_avatar(char_data["avatar"])
        self.analyze_creature(char_data["creature"])
        self.analyze_insignia(char_data["flag"])
        
        return self.get_final_dps(char_data["status"])

# --- 스크립트 실행 부분 ---
async def main():
    """스크립트 실행을 위한 메인 비동기 함수."""
    parser = argparse.ArgumentParser(description="D&F 캐릭터 DPS 분석기")
    parser.add_argument("--server", type=str, required=True, help="캐릭터 서버 ID (예: cain)")
    parser.add_argument("--characterId", type=str, required=True, help="캐릭터 고유 ID")
    parser.add_argument("--cleansing_cdr", action=argparse.BooleanOptionalAction, default=True, help="정화의 불꽃 쿨감 적용 여부")
    parser.add_argument("--weapon_cdr", action=argparse.BooleanOptionalAction, default=True, help="무기 쿨감 적용 여부 (현재 미사용)")
    parser.add_argument("--average_set_dmg", action=argparse.BooleanOptionalAction, default=False, help="세트 아이템 평균 데미지 적용 여부")
    parser.add_argument("--apikey", type=str, default=os.environ.get('DFO_API_KEY', 'sRngDaw09CPuVYcpzfL1VG5F8ozrWnQQ'), help="Neople API 키")
    
    args = parser.parse_args()

    # 분석기 클래스 인스턴스 생성
    analyzer = CharacterAnalyzer(
        api_key=args.apikey,
        server=args.server,
        character_id=args.characterId,
        cleansing_cdr=args.cleansing_cdr,
        weapon_cdr=args.weapon_cdr,
        average_set_dmg=args.average_set_dmg
    )
    
    # 비동기 세션을 통해 분석 실행
    async with aiohttp.ClientSession() as session:
        start_time = time.time()
        print("캐릭터 정보 분석을 시작합니다...")
        results = await analyzer.run_analysis(session)
        end_time = time.time()
        print(f"분석 완료! (소요 시간: {end_time - start_time:.2f}초)")

    # 결과 출력
    print("\n--- 최종 분석 결과 ---")
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    # 예시: 터미널에서 아래와 같이 실행
    # python dmgCalc.py --server cain --characterId d25349b117002ecfbe3fb50c572f65dc
    asyncio.run(main())
