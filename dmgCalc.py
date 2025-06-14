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

def parse_explain_detail(text, source="unknown"):
    global overall_dmg_mul, cd_reduction_mul, damage_value_sum, atk_amp_sum, cd_recovery_sum, elemental_dmg_sum

    lines = text.lower().split("\n")
    for line in lines:
        if "all atk." in line:
            match = re.search(r"\+([\d.]+)%", line)
            if match:
                val = float(match.group(1))
                atk_amp_sum += val
                continue

        match = re.search(r"(overall|skill|attack)[^\n]*\+([\d.]+)%", line)
        if match:
            val = float(match.group(2)) / 100
            overall_dmg_mul *= (1 + val)
            continue

        match = re.search(r"cooldown[^\n\-+]*[-–−+]([\d.]+)%", line)
        if match:
            val = float(match.group(1)) / 100
            cd_reduction_mul *= (1 - val)
            continue

        match = re.search(r"damage value\s*\+([\d.]+)", line)
        if match:
            val = float(match.group(1))
            damage_value_sum += val
            print(f"📅 Damage Value +{val:.1f} → total {damage_value_sum:.2f} ({source} / \"{line.strip()}\")")
            continue

        match = re.search(r"attack amplification\s*\+([\d.]+)", line)
        if match:
            atk_amp_sum += float(match.group(1))
            continue

        match = re.search(r"cooldown recovery\s*\+([\d.]+)%", line)
        if match:
            cd_recovery_sum += float(match.group(1))
            continue

        for key, element in ELEMENT_KEYWORDS.items():
            if key in line:
                match = re.search(r"\+([\d.]+)", line)
                if match:
                    val = float(match.group(1))
                    elemental_dmg_sum[element] += val
                    print(f"🌟 Element {element} +{val:.1f} → total {elemental_dmg_sum[element]:.2f} ({source} / \"{line.strip()}\")")

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
        return
    elif "damage value" in name:
        damage_value_sum += value
        print(f"📅 Damage Value +{value:.1f} → total {damage_value_sum:.2f} ({source or 'unknown'} / stat: \"{stat['name']}\")")
    elif "attack amplification" in name or "atk. amp" in name:
        atk_amp_sum += value
    elif "cooldown reduction" in name:
        cd_reduction_mul *= (1 - value / 100)
    elif "cooldown recovery" in name:
        cd_recovery_sum += value
    else:
        for key, element in ELEMENT_KEYWORDS.items():
            if key in name:
                elemental_dmg_sum[element] += value
                print(f"🌟 Element {element} +{value:.1f} → total {elemental_dmg_sum[element]:.2f} ({source or 'unknown'} / stat: \"{stat['name']}\")")

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
    print(f"\U0001f9fe 분석 대상 장비 수: {len(res.get('equipment', []))}")

    for item in res.get("equipment", []):
        if item.get("slotName") == "Secondary Weapon":
            continue

        item_id = item.get("itemId")
        item_name = item.get("itemName")

        parse_item_stats(item_id)
        parse_fusion_options(item)

        for stat in item.get("enchant", {}).get("status", []):
            parse_stat_entry(stat, source=f"[마부] {item_name}")

    for setitem in res.get("setItemInfo", []):
        set_name = setitem.get("setItemName", "Unknown Set")
        print(f"[DEBUG] 세트효과 탐지됨: {set_name}")
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