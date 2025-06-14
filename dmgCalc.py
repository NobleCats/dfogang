import requests
import re
import math

API_KEY = "sRngDaw09CPuVYcpzfL1VG5F8ozrWnQQ"
BASE_URL = "https://api.dfoneople.com/df"
SERVER = "cain"
CHARACTER_ID = "d25349b117002ecfbe3fb50c572f65dc"
CLEANSING_CDR = True
WEAPON_CDR = True

# 누적 스탯 초기화
overall_dmg_mul = 1.0
cd_reduction_mul = 1.0
damage_value_sum = 0.0
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

def engrave_cal(option=None):
    if not isinstance(option, list):
        return 0

    for entry in option:
        if not isinstance(entry, dict):
            continue

        engraves = entry.get("engrave")

        # 🛠 engrave가 dict 하나일 경우 → 리스트처럼 처리
        if isinstance(engraves, dict):
            engraves = [engraves]
        elif engraves is None:
            engraves = []

        for engrave in engraves:
            color = engrave.get("color", "")
            value = engrave.get("value", 0)

            if "gold" in color:
                if value == 1:
                    return 0.3
                elif value == 2:
                    return 0.5
                elif value == 3:
                    return 1.5

    return 0

def reinforce_calc(reinforce, amplificationName, slotName, source=""):
    base_overall_dmg = 0.2
    under15 = 0.3
    over15 = 0.2
    total_overall_dmg = 0
    
    if amplificationName == None:
        if slotName == "Earrings" or slotName == "Weapon":
            if reinforce < 12:
                return
            else:
                total_overall_dmg += base_overall_dmg * 2 + under15 * min(2, (reinforce - 12))
                total_overall_dmg += over15 * max(0, (reinforce - 15))
        else:
            return
    else:
        if reinforce < 10:
            return
        else:
            total_overall_dmg += base_overall_dmg + base_overall_dmg * min(1, (reinforce - 10))
            total_overall_dmg += under15 * max(0, min(2, (reinforce - 11)))
            total_overall_dmg += over15 * max(0, (reinforce - 13))

    overall_dmg_calc(total_overall_dmg, source)
    
def overall_dmg_calc(overall_dmg, source="unknown"):
    if overall_dmg == 0: return
    global overall_dmg_mul
    
    print(f"[OVERALL]\t+{overall_dmg:.1f}%\tfrom {source}")
    print(f"-> Total : {overall_dmg_mul * 100:.1f}% -> ", end="")
    overall_dmg_mul *= (1 + overall_dmg * 0.01)
    print(f"{overall_dmg_mul * 100:.1f}%")
    
def cooldown_reduction_calc(cooldown_reduction, source="unknown"):
    if cooldown_reduction == 0: return
    global cd_reduction_mul
    
    print(f"[COOLDOWN]\t+{cooldown_reduction:.1f}%\tfrom {source}")
    print(f"-> Total : {cd_reduction_mul * 100:.1f}% -> ", end="")
    cd_reduction_mul *= (1 - cooldown_reduction / 100)
    print(f"{cooldown_reduction * 100:.1f}%")


def parse_explain_detail(text, source="unknown", reinforce=None, option=None):
    global overall_dmg_mul, cd_reduction_mul, damage_value_sum, cd_recovery_sum, elemental_dmg_sum

    lines = text.lower().split("\n")
    
    if "[FUSION_LEG]" in source:
        option = None
    
    for line in lines:
        current_ovarall_dmg = 0
        if "sensory satisfaction" in line and reinforce is not None:
            bonus = min(max(reinforce - 10, 0), 2)
            overall_dmg_calc(bonus, source)
            return
            

        match = re.search(r"(\d+(?:\.\d+)?)% chance.*?skill atk\. \+(\d+(?:\.\d+)?)%", line)
        if match:
            chance = float(match.group(1)) / 100
            bonus = float(match.group(2))
            expected = chance * bonus
            current_ovarall_dmg = engrave_cal(option)
            current_ovarall_dmg += expected

        match = re.search(r"(\d+(?:\.\d+)?)% chance.*?reset.*cooldown", line)
        if match:
            chance = float(match.group(1)) / 100
            boost = 1 / (1 - chance)
            current_ovarall_dmg = engrave_cal(option)
            current_ovarall_dmg += (boost - 1) * 100


        match = re.search(r"overall damage[^\n\d]*\+([\d.]+)%", line)
        if match:
            val = float(match.group(1))
            current_ovarall_dmg = engrave_cal(option)
            current_ovarall_dmg += val

        match = re.search(r"damage value\s*\+([\d.]+)", line)
        if match:
            val = float(match.group(1))
            damage_value_sum += val

        match = re.search(r"cooldown recovery\s*\+([\d.]+)%", line)
        if match:
            val = float(match.group(1))
            cd_recovery_sum += val
            
        match = re.search(r"cooldown recovery\s*\+([\d.]+)%", line)
        if match:
            val = float(match.group(1))
            cd_recovery_sum += val
            
        match = re.search(r"cooldown reduction\s*\+([\d.]+)%", line)
        if match:
            value = float(match.group(1))
            cooldown_reduction_calc(value, source)
            
        match = re.search(r"skill cooldown\s*\-([\d.]+)%", line)
        if match:
            value = float(match.group(1))
            cooldown_reduction_calc(value, source)

        for key, element in ELEMENT_KEYWORDS.items():
            if key in line:
                match = re.search(r"\+([\d.]+)", line)
                if match:
                    val = float(match.group(1))
                    elemental_dmg_sum[element] += val
                    
        overall_dmg_calc(current_ovarall_dmg, source)
                    


def parse_stat_entry(stat, source=None):
    global overall_dmg_mul, cd_reduction_mul, damage_value_sum, cd_recovery_sum, elemental_dmg_sum

    name = stat.get("name", "").lower()
        
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
    elif "cooldown reduction" in name:
        cooldown_reduction_calc(value, source)
    elif "cooldown recovery" in name:
        cd_recovery_sum += value
    elif "overall damage" in name:
        overall_dmg_calc(value, source)
    else:
        for key, element in ELEMENT_KEYWORDS.items():
            if key in name:
                elemental_dmg_sum[element] += value

def parse_explain(explain, source=None):
    global overall_dmg_mul, cd_reduction_mul, damage_value_sum, cd_recovery_sum, elemental_dmg_sum

    explain_txt = explain.lower()

    # 어떤 효과인지 먼저 판단
    if "overall damage" in explain_txt:
        match = re.search(r"overall damage\s*\+([\d.]+)%", explain_txt)
        if match:
            value = float(match.group(1))
            overall_dmg_calc(value, source)
    elif "damage value" in explain_txt:
        match = re.search(r"damage value\s*\+([\d.]+)", explain_txt)
        if match:
            value = float(match.group(1))
            damage_value_sum += value
    elif "cooldown reduction" in explain_txt:
        match = re.search(r"cooldown reduction\s*\+([\d.]+)%", explain_txt)
        if match:
            value = float(match.group(1))
            cooldown_reduction_calc(value, source)
    elif "cooldown recovery" in explain_txt:
        match = re.search(r"cooldown recovery\s*\+([\d.]+)%", explain_txt)
        if match:
            value = float(match.group(1))
            cd_recovery_sum += value
    else:
        for key, element in ELEMENT_KEYWORDS.items():
            if key in explain_txt:
                match = re.search(rf"{key}[^+]*\+([\d.]+)", explain_txt)
                if match:
                    value = float(match.group(1))
                    elemental_dmg_sum[element] += value

                
def parse_item_stats(item_id):
    url = f"{BASE_URL}/items/{item_id}?apikey={API_KEY}"
    res = requests.get(url).json()
    item_name = res.get("itemName", item_id)
    stats = res.get("itemStatus", [])
    itemBuff = res.get("itemBuff", {})
    explain = itemBuff.get("explain", "")
    
    if "skill cooldown" in explain.lower():
        stats = [stat for stat in stats if stat.get("name") != "Skill Cooldown Reduction"]
    
    for stat in stats:
        parse_stat_entry(stat, source=f"[ITEM] {item_name}")
        
    detail = res.get("itemExplainDetail", "")
    if detail:
        parse_explain_detail(detail, source=f"[ITEM_DETAIL] {item_name}")

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
                parse_explain_detail(detail, source=f"[FUSION_LEG] {item_name}", option=options)
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
            parse_explain_detail(detail, source=f"[FUSIONSTONE] {upgrade_info.get('itemName', 'Unknown')}", reinforce=reinforce,  option=options)

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
        parse_creature_item(creature["itemId"], source=f"[CREATURE] {creature.get('itemName')}")

    for artifact in creature.get("artifact", []):
        if artifact.get("itemId"):
            parse_creature_item(artifact["itemId"], source=f"[ARTIFACT] {artifact.get('itemName')}")

