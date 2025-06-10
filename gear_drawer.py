# gear_drawer.py (trimmed for web use)

import os
import requests
from PIL import Image

display_slot_order = [
    "Title", "Weapon", "Top", "Bottom", "Shoulder", "Belt",
    "Shoes", "Necklace", "Bracelet", "Ring", "Sub Equipment", "Magic Stone", "Earrings"
]

def get_character_id(server, name):
    with open("config.txt", "r", encoding="utf-8") as f:
        api_key = f.read().strip()
    url = f"https://api.dfoneople.com/df/servers/{server}/characters?characterName={name}&apikey={api_key}"
    res = requests.get(url)
    res.raise_for_status()
    return res.json()['rows'][0]['characterId']

def get_character_info(server, character_id):
    with open("config.txt", "r", encoding="utf-8") as f:
        api_key = f.read().strip()
    url = f"https://api.dfoneople.com/df/servers/{server}/characters/{character_id}?apikey={api_key}"
    res = requests.get(url)
    res.raise_for_status()
    return res.json()

def get_character_equipments(server, character_id):
    with open("config.txt", "r", encoding="utf-8") as f:
        api_key = f.read().strip()
    url = f"https://api.dfoneople.com/df/servers/{server}/characters/{character_id}/equip/equipment?apikey={api_key}"
    res = requests.get(url)
    res.raise_for_status()
    return res.json()

def draw_equipment_icons(server, character_id):
    equip_data = get_character_equipments(server, character_id)
    icon_folder = "assets/equipments"

    from PIL import ImageDraw
    canvas = Image.new("RGBA", (624, 624), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    for equip in equip_data.get("equipment", []):
        item_slot = equip.get("slotName")
        icon_name = equip.get("itemName", "").replace(" ", "_") + ".png"
        icon_path = os.path.join(icon_folder, icon_name)

        if not os.path.exists(icon_path):
            continue

        icon = Image.open(icon_path).convert("RGBA").resize((48, 48))

        if item_slot in display_slot_order:
            idx = display_slot_order.index(item_slot)
            x = (idx % 4) * 64
            y = (idx // 4) * 64
            canvas.paste(icon, (x, y), icon)

    output_path = f"output/{server}_{character_id}_gear.png"
    canvas.save(output_path)
    return output_path
