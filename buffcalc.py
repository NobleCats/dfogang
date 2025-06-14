import json

enchantress_buff_table = {
    1: {"atk": 34, "stat": 131},
    2: {"atk": 35, "stat": 140},
    3: {"atk": 37, "stat": 149},
    4: {"atk": 38, "stat": 158},
    5: {"atk": 39, "stat": 167},
    6: {"atk": 41, "stat": 175},
    7: {"atk": 42, "stat": 184},
    8: {"atk": 43, "stat": 193},
    9: {"atk": 45, "stat": 202},
    10: {"atk": 46, "stat": 211},
    11: {"atk": 47, "stat": 220},
    12: {"atk": 49, "stat": 229},
    13: {"atk": 50, "stat": 238},
    14: {"atk": 51, "stat": 247},
    15: {"atk": 53, "stat": 256},
    16: {"atk": 54, "stat": 264},
    17: {"atk": 55, "stat": 273},
    18: {"atk": 57, "stat": 282},
    19: {"atk": 58, "stat": 291},
    20: {"atk": 60, "stat": 300},
    21: {"atk": 61, "stat": 309},
    22: {"atk": 62, "stat": 318},
    23: {"atk": 64, "stat": 327},
    24: {"atk": 65, "stat": 336},
    25: {"atk": 66, "stat": 345},
    26: {"atk": 68, "stat": 353},
    27: {"atk": 69, "stat": 362},
    28: {"atk": 70, "stat": 371},
    29: {"atk": 72, "stat": 380},
    30: {"atk": 73, "stat": 389},
    31: {"atk": 74, "stat": 398},
    32: {"atk": 76, "stat": 407},
    33: {"atk": 77, "stat": 416},
    34: {"atk": 78, "stat": 425},
    35: {"atk": 80, "stat": 434},
    36: {"atk": 81, "stat": 442},
    37: {"atk": 82, "stat": 451},
    38: {"atk": 84, "stat": 460},
    39: {"atk": 85, "stat": 469},
    40: {"atk": 87, "stat": 478}
}
muse_buff_table = {
    1: {"atk": 40, "stat": 162},
    2: {"atk": 42, "stat": 173},
    3: {"atk": 44, "stat": 186},
    4: {"atk": 46, "stat": 196},
    5: {"atk": 47, "stat": 207},
    6: {"atk": 49, "stat": 217},
    7: {"atk": 51, "stat": 227},
    8: {"atk": 52, "stat": 239},
    9: {"atk": 54, "stat": 249},
    10: {"atk": 55, "stat": 262},
    11: {"atk": 56, "stat": 272},
    12: {"atk": 58, "stat": 283},
    13: {"atk": 60, "stat": 295},
    14: {"atk": 61, "stat": 306},
    15: {"atk": 63, "stat": 318},
    16: {"atk": 64, "stat": 328},
    17: {"atk": 65, "stat": 338},
    18: {"atk": 67, "stat": 350},
    19: {"atk": 70, "stat": 360},
    20: {"atk": 72, "stat": 372},
    21: {"atk": 73, "stat": 382},
    22: {"atk": 74, "stat": 394},
    23: {"atk": 76, "stat": 406},
    24: {"atk": 78, "stat": 416},
    25: {"atk": 80, "stat": 428},
    26: {"atk": 82, "stat": 437},
    27: {"atk": 83, "stat": 448},
    28: {"atk": 84, "stat": 460},
    29: {"atk": 86, "stat": 471},
    30: {"atk": 88, "stat": 482},
    31: {"atk": 89, "stat": 493},
    32: {"atk": 92, "stat": 503},
    33: {"atk": 93, "stat": 516},
    34: {"atk": 94, "stat": 527},
    35: {"atk": 96, "stat": 539},
    36: {"atk": 98, "stat": 548},
    37: {"atk": 99, "stat": 559},
    38: {"atk": 101, "stat": 570},
    39: {"atk": 102, "stat": 581},
    40: {"atk": 104, "stat": 593}
}
msader_aura_table = {
    1: {"stat": 40},
    2: {"stat": 48},
    3: {"stat": 58},
    4: {"stat": 67},
    5: {"stat": 77},
    6: {"stat": 87},
    7: {"stat": 98},
    8: {"stat": 109},
    9: {"stat": 120},
    10: {"stat": 133},
    11: {"stat": 144},
    12: {"stat": 157},
    13: {"stat": 171},
    14: {"stat": 184},
    15: {"stat": 198},
    16: {"stat": 212},
    17: {"stat": 226},
    18: {"stat": 242},
    19: {"stat": 258},
    20: {"stat": 273},
    21: {"stat": 290},
    22: {"stat": 306},
    23: {"stat": 323},
    24: {"stat": 341},
    25: {"stat": 359},
    26: {"stat": 378},
    27: {"stat": 397},
    28: {"stat": 416},
    29: {"stat": 436},
    30: {"stat": 456},
    31: {"stat": 476},
    32: {"stat": 498},
    33: {"stat": 518},
    34: {"stat": 541},
    35: {"stat": 562},
    36: {"stat": 586},
    37: {"stat": 609},
    38: {"stat": 632},
    39: {"stat": 654},
    40: {"stat": 678},
    41: {"stat": 702},
    42: {"stat": 726},
    43: {"stat": 750},
    44: {"stat": 774},
    45: {"stat": 798},
    46: {"stat": 823},
    47: {"stat": 848},
    48: {"stat": 873},
    49: {"stat": 898},
    50: {"stat": 923}
}
msader_buff_table = {
    1: {"atk": 41, "stat": 161},
    2: {"atk": 42, "stat": 171},
    3: {"atk": 44, "stat": 181},
    4: {"atk": 45, "stat": 193},
    5: {"atk": 46, "stat": 204},
    6: {"atk": 48, "stat": 214},
    7: {"atk": 50, "stat": 224},
    8: {"atk": 51, "stat": 236},
    9: {"atk": 53, "stat": 247},
    10: {"atk": 55, "stat": 258},
    11: {"atk": 56, "stat": 269},
    12: {"atk": 57, "stat": 279},
    13: {"atk": 59, "stat": 291},
    14: {"atk": 60, "stat": 301},
    15: {"atk": 62, "stat": 313},
    16: {"atk": 64, "stat": 322},
    17: {"atk": 65, "stat": 333},
    18: {"atk": 67, "stat": 345},
    19: {"atk": 69, "stat": 356},
    20: {"atk": 71, "stat": 366},
    21: {"atk": 72, "stat": 377},
    22: {"atk": 74, "stat": 389},
    23: {"atk": 76, "stat": 399},
    24: {"atk": 77, "stat": 410},
    25: {"atk": 79, "stat": 421},
    26: {"atk": 81, "stat": 431},
    27: {"atk": 81, "stat": 442},
    28: {"atk": 83, "stat": 454},
    29: {"atk": 85, "stat": 464},
    30: {"atk": 86, "stat": 474},
    31: {"atk": 88, "stat": 486},
    32: {"atk": 90, "stat": 497},
    33: {"atk": 91, "stat": 508},
    34: {"atk": 93, "stat": 518},
    35: {"atk": 94, "stat": 531},
    36: {"atk": 95, "stat": 540},
    37: {"atk": 97, "stat": 551},
    38: {"atk": 99, "stat": 562},
    39: {"atk": 100, "stat": 572},
    40: {"atk": 103, "stat": 584}
}
fsader_buff_table = {
    1: {"atk": 39, "stat": 154},
    2: {"atk": 41, "stat": 164},
    3: {"atk": 43, "stat": 176},
    4: {"atk": 44, "stat": 186},
    5: {"atk": 45, "stat": 197},
    6: {"atk": 47, "stat": 206},
    7: {"atk": 49, "stat": 216},
    8: {"atk": 50, "stat": 227},
    9: {"atk": 52, "stat": 237},
    10: {"atk": 53, "stat": 249},
    11: {"atk": 54, "stat": 259},
    12: {"atk": 56, "stat": 269},
    13: {"atk": 58, "stat": 280},
    14: {"atk": 59, "stat": 290},
    15: {"atk": 61, "stat": 302},
    16: {"atk": 62, "stat": 311},
    17: {"atk": 63, "stat": 321},
    18: {"atk": 65, "stat": 332},
    19: {"atk": 67, "stat": 342},
    20: {"atk": 69, "stat": 353},
    21: {"atk": 70, "stat": 363},
    22: {"atk": 71, "stat": 374},
    23: {"atk": 73, "stat": 385},
    24: {"atk": 75, "stat": 395},
    25: {"atk": 77, "stat": 406},
    26: {"atk": 79, "stat": 415},
    27: {"atk": 80, "stat": 425},
    28: {"atk": 81, "stat": 437},
    29: {"atk": 83, "stat": 447},
    30: {"atk": 85, "stat": 458},
    31: {"atk": 86, "stat": 468},
    32: {"atk": 88, "stat": 478},
    33: {"atk": 89, "stat": 489},
    34: {"atk": 90, "stat": 500},
    35: {"atk": 92, "stat": 511},
    36: {"atk": 94, "stat": 520},
    37: {"atk": 95, "stat": 530},
    38: {"atk": 97, "stat": 541},
    39: {"atk": 98, "stat": 551},
    40: {"atk": 100, "stat": 563}
}

common_aura_table = {
    1: {"stat": 14},
    2: {"stat": 37},
    3: {"stat": 59},
    4: {"stat": 82},
    5: {"stat": 104},
    6: {"stat": 127},
    7: {"stat": 149},
    8: {"stat": 172},
    9: {"stat": 194},
    10: {"stat": 217},
    11: {"stat": 239},
    12: {"stat": 262},
    13: {"stat": 284},
    14: {"stat": 307},
    15: {"stat": 329},
    16: {"stat": 352},
    17: {"stat": 374},
    18: {"stat": 397},
    19: {"stat": 419},
    20: {"stat": 442},
    21: {"stat": 464},
    22: {"stat": 487},
    23: {"stat": 509},
    24: {"stat": 532},
    25: {"stat": 554},
    26: {"stat": 577},
    27: {"stat": 599},
    28: {"stat": 622},
    29: {"stat": 644},
    30: {"stat": 667},
    31: {"stat": 689},
    32: {"stat": 712},
    33: {"stat": 734},
    34: {"stat": 757},
    35: {"stat": 779},
    36: {"stat": 802},
    37: {"stat": 824},
    38: {"stat": 847},
    39: {"stat": 869},
    40: {"stat": 892},
    41: {"stat": 914},
    42: {"stat": 937},
    43: {"stat": 959},
    44: {"stat": 982},
    45: {"stat": 1004},
    46: {"stat": 1027},
    47: {"stat": 1049},
    48: {"stat": 1072},
    49: {"stat": 1094},
    50: {"stat": 1117}
}
common_1a_table = {
    1: {"stat": 43},
    2: {"stat": 57},
    3: {"stat": 74},
    4: {"stat": 91},
    5: {"stat": 111},
    6: {"stat": 131},
    7: {"stat": 153},
    8: {"stat": 176},
    9: {"stat": 201},
    10: {"stat": 228},
    11: {"stat": 255},
    12: {"stat": 284},
    13: {"stat": 315},
    14: {"stat": 346},
    15: {"stat": 379},
    16: {"stat": 414},
    17: {"stat": 449},
    18: {"stat": 487},
    19: {"stat": 526},
    20: {"stat": 567},
    21: {"stat": 608},
    22: {"stat": 651},
    23: {"stat": 696},
    24: {"stat": 741},
    25: {"stat": 789},
    26: {"stat": 838},
    27: {"stat": 888},
    28: {"stat": 939},
    29: {"stat": 993},
    30: {"stat": 1047},
    31: {"stat": 1103},
    32: {"stat": 1160},
    33: {"stat": 1219},
    34: {"stat": 1278},
    35: {"stat": 1340},
    36: {"stat": 1403},
    37: {"stat": 1467},
    38: {"stat": 1533},
    39: {"stat": 1600},
    40: {"stat": 1668},
    41: {"stat": 1736},
    42: {"stat": 1804},
    43: {"stat": 1872},
    44: {"stat": 1940},
    45: {"stat": 2008},
    46: {"stat": 2076},
    47: {"stat": 2144},
    48: {"stat": 2212},
    49: {"stat": 2280},
    50: {"stat": 2348},
}
common_3a_table = {
    1: {"percent": 109},
    2: {"percent": 110},
    3: {"percent": 111},
    4: {"percent": 112},
    5: {"percent": 113},
    6: {"percent": 114},
    7: {"percent": 115},
    8: {"percent": 116},
    9: {"percent": 117},
    10: {"percent": 118},
    11: {"percent": 119},
    12: {"percent": 120},
    13: {"percent": 121},
    14: {"percent": 122},
    15: {"percent": 123},
    16: {"percent": 124},
    17: {"percent": 125},
    18: {"percent": 126},
    19: {"percent": 127},
    20: {"percent": 128},
    21: {"percent": 129},
    22: {"percent": 130},
    23: {"percent": 131},
    24: {"percent": 132},
    25: {"percent": 133},
    26: {"percent": 134},
    27: {"percent": 135},
    28: {"percent": 136},
    29: {"percent": 137},
    30: {"percent": 138},
    31: {"percent": 139},
    32: {"percent": 140},
    33: {"percent": 141},
    34: {"percent": 142},
    35: {"percent": 143},
    36: {"percent": 144},
    37: {"percent": 145},
    38: {"percent": 146},
    39: {"percent": 147},
    40: {"percent": 148},
    41: {"percent": 149},
    42: {"percent": 150},
    43: {"percent": 151},
    44: {"percent": 152},
    45: {"percent": 153},
    46: {"percent": 154},
    47: {"percent": 155},
    48: {"percent": 156},
    49: {"percent": 157},
    50: {"percent": 158},
}

buff_const = 665
buff_1a_const = 750

def calc_buff_attack(stat, main_stat, skillLv, apocLv, buff_table, buffPower, itemMul):
    buffConst = buff_table[skillLv]  # {"atk": x, "stat": y}
    apocConst = common_1a_table[apocLv] * common_3a_table[apocLv] * 0.01  # {"percent": x}

    # 기본 버프 공격력
    basicBuffAtk = buffConst['atk'] * ((main_stat / 665 + 1))
    mainBuffAtk = (buffConst['atk'] * ((main_stat + 4350) / 665 + 1)) * (buffPower + 3500) * 0.0000379 + basicBuffAtk

    # 기본 버프 스탯
    basicBuffStat = buffConst['stat'] * ((main_stat / 665 + 1) * itemMul)
    mainBuffStat = (buffConst['stat'] * ((main_stat + 4350) / 665 + 1)) * (buffPower + 3500) * 0.0000379 + basicBuffStat

    # 아포칼립스 스탯 증가
    basicApocStat = apocConst['stat'] * ((main_stat / 750 + 1))
    apocBuffStat = (apocConst['stat'] * ((main_stat + 6150) / 750 + 1)) * (buffPower + 5000) * 0.0000025 + basicApocStat

    return {
        "finalBuffAtk": mainBuffAtk,
        "finalBuffStat": mainBuffStat,
        "apocBuffStat": apocBuffStat
    }


    
def get_buff_stat(statusData, equipmentData, buffGearData):
    try:
        jobName = statusData.jobName
        jobGrowName = statusData.jobGrowName

        base_stat = {}
        for stat in statusData:
            key = statusData["name"].strip()
            base_stat[key] = max(base_stat.get(key, 0), stat["value"])

        if jobName == "Priest (M)" and jobGrowName == "Neo: Crusader":
            jobGrowName = "Neo: Crusader (M)"
        elif jobName == "Priest (F)" and jobGrowName == "Neo: Crusader":
            jobGrowName = "Neo: Crusader (F)"

        if "Neo: Enchantress" in jobGrowName:
            main_stat = "Intelligence"
            buff_table = enchantress_buff_table
        elif "Neo: Crusader (F)" in jobGrowName:
            main_stat = "Intelligence"
            buff_table = fsader_buff_table
        elif "Neo: Muse" in jobGrowName:
            main_stat = "Spirit"
            buff_table = muse_buff_table
        elif "Neo: Crusader (M)" in jobGrowName:
            main_stat = "Vitality"
            buff_table = msader_buff_table
        else:
            return 0

        

        stat_total = base_stat.get(main_stat, 0)
        
        print(f"stat_total: {stat_total}")
        buff_power = base_stat.get("Buff Power", 0)
        buff_amp_percent = base_stat.get("Buff Power Amp.", 0)
        
        #buff_power_final = int((buff_power * (1 + buff_amp_percent / 100) + 193848) / 22830)
        #buff_power_final = int((buff_power * (1 + buff_amp_percent / 100) + 47702.93) / 19381.31)
        buff_power_add = 140000
        buff_power_div = 28994.88
        buff_power_final = (buff_power * (1 + buff_amp_percent / 100) + buff_power_add) / buff_power_div
        print("base_stat keys =", list(base_stat.keys()))
        print("Value for 'Intelligence' =", base_stat.get('Intelligence'))

        buff_data = get_buff_equipment(server, char_id)
        print("[DEBUG] buff_data.skill:", type(buff_data.get("skill")))
        print("[DEBUG] buff_data.buff:", type(buff_data.get("skill", {}).get("buff")))

        buff_level = (
            buff_data.get("skill", {})
                     .get("buff", {})
                     .get("skillInfo", {})
                     .get("option", {})
                     .get("level", 0)
        )

        buff_equip = buff_data.get("skill", {}).get("buff", {}).get("equipment", [])
        current_equip = get_equipment(server, char_id)
        current_equip_map = {item["slotId"]: item["itemId"] for item in current_equip}

        for item in buff_equip:
            slot = item["slotId"]
            buff_item_id = item.get("itemId")
            if not buff_item_id or slot not in current_equip_map:
                continue
            equip_item_id = current_equip_map[slot]
            buff_stats = get_item_stat(buff_item_id)
            equip_stats = get_item_stat(equip_item_id)
            stat_total += buff_stats.get(main_stat, 0) - equip_stats.get(main_stat, 0)

        # Avatar
        buff_avatar = get_buff_avatar(server, char_id)
        current_avatar = get_avatar(server, char_id)
        current_avatar_map = {item["slotId"]: item["itemId"] for item in current_avatar}
        
        for item in buff_avatar:
            slot = item["slotId"]
            buff_item_id = item.get("itemId")
            if not buff_item_id or slot not in current_avatar_map:
                continue

            equip_item_id = current_avatar_map[slot]
            buff_stats = get_item_stat(buff_item_id)
            equip_stats = get_item_stat(equip_item_id)

            buff_val = buff_stats.get(main_stat, 0)
            equip_val = equip_stats.get(main_stat, 0)
            delta = buff_val - equip_val
            stat_total += delta

            print(f"[AVATAR] {slot} | Buff: {buff_val} - Equip: {equip_val} => Δ{delta}")

            # Emblems
            for emblem in item.get("emblems", []):
                emblem_id = emblem.get("itemId")
                if emblem_id:
                    emblem_stats = get_item_stat(emblem_id)
                    emblem_val = emblem_stats.get(main_stat, 0)
                    stat_total += emblem_val
                    print(f"[EMBLEM] {slot} | Emblem ID: {emblem_id} -> {main_stat} +{emblem_val}")

        # Creature
        buff_creature = get_buff_creature(server, char_id)
        current_creature = get_creature(server, char_id)
        if buff_creature and current_creature:
            buff_item_id = buff_creature.get("itemId")
            equip_item_id = current_creature.get("itemId")
            if buff_item_id and equip_item_id:
                buff_stats = get_item_stat(buff_item_id)
                equip_stats = get_item_stat(equip_item_id)
                stat_total += buff_stats.get(main_stat, 0) - equip_stats.get(main_stat, 0)

        buff_atk = buff_table[buff_level]["atk"]
        buff_stat_val = buff_table[buff_level]["stat"]

        buff_pmi = round(buff_atk * (1 + stat_total / buff_const) * buff_power_final)
        
        print("buff_power =", buff_power_final)

        return buff_pmi#, buff_stat_result

    except Exception as e:
        import traceback
        print("❌ Error in get_buff_stat():", e)
        traceback.print_exc()
        return e