def analyze_aura_avatar():
    url = f"{BASE_URL}/servers/{SERVER}/characters/{CHARACTER_ID}/equip/avatar?apikey={API_KEY}"
    res = requests.get(url).json()
    for avatar in res.get("avatar", []):
        if avatar.get("slotName") == "Aura Avatar":
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
        parse_creature_item(flag["itemId"], source=f"[INSIGNIA] {flag.get('itemName')}")

    for stat in flag.get("reinforceStatus", []):
        parse_stat_entry(stat, source=f"[INSIGNIA REINFORCE] {flag.get('itemName')}")

    for gem in flag.get("gems", []):
        if gem.get("itemId"):
            parse_creature_item(gem["itemId"], source=f"[INSIGNIA GEM] {gem.get('itemName')}")
            
def analyze_setitem(res):
    global overall_dmg_mul, cd_reduction_mul, damage_value_sum, cd_recovery_sum, elemental_dmg_sum
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
        

        overall_dmg_calc(reinforce_acc_overall_damage, setItemName)
        overall_dmg_calc(reinforce_total_overall_damage, setItemName)
        overall_dmg_calc(overall_damage, setItemName)
        
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
                
        overall_dmg_calc(overall_damage, setItemName)
        
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
        

        overall_dmg_calc(overall_damage, setItemName)
        
    elif is_dragon_set(setItemName):
        if "epic" in setItemRarityName.lower():
            overall_damage = 1.5
        elif "primeval" in setItemRarityName.lower():
            overall_damage = 3
        

        overall_dmg_calc(overall_damage, setItemName)
        
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

        overall_dmg_calc(overall_damage, setItemName)
        overall_dmg_calc(total_expected_overall_dmg, setItemName)
        
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
            
        overall_dmg_calc(overall_damage, setItemName)
        
    for stat in setItemStat:
        parse_stat_entry(stat, source=f"[SET OPTION] {setItemName}")
    

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
            parse_stat_entry(stat, source=f"[WEAPON] {item.get('itemName')}")

        for stat in item.get("enchant", {}).get("status", []):
            parse_stat_entry(stat, source=f"[ENCHANT] {item_name}")
            
        explain = item.get("enchant", {}).get("explain", "")
        parse_explain(explain, source=f"[ENCHANT] {item_name}" )
        
        amplificationName = item.get("amplificationName")
        slotName = item.get("slotName")
        reinforce = item.get("reinforce")
        
        reinforce_calc(reinforce=reinforce, amplificationName=amplificationName, slotName=slotName, source=f"[REINFORCE]")

    analyze_setitem(res)

def print_results():
    
    url = f"{BASE_URL}/servers/{SERVER}/characters/{CHARACTER_ID}/status/?apikey={API_KEY}"
    res = requests.get(url).json()
    status = res.get("status", [])
    atk_amp = next((s["value"] for s in status if s["name"] == "Atk. Amp."), None)
    
    print(f"[RESULT]")
    print(f"Overall Damage : \t{overall_dmg_mul * 100:.4f}%")
    print(f"Cooldown Reduction : \t{(1 - cd_reduction_mul) * 100:.4f}%")
    print(f"Damage Value : \t\t{damage_value_sum:.2f}")
    print(f"Atk. Amp : \t\t{atk_amp:.2f}")
    print(f"Cooldown Recovery : \t{cd_recovery_sum:.2f}")
    print("Elemental Damage :")
    for key, val in elemental_dmg_sum.items():
        print(f"   - {key}: {val:.2f}")

if __name__ == "__main__":
    analyze_character_equipment()
    analyze_aura_avatar()
    analyze_creature()
    analyze_insignia()
    print_results()
