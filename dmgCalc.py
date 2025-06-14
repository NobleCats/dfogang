import requests
import re
import math

API_KEY = "sRngDaw09CPuVYcpzfL1VG5F8ozrWnQQ"
BASE_URL = "https://api.dfoneople.com/df"
SERVER = "cain"
CHARACTER_ID = "66707ebab4c88f3cb5d15e7dff83bb35"
CLEANSING_CDR = False
WEAPON_CDR = True

# 누적 스탯 초기화
overall_dmg_mul = 1.0
cd_reduction_mul = 1.0
damage_value_sum = 0.0
atk_amp_sum = 0.0
cd_recovery_sum = 0.0
elemental_dmg_sum = {"Fire": 13.0, "Water": 13.0, "Light": 13.0, "Shadow": 13.0, "All": 0.0}  # 기본 속강 13 포함

ELEMENT_KEYWORDS = {
    "fire": "Fire",
    "water": "Water",
    "light": "Light",
    "shadow": "Shadow",
    "all elemental": "All"
}

def is_paradise_set(set_name):
    return "paradise" in set_name.lower() or "gold" in set_name.lower()

def is_cleansing_set(set_name):
    return "cleansing" in set_name.lower()

def is_ethereal_set(set_name):
    return "ethereal" in set_name.lower()

def is_dragon_set(set_name):
    return "dragon" in set_name.lower()

def is_serendipity_set(set_name):
    return "serendipity" in set_name.lower()

def is_pack_set(set_name):
    return "pack" in set_name.lower()

def parse_explain_detail(text, source="unknown", reinforce=None):
    global overall_dmg_mul, cd_reduction_mul, damage_value_sum, atk_amp_sum, cd_recovery_sum, elemental_dmg_sum

    lines = text.lower().split("\n")
    bonus_from_reinforce = 0
    for line in lines:
        if "sensory satisfaction" in line and reinforce is not None:
            bonus = min(max(reinforce - 10, 0), 2) * 0.01
            bonus_from_reinforce = bonus
            continue

        if "all atk." in line:
            match = re.search(r"\+([\d.]+)%", line)
            if match:
                val = float(match.group(1))
                atk_amp_sum += val
                continue

        match = re.search(r"(\d+(?:\.\d+)?)% chance.*?skill atk\. \+(\d+(?:\.\d+)?)%", line)
        if match:
            chance = float(match.group(1)) / 100
            bonus = float(match.group(2)) / 100
            expected = chance * bonus
            overall_dmg_mul *= (1 + expected)
            print(f"[EXPLAIN] {source} -> {chance*100:.2f}% chance of +{bonus*100:.2f}% -> x{1 + expected:.4f} -> Total : {overall_dmg_mul * 100:.1f}%")
            continue

        match = re.search(r"(\d+(?:\.\d+)?)% chance.*?reset.*cooldown", line)
        if match:
            chance = float(match.group(1)) / 100
            boost = 1 / (1 - chance)
            overall_dmg_mul *= boost
            print(f"[EXPLAIN] {source} -> {chance*100:.2f}% chance of cooldown reset -> treated as x{boost:.4f} Overall Dmg -> Total : {overall_dmg_mul * 100:.1f}%")
            continue


        match = re.search(r"overall damage[^\n\d]*\+([\d.]+)%", line)
        if match:
            val = float(match.group(1)) / 100
            mult = (1 + val) * (1 + bonus_from_reinforce)
            overall_dmg_mul *= mult
            print(f"🔥[OVERALL] {source} -> +{val*100:.1f}% Overall (+{bonus_from_reinforce*100:.1f}% cond) -> x{mult:.4f} -> Total : {overall_dmg_mul * 100:.1f}%")
            continue

        match = re.search(r"damage value\s*\+([\d.]+)", line)
        if match:
            val = float(match.group(1))
            damage_value_sum += val
            continue

        match = re.search(r"attack amplification\s*\+([\d.]+)", line)
        if match:
            atk_amp_sum += float(match.group(1))
            continue

        match = re.search(r"cooldown recovery\s*\+([\d.]+)%", line)
        if match:
            val = float(match.group(1))
            cd_recovery_sum += val
            continue

        for key, element in ELEMENT_KEYWORDS.items():
            if key in line:
                match = re.search(r"\+([\d.]+)", line)
                if match:
                    val = float(match.group(1))
                    elemental_dmg_sum[element] += val


def parse_stat_entry(stat, source=None):
    global overall_dmg_mul, cd_reduction_mul, damage_value_sum, atk_amp_sum, cd_recovery_sum, elemental_dmg_sum

    name = stat["name"].lower()
    value_raw = stat["value"]
    
    
    if isinstance(value_raw, str):
        value_str = value_raw.replace('%', '').replace(',', '').strip()
        try:
            value = float(value_str)
        except ValueError:
            return
    else:
        value = float(value_raw)

    if "damage value" in name:
        damage_value_sum += value
    elif "attack amplification" in name or "atk. amp" in name:
        atk_amp_sum += value
    elif "cooldown reduction" in name:
        cd_reduction_mul *= (1 - value / 100)
    elif "cooldown recovery" in name:
        cd_recovery_sum += value
    elif "overall damage" in name:
        overall_dmg_mul *= (1 + value / 100)
        print(f"🔥[OVERALL] {source} -> +{value:.1f}% Overall (Tune) -> x{1 + value/100:.4f} -> Total : {overall_dmg_mul * 100:.1f}%")
    else:
        for key, element in ELEMENT_KEYWORDS.items():
            if key in name:
                elemental_dmg_sum[element] += value

    # 무기 튠 확인
#    if source and "튠" in source:
#        if "overall damage" in name:
#            overall_dmg_mul *= (1 + value / 100)
#            print(f"🔥[OVERALL] {source} -> +{value:.1f}% Overall (Tune) -> x{1 + value/100:.4f} -> Total : {overall_dmg_mul * 100:.1f}%")
                
def parse_item_stats(item_id):
    url = f"{BASE_URL}/items/{item_id}?apikey={API_KEY}"
    res = requests.get(url).json()
    item_name = res.get("itemName", item_id)
    stats = res.get("itemStatus", [])
    
    
    for stat in stats:
        parse_stat_entry(stat, source=f"[아이템] {item_name}")

    detail = res.get("itemExplainDetail", "")
    if detail:
        parse_explain_detail(detail, source=f"[아이템설명] {item_name}")

def parse_fusion_options(item):
    reinforce = item.get("reinforce")
    upgrade_info = item.get("upgradeInfo", {})
    fusion = item.get("fusionOption", {})
    options = fusion.get("options", [])
    item_name = item.get("itemName", "Unknown")

    if "eternal fragment" in upgrade_info.get("itemName", "").lower():
        for opt in options:
            detail = opt.get("explainDetail", "") or opt.get("explain", "")
            if detail:
                parse_explain_detail(detail, source=f"[융합석:기존] {item_name}")
        return

    fusion_item_id = upgrade_info.get("itemId")
    if not fusion_item_id:
        return

    url = f"{BASE_URL}/items/{fusion_item_id}?apikey={API_KEY}"
    res = requests.get(url).json()
    fusion_options = res.get("fusionOption", {}).get("options", [])

    for opt in fusion_options:
        detail = opt.get("explainDetail", "") or opt.get("explain", "")
        if detail:
            parse_explain_detail(detail, source=f"[융합석:조회] {upgrade_info.get('itemName', 'Unknown')}", reinforce=reinforce)

def parse_creature_item(item_id, source="unknown"):
    url = f"{BASE_URL}/items/{item_id}?apikey={API_KEY}"
    res = requests.get(url).json()
    stats = res.get("itemStatus", [])
    for stat in stats:
        parse_stat_entry(stat, source=source)

def analyze_creature():
    url = f"{BASE_URL}/servers/{SERVER}/characters/{CHARACTER_ID}/equip/creature?apikey={API_KEY}"
    res = requests.get(url).json()
    creature = res.get("creature", {})
    if not creature:
        return

    if creature.get("itemId"):
        parse_creature_item(creature["itemId"], source=f"[크리쳐] {creature.get('itemName')}")

    for artifact in creature.get("artifact", []):
        if artifact.get("itemId"):
            parse_creature_item(artifact["itemId"], source=f"[아티팩트] {artifact.get('itemName')}")

def analyze_aura_avatar():
    url = f"{BASE_URL}/servers/{SERVER}/characters/{CHARACTER_ID}/equip/avatar?apikey={API_KEY}"
    res = requests.get(url).json()
    for avatar in res.get("avatar", []):
        if avatar.get("slotId") == "AURORA":
            item_id = avatar.get("itemId")
            if item_id:
                parse_item_stats(item_id)

def analyze_insignia():
    url = f"{BASE_URL}/servers/{SERVER}/characters/{CHARACTER_ID}/equip/flag?apikey={API_KEY}"
    res = requests.get(url).json()
    flag = res.get("flag", {})
    if not flag:
        return

    if flag.get("itemId"):
        parse_creature_item(flag["itemId"], source=f"[인시그니아] {flag.get('itemName')}")

    for stat in flag.get("reinforceStatus", []):
        parse_stat_entry(stat, source=f"[인시그니아 강화] {flag.get('itemName')}")

    for gem in flag.get("gems", []):
        if gem.get("itemId"):
            parse_creature_item(gem["itemId"], source=f"[인시그니아 젬] {gem.get('itemName')}")
            
def analyze_setitem(res):
    global overall_dmg_mul, cd_reduction_mul, damage_value_sum, atk_amp_sum, cd_recovery_sum, elemental_dmg_sum
    setItemInfoList = res.get("setItemInfo", [])
    if not setItemInfoList:
        return 

    setItemInfo = setItemInfoList[0]
    setItemName = setItemInfo.get("setItemName")
    setItemRarityName = setItemInfo.get("setItemRarityName")
    setItemActive = setItemInfo.get("active")
    setItemStat = setItemActive.get("status", [])
    
    stat = setItemInfo
    
    if is_paradise_set(setItemName):
        reinforce_acc = 0
        reinforce_total = 0
        overall_damage = 0
        
        #Calc reinforce overall damage
        for item in res.get("equipment", []):
            if "weapon" in item.get("slotName").lower():
                continue
            if any(x in item.get("slotName").lower() for x in ["ring", "bracelet", "necklace"]):
                reinforce_acc += item.get("reinforce", 0)
            reinforce_total += item.get("reinforce", 0)
            
        if "unique" in setItemRarityName.lower():
            max_reinforce_acc_stack = 7
        elif "legendary" in setItemRarityName.lower():
            max_reinforce_acc_stack = 12
        else:
            max_reinforce_acc_stack = 12
            max_reinforce_total_stack = 2
            
        reinforce_acc_overall_damage = min(math.floor(reinforce_acc / 3), max_reinforce_acc_stack)
        reinforce_total_overall_damage = min(math.floor((reinforce_total - 110) / 11), max_reinforce_total_stack) * 2
        
        reinforce_overall_damage = (1 + reinforce_acc_overall_damage / 100) * (1 + reinforce_total_overall_damage / 100)

        overall_dmg_mul *= reinforce_overall_damage
            
        overall_dmg_mul *= (1 + overall_damage / 100)
        print(f"🔥[OVERALL] [세트] {setItemName} -> 악세 강화: {reinforce_acc}, 무기 제외 총 강화: {reinforce_total} -> x{reinforce_overall_damage:.4f} -> Total : {overall_dmg_mul * 100:.1f}%")
        
        #Trim CDR part
        filtered_status = [s for s in setItemStat if s.get("name") != "Skill Cooldown Reduction"]
        setItemStat = filtered_status

    elif is_cleansing_set(setItemName):
        overall_damage = 0
        if any(x in setItemRarityName.lower() for x in ["legendary", "epic", "primeval"]):
            if(CLEANSING_CDR):
                for stat in setItemStat:
                    if stat.get("name") == "Skill Cooldown Reduction":
                        stat["value"] = "55%"
                        break
            else:
                overall_damage = 17.5
                for stat in setItemStat:
                    if stat.get("name") == "Skill Cooldown Reduction":
                        stat["value"] = "30%"
                        break
                
        overall_dmg_mul *= (1 + overall_damage / 100)
        print(f"🔥[OVERALL] [세트] {setItemName} -> +{overall_damage:.1f}% Overall (쿨감 {CLEANSING_CDR}) -> Total : {overall_dmg_mul * 100:.1f}%")
        
    elif is_ethereal_set(setItemName):
        overall_damage = 0
        orb_count = 0
        
        if "unique" in setItemRarityName.lower():
            orb_count = 1
        elif "legendary" in setItemRarityName.lower():
            orb_count = 2
        elif "epic" in setItemRarityName.lower():
            orb_count = 3
        elif "primeval" in setItemRarityName.lower():
            orb_count = 4
        overall_damage = 10 * orb_count
        

        overall_dmg_mul *= (1 + overall_damage / 100)
        print(f"🔥[OVERALL] [세트] {setItemName} -> +{overall_damage:.1f}% Overall -> Total : {overall_dmg_mul * 100:.1f}%")
        
    elif is_dragon_set(setItemName):
        if "epic" in setItemRarityName.lower():
            overall_damage = 1.5
        elif "primeval" in setItemRarityName.lower():
            overall_damage = 3
        

        overall_dmg_mul *= (1 + overall_damage / 100)
        print(f"🔥[OVERALL] [세트] {setItemName} -> +{overall_damage:.1f}% Overall -> Total : {overall_dmg_mul * 100:.1f}%")
        
    elif is_serendipity_set(setItemName):
        overall_damage = 0
        elemental_dmg = 0
        expected_overall_damage = []
        expected_overall_damage_short = 1.5
        expected_overall_damage_long = 4
        expected_overall_damage_random = 3
        expected_overall_damage_all = 10
        
        if "unique" in setItemRarityName.lower():
            overall_damage = 3
            expected_overall_damage.append(expected_overall_damage_long)
        elif "legendary" in setItemRarityName.lower():
            overall_damage = 3
            elemental_dmg = 33
            expected_overall_damage.append(expected_overall_damage_short)
            expected_overall_damage.append(expected_overall_damage_long)
        elif "epic" in setItemRarityName.lower():
            overall_damage = 3
            elemental_dmg = 33
            expected_overall_damage.append(expected_overall_damage_long)
            expected_overall_damage.append(expected_overall_damage_all)
        elif "primeval" in setItemRarityName.lower():
            overall_damage = 3
            elemental_dmg = 33
            expected_overall_damage.append(expected_overall_damage_long)
            expected_overall_damage.append(expected_overall_damage_random)
            expected_overall_damage.append(expected_overall_damage_all)
            
        elemental_dmg_sum["All"] += elemental_dmg
        total_expected_overall_dmg = math.prod([1 + x / 100 for x in expected_overall_damage])

        overall_dmg_mul *= (1 + overall_damage / 100)
        overall_dmg_mul *= (1 + total_expected_overall_dmg / 100)
        print(f"🔥[OVERALL] [세트] {setItemName} 기본: +{overall_damage}%, 기대값: x{total_expected_overall_dmg:.4f} -> Total : {overall_dmg_mul * 100:.1f}%")
        
    elif is_pack_set(setItemName):
        overall_damage = 0
        if "unique" in setItemRarityName.lower():
            overall_damage = 5
        elif "legendary" in setItemRarityName.lower():
            overall_damage = 6
        elif "epic" in setItemRarityName.lower():
            overall_damage = 7
        elif "primeval" in setItemRarityName.lower():
            overall_damage = 8
            

        overall_dmg_mul *= (1 + overall_damage / 100)
        print(f"🔥[OVERALL] [세트] {setItemName} -> +{overall_damage:.1f}% Overall -> Total : {overall_dmg_mul * 100:.1f}%")
        
    for stat in setItemStat:
        parse_stat_entry(stat, source=f"[세트효과] {setItemName}")
    

def analyze_character_equipment():
    url = f"{BASE_URL}/servers/{SERVER}/characters/{CHARACTER_ID}/equip/equipment?apikey={API_KEY}"
    res = requests.get(url).json()

    for item in res.get("equipment", []):
        if item.get("slotName") == "Secondary Weapon":
            continue

        item_id = item.get("itemId")
        item_name = item.get("itemName")
        
        parse_item_stats(item_id)
        parse_fusion_options(item)

        for stat in item.get("tune", {}).get("status", []):
            parse_stat_entry(stat, source=f"[튠] {item.get('itemName')}")

        for stat in item.get("enchant", {}).get("status", []):
            parse_stat_entry(stat, source=f"[마부] {item_name}")

    analyze_setitem(res)

def print_results():
    print(f"\n\U0001f3af 최종 계산 결과")
    print(f"✅ Overall Damage Multiplier: {overall_dmg_mul * 100:.4f}%")
    print(f"✅ Cooldown Reduction Multiplier: x{(1 - cd_reduction_mul) * 100:.4f}")
    print(f"✅ Damage Value Sum: {damage_value_sum:.2f}")
    print(f"✅ Atk. Amp Sum: {atk_amp_sum:.2f}")
    print(f"✅ Cooldown Recovery Sum: {cd_recovery_sum:.2f}")
    print("✅ Elemental Damage Sums:")
    for key, val in elemental_dmg_sum.items():
        print(f"   - {key}: {val:.2f}")

if __name__ == "__main__":
    analyze_character_equipment()
    analyze_aura_avatar()
    analyze_creature()
    analyze_insignia()
    print_results()
