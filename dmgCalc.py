import requests
import re

API_KEY = "sRngDaw09CPuVYcpzfL1VG5F8ozrWnQQ"
BASE_URL = "https://api.dfoneople.com/df"
SERVER = "cain"
CHARACTER_ID = "479957cad33e18e35d5ae25d3a4a688c"

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

def should_ignore_set_cd(set_name):
    return "paradise" in set_name.lower() or "gold" in set_name.lower()

def is_cleansing_set(set_name):
    return "cleansing" in set_name.lower()

def is_ethereal_set(set_name):
    return "ethereal" in set_name.lower()

def is_dragon_set(set_name):
    return "dragon" in set_name.lower()

def parse_explain_detail(text, source="unknown"):
    global overall_dmg_mul, cd_reduction_mul, damage_value_sum, atk_amp_sum, cd_recovery_sum, elemental_dmg_sum

    if "세트효과" in source and is_ethereal_set(source):
        max_orbs = 0
        dmg_per_orb = 0

        max_orb_match = re.search(r"max orb charges\D*(\d+)", text.lower())
        if max_orb_match:
            max_orbs = int(max_orb_match.group(1))

        dmg_match = re.search(r"overall damage \+(\d+)% per orb", text.lower())
        if dmg_match:
            dmg_per_orb = float(dmg_match.group(1)) / 100

        if max_orbs and dmg_per_orb:
            boost = (1 + dmg_per_orb * max_orbs)
            print(f"[ETHEREAL] max_orbs={max_orbs}, dmg_per_orb={dmg_per_orb}, boost={boost:.4f}")
            overall_dmg_mul *= boost
        return

    if "세트효과" in source and is_dragon_set(source):
        dmg_match = re.search(r"overall damage \+(\d+)%", text.lower())
        if dmg_match:
            val = float(dmg_match.group(1)) / 100
            print(f"[DRAGON] Overall Damage +{val*100}% -> x{1+val:.4f}")
            overall_dmg_mul *= (1 + val)
        return

    lines = text.lower().split("\n")
    for line in lines:
        if "all atk." in line:
            match = re.search(r"\+([\d.]+)%", line)
            if match:
                val = float(match.group(1))
                atk_amp_sum += val
                continue
            
        match = re.search(r"overall damage\s*\+([\d.]+)%", line)
        
        if match:
            if "세트효과" in source and is_cleansing_set(source):
                continue
            val = float(match.group(1)) / 100
            print(f"[EXPLAIN] {source} -> +{val*100:.1f}% Overall -> x{1+val:.4f}")
            overall_dmg_mul *= (1 + val)
            continue

        match = re.search(r"cooldown[^\n\-+]*[-–−+]([\d.]+)%", line)
        if match:
            if "세트효과" in source and is_cleansing_set(source):
                cd_reduction_mul *= (1 - 0.55)
            else:
                val = float(match.group(1)) / 100
                cd_reduction_mul *= (1 - val)
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

    if "overall damage" in name:
        if source and "세트효과" in source and is_cleansing_set(source):
            return
        print(f"[STAT] {source} -> +{value:.1f}% Overall -> x{1 + value/100:.4f}")
        overall_dmg_mul *= (1 + value / 100)
    elif "damage value" in name:
        damage_value_sum += value
    elif "attack amplification" in name or "atk. amp" in name:
        atk_amp_sum += value
    elif "cooldown reduction" in name:
        if source and "세트효과" in source:
            if should_ignore_set_cd(source):
                return
            if is_cleansing_set(source):
                cd_reduction_mul *= (1 - 0.55)
                return
        cd_reduction_mul *= (1 - value / 100)
    elif "cooldown recovery" in name:
        cd_recovery_sum += value
    else:
        for key, element in ELEMENT_KEYWORDS.items():
            if key in name:
                elemental_dmg_sum[element] += value

    # 무기 튠 확인
    if source and "튠" in source:
        if "overall damage" in name:
            print(f"[TUNE] {source} -> +{value:.1f}% Overall -> x{1 + value/100:.4f}")
            overall_dmg_mul *= (1 + value / 100)
                
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
            parse_explain_detail(detail, source=f"[융합석:조회] {upgrade_info.get('itemName', 'Unknown')}")

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

    for setitem in res.get("setItemInfo", []):
        set_name = setitem.get("setItemName", "Unknown Set")
        for stat in setitem.get("active", {}).get("status", []):
            parse_stat_entry(stat, source=f"[세트효과] {set_name}")

def print_results():
    print(f"\n\U0001f3af 최종 계산 결과")
    print(f"✅ Overall Damage Multiplier: x{overall_dmg_mul:.4f}")
    print(f"✅ Cooldown Reduction Multiplier: x{cd_reduction_mul:.4f}")
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
