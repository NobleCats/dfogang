// ===================================
//          api.js
// ===================================
const API_ROOT = "https://api.dfogang.com";

async function postData(endpoint, body) {
    try {
        const response = await fetch(`${API_ROOT}${endpoint}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Failed to fetch from ${endpoint}:`, error);
        return null;
    }
}

export async function getCharacterDps(server, characterName, options) {
    return await postData("/dps", {
        server,
        characterName,
        cleansing_cdr: options.cleansing_cdr,
        weapon_cdr: options.weapon_cdr,
        average_set_dmg: options.average_set_dmg,
    });
}


export async function getImage(url) {
  const proxyRequestUrl = `${API_ROOT}/image-proxy?url=${encodeURIComponent(url)}`;
  
  const response = await fetch(proxyRequestUrl);
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

export async function getCharacterBuffPower(server, characterId) {
    return await postData("/buff_power", { server, characterId });
}


export async function logSearch(server, name) {
    await postData("/search_log", { server, name });
}
export async function searchCharacters(server, name, average_set_dmg) {
    const endpoint = server === "explorer" ? "/search_explorer" : "/search";
    const data = await postData(endpoint, { name, server, average_set_dmg });
    return data ? data.results : [];
}
export async function getCharacterProfile(server, name) {
    return await postData("/profile", { server, name });
}
export async function getCharacterEquipment(server, name) {
    return await postData("/equipment", { server, name });
}
export async function getFameHistory(server, characterName) {
    return await postData("/fame-history", { server, characterName });
}
export async function getGearHistory(server, characterName) {
    return await postData("/history", { server, characterName });
}
export async function getCharacterBuffSkill(server, characterId) {
    return await postData("/buff_skill", { server, characterId });
}
export async function getItemFame(itemId) {
    if (!itemId) return 0;
    try {
        const response = await fetch(`${API_ROOT}/item-fame/${itemId}`);
        if (!response.ok) return null;
        const data = await response.json();
        return data.fame ?? null;
    } catch (e) {
        return null;
    }
}

export async function getCharacterStatus(serverId, characterId) {
    return await postData("/character/status", { serverId, characterId });
}

export async function getCheaters() {
    try {
        const response = await fetch(`${API_ROOT}/cheaters`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch cheaters:", error);
        return null;
    }
}