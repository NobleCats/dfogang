// ===================================
//          ui.js
// ===================================
import * as api from './api.js';

const SCALE = 2.0;
const SLOT_POSITION = {
    HeadShoulder: [7, 8], Top: [39, 8], Bottom: [7, 40], Belt: [39, 40], Shoes: [7, 72],
    Weapon: [181, 8], Title: [213, 8], Bracelet: [181, 40], Necklace: [213, 40], Ring: [213, 72],
    SubEquipment: [181, 72], Earrings: [181, 104], MagicStone: [213, 104]
};
const rarityColors = {
    "None": "#FFFFFF", "Rare": "#B36BFF", "Unique": "#FF00FF",
    "Legendary": "#FF7800", "Epic": "#FFB400"
};
const SET_CATEGORIES = [
    "Dragon", "Magic", "Alpha", "Shadow", "Ethereal", "Valkyrie",
    "Nature", "Fairy", "Energy", "Serendipity", "Cleansing", "Gold", "Tales"
];

function getSetIconPath(setName) {
    if (!setName || typeof setName !== "string") return "assets/sets/Unknown.png";
    if (setName.includes("Pack")) return "assets/sets/Alpha.png";
    if (setName.includes("Paradise")) return "assets/sets/Gold.png";
    if (setName.includes("Death Plane")) return "assets/sets/Shadow.png";
    for (const keyword of SET_CATEGORIES) {
        if (setName.includes(keyword)) return `assets/sets/${keyword}.png`;
    }
    return "assets/sets/Unknown.png";
}

export function createCharacterCard(profile, searchName, dpsToShow, isBuffer) { 
    const spritePath = `assets/characters/${profile.jobName}.png`;
    const setIconPath = getSetIconPath(profile.setItemName ?? "");
    const rarityName = profile.setItemRarityName ?? "None";
    let rarityStyle = 'padding:2px 0;';
    if (rarityName === "Primeval") {
        rarityStyle = `background: linear-gradient(to bottom, #57e95b, #3a8390); -webkit-background-clip: text; -webkit-text-fill-color: transparent;`;
    } else {
        const colorKey = Object.keys(rarityColors).find(key => rarityName.includes(key)) || "None";
        rarityStyle = `color: ${rarityColors[colorKey]};`;
    }
    const card = document.createElement('div');
    card.className = 'card';
    card.dataset.characterId = profile.characterId;
    card.dataset.characterName = profile.characterName;
    card.dataset.serverId = profile.serverId;

    let dpsOrBuffDisplay = '';
    if (isBuffer) {
        dpsOrBuffDisplay = `<span style="font-size: 1.2em; color: var(--color-accent-blue);">${profile.total_buff_score != null ? profile.total_buff_score.toLocaleString() : 'N/A'}</span>`;
    } else {
        dpsOrBuffDisplay = `<span style="font-size: 1.2em; color: var(--color-accent-blue);">${dpsToShow != null ? dpsToShow.toLocaleString() : 'N/A'}</span>`;
    }

    card.innerHTML = `
        <div style="position: absolute; top: 16px; right: 16px; text-align: right;">
            <div style="font-size: 0.8em; color:var(--color-text-secondary);">${profile.serverId}</div>
            <div style="display:flex; align-items:center; justify-content: flex-end; margin-top:4px;">
                <img src="assets/image/fame.png" alt="Fame" style="width:15px; height:13px; margin-right:4px;">
                <span style="color:var(--color-fame); font-size:0.9em; font-weight: 500;">${profile.fame?.toLocaleString() ?? '-'}</span>
            </div>
        </div>
        <div class="character-sprite-container"> <img src="${spritePath}" alt="${profile.jobName}"> </div>

        <div style="color:${profile.adventureName === searchName ? 'var(--color-fame)' : 'var(--color-text-secondary)'}; font-weight:500;">${profile.adventureName ?? '-'}</div>
        <div style="font-family: var(--font-display); color:#eee; font-size:1.8em; font-weight:600;">${profile.characterName ?? '-'}</div>
        <div style="color:#A0844B; font-size:0.8em;">[${profile.jobGrowName ?? '-'}]</div>
        <div style="display: flex; align-items: center; gap: 2px;"> <img src="${setIconPath}" alt="Set Icon"> <span style="${rarityStyle};"> ${rarityName}</span>
            ${profile.setPoint > 0 ? `<span style="color:#aaa; font-size: 0.9em; margin-left: 4px;">(${profile.setPoint})</span>` : ''}
        </div>

        <div style="display: flex; align-items: center; gap: 6px; font-family: var(--font-dfo);">
            <span style="font-size: 1em; margin-top: 2.1px; color: var(--color-text-secondary);">${isBuffer ? 'Buff Score' : 'DPS'}</span>
            ${dpsOrBuffDisplay}
        </div>
    `;
    return card;
}

export function renderMainDpsOptions(container, dpsOptions) {
    container.innerHTML = `
        <div class="dps-toggle-group">
            <div class="dps-toggle-label">
                Set Normalize
                <span class="tooltip-icon">?</span> <div class="tooltip-content">
                    <p>Calculates damage based on a comparable tier of the Death in the Shadows Set.</p>
                    <p>(This feature was added to provide a rough standard, as object damage is not reflected in DPS calculations.)</p>
                </div>
            </div>
            <div class="dps-toggle-switch">
                <div class="dps-toggle-option ${dpsOptions.average_set_dmg ? 'active' : ''}" data-dps-option="average_set_dmg" data-dps-value="true">On</div>
                <div class="dps-toggle-option ${!dpsOptions.average_set_dmg ? 'active' : ''}" data-dps-option="average_set_dmg" data-dps-value="false">Off</div>
            </div>
        </div>
    `;
}

function renderDpsCalculatorWidget(profile, equipment, setItemInfo, dpsState, isBuffer) {
    const dpsOptions = dpsState.options;
    const dpsResult = dpsState.result;

    const widgetDiv = document.createElement('div');
    widgetDiv.className = 'detail-widget detail-widget-dps';
    widgetDiv.innerHTML = `<h3 class="widget-title">DPS Calculator</h3>`;

    const container = document.createElement('div');
    container.className = 'dps-calculator-container';

    if (isBuffer) { // This block is now redundant due to the new conditional rendering in renderCharacterDetail
        container.innerHTML = `
            <div style="text-align: center; color: var(--color-text-secondary); padding: 20px;">
                This character is a Buffer. DPS calculation is not applicable.
            </div>
        `;
    } else { 
        let isCleansingSetEquipped = false;
        if (setItemInfo && Array.isArray(setItemInfo)) {
            for (const itemInfo of setItemInfo) {
                if (itemInfo.setItemName && itemInfo.setItemName.includes("Cleansing")) {
                    isCleansingSetEquipped = true;
                    break;
                }
            }
        }

        if (isCleansingSetEquipped) {
            container.innerHTML += `
                <div class="dps-toggle-group">
                    <div class="dps-toggle-label">Cleansing Mode</div>
                    <div class="dps-toggle-switch">
                        <div class="dps-toggle-option ${!dpsOptions.cleansing_cdr ? 'active' : ''}" data-dps-option="cleansing_cdr" data-dps-value="false">Corruption</div>
                        <div class="dps-toggle-option ${dpsOptions.cleansing_cdr ? 'active' : ''}" data-dps-option="cleansing_cdr" data-dps-value="true">Cleansing</div>
                    </div>
                </div>
            `;
        }

        const weapon = equipment.find(eq => eq.slotId === 'WEAPON');
        const weaponName = weapon?.itemName || "";
        const conditional_weapon_names = new Set([
            "Falke the Ally", "Falke the Friend", "Falke the Family",
            "Secret Solo", "Secret Duet", "Secret Concert",
            "Mist Traveler", "Mist Explorer", "Mist Pioneer",
            "Malefic Dawn", "Malefic Daybreak", "Malefic Twilight",
            "Yang Ull's Twig: Extreme"
        ]);

        if (conditional_weapon_names.has(weaponName)) {
            const jobId = profile.jobId;
            const jobGrowName = profile.jobGrowName;

            let labels = {};
            if (jobId === 'dbbdf2dd28072b26f22b77454d665f21') {
                if (jobGrowName.includes("Hunter")) labels = { title: "Change Tactics", false: "Falke Assist", true: "Falke Patrol" };
                else if (jobGrowName.includes("Muse")) labels = { title: "Harmonize", false: "Climax!", true: "Vivace!" };
                else if (jobGrowName.includes("Traveler")) labels = { title: "Wayfinder", false: "Mist Path", true: "Mist Road" };
                else if (jobGrowName.includes("Vigilante")) labels = { title: "Sensory Focus", false: "Spot Weakness", true: "Sense Menace" };
            }


            if (labels.title) {
                container.innerHTML += `
                    <div class="dps-toggle-group">
                        <div class="dps-toggle-label">${labels.title}</div>
                        <div class="dps-toggle-switch">
                            <div class="dps-toggle-option ${!dpsOptions.weapon_cdr ? 'active' : ''}" data-dps-option="weapon_cdr" data-dps-value="false">${labels.false}</div>
                            <div class="dps-toggle-option ${dpsOptions.weapon_cdr ? 'active' : ''}" data-dps-option="weapon_cdr" data-dps-value="true">${labels.true}</div>
                        </div>
                    </div>
                `;
            }
        }

        container.innerHTML += `
            <div class="dps-toggle-group">
                <div class="dps-toggle-label">Set Normalize</div>
                <div class="dps-toggle-switch">
                    <div class="dps-toggle-option ${dpsOptions.average_set_dmg ? 'active' : ''}" data-dps-option="average_set_dmg" data-dps-value="true">On</div>
                    <div class="dps-toggle-option ${!dpsOptions.average_set_dmg ? 'active' : ''}" data-dps-option="average_set_dmg" data-dps-value="false">Off</div>
                </div>
            </div>
        `;

        const appliedDamage = dpsResult?.finalDamage != null ? dpsResult.finalDamage.toLocaleString() : 'N/A';
        const appliedCooldownReduction = dpsResult?.cooldownReduction != null ? dpsResult.cooldownReduction.toFixed(2) + '%' : 'N/A';

        const dpsDisplayValue = dpsResult?.dps != null ? dpsResult.dps.toLocaleString() : 'N/A';

        const dpsResultHtml = `
            <div class="dps-stats-display" style="display: flex; flex-direction: column; gap: 8px; margin-top: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; font-size: 1.0em; color: var(--color-text-secondary);">
                    <span>Applied Damage:</span>
                    <span style="color: var(--color-text-primary); font-weight: 500;">${appliedDamage}</span>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; font-size: 1.0em; color: var(--color-text-secondary);">
                    <span>Applied Cooldown Reduction:</span>
                    <span style="color: var(--color-text-primary); font-weight: 500;">${appliedCooldownReduction}</span>
                </div>
            </div>
            <div class="dps-result-display" style="margin-top: 16px;">
                <span class="dps-result-label">Expected DPS</span>
                <span class="dps-result-value">${dpsDisplayValue}</span>
            </div>
        `;

        container.innerHTML += dpsResultHtml;
    }
    widgetDiv.appendChild(container);
    return widgetDiv;
}

function renderBuffCalculatorWidget(buffResults) {
    const widgetDiv = document.createElement('div');
    widgetDiv.className = 'detail-widget detail-widget-buff'; 
    widgetDiv.innerHTML = `<h3 class="widget-title">Buff Calculator</h3>`;

    const container = document.createElement('div');
    container.className = 'buff-calculator-container';

    if (!buffResults || Object.keys(buffResults).length === 0) {
        container.innerHTML = `
            <div style="text-align: center; color: var(--color-text-secondary); padding: 20px;">
                Failed to load buff data or no buff information available.
            </div>
        `;
    } else {
        const buffs = buffResults.buffs || {};
        const totalBuffScore = buffResults.total_buff_score != null ? buffResults.total_buff_score.toLocaleString() : 'N/A';

        let buffDetailsHtml = ``;

        // Main Buff
        const mainBuff = buffs.main;
        if (mainBuff) {
            const mainLevel = mainBuff.level != null ? `Lv.${mainBuff.level}` : '';
            const statBonus = mainBuff.stat_bonus != null ? mainBuff.stat_bonus.toLocaleString() : 'N/A';
            const atkBonus = mainBuff.atk_bonus != null ? mainBuff.atk_bonus.toLocaleString() : 'N/A';
            let enchantressFavoredBonus = '';
            if (mainBuff.stat_bonus_fav != null && mainBuff.atk_bonus_fav != null) {
                
                buffDetailsHtml += `
                    <div class="buff-category">
                        <span class="buff-title">Main Buff (${mainLevel})</span>
                        <div>
                            <span>Stat:</span>
                            <span>${statBonus}</span>
                        </div>
                        <div>
                            <span></span>
                            <span style="color: var(--color-text-tertiary)">${mainBuff.stat_bonus_fav.toLocaleString()}</span>
                        </div>
                        <div>
                            <span>Attack:</span>
                            <span>${atkBonus}</span>
                        </div>
                        <div>
                            <span></span>
                            <span style="color: var(--color-text-tertiary)">${mainBuff.atk_bonus_fav.toLocaleString()}</span>
                        </div>
                    </div>
                `;
                enchantressFavoredBonus = `
                    <div class="favored-bonus-line">
                        <span>Favored Stat:</span>
                        <span>${mainBuff.stat_bonus_fav.toLocaleString()}</span>
                    </div>
                    <div class="favored-bonus-line">
                        <span>Favored Atk:</span>
                        <span>${mainBuff.atk_bonus_fav.toLocaleString()}</span>
                    </div>
                `;
            }
            else {
                buffDetailsHtml += `
                    <div class="buff-category">
                        <span class="buff-title">Main Buff (${mainLevel})</span>
                        <div>
                            <span>Stat:</span>
                            <span>${statBonus}</span>
                        </div>
                        <div>
                            <span>Attack:</span>
                            <span>${atkBonus}</span>
                        </div>
                    </div>
                `;
            }

        }

        // 1A Buff
        const oneABuff = buffs['1a'];
        if (oneABuff) {
            const oneALevel = oneABuff.level != null ? `Lv.${oneABuff.level}` : '';
            const statBonus = oneABuff.stat_bonus != null ? oneABuff.stat_bonus.toLocaleString() : 'N/A';
            buffDetailsHtml += `
                <div class="buff-category">
                    <span class="buff-title">1st Awakening Buff (${oneALevel})</span>
                    <div>
                        <span>Stat:</span>
                        <span>${statBonus}</span>
                    </div>
                </div>
            `;
        }

        // 3A Buff
        const threeABuff = buffs['3a'];
        if (threeABuff) {
            const threeALevel = threeABuff.level != null ? `Lv.${threeABuff.level}` : '';
            const statBonus = threeABuff.stat_bonus != null ? threeABuff.stat_bonus.toLocaleString() : 'N/A';
            const increasePercent = threeABuff.increase_percent != null ? threeABuff.increase_percent.toFixed(2) + '%' : 'N/A';
            buffDetailsHtml += `
                <div class="buff-category">
                    <span class="buff-title">3rd Awakening Buff (${threeALevel})</span>
                    <div>
                        <span>Stat:</span>
                        <span>${statBonus}</span>
                    </div>
                </div>
            `;
        }

        // Aura Buff
        const auraBuff = buffs.aura;
        if (auraBuff) {
            const auraLevel = auraBuff.level != null ? `Lv.${auraBuff.level}` : '';
            const statBonus = auraBuff.stat_bonus != null ? auraBuff.stat_bonus.toLocaleString() : 'N/A';
            buffDetailsHtml += `
                <div class="buff-category">
                    <span class="buff-title">Aura (${auraLevel})</span>
                    <div>
                        <span>Stat:</span>
                        <span>${statBonus}</span>
                    </div>
                </div>
            `;
        }

        container.innerHTML = `
            ${buffDetailsHtml}
            <div class="buff-score-display"> 
                <span class="buff-score-label">Buff Score</span>
                <span class="buff-score-value">${totalBuffScore}</span> 
            </div>
        `;
    }

    widgetDiv.appendChild(container);
    return widgetDiv;
}

export async function renderCharacterDetail(profile, equipment, setItemInfo, fameHistory, gearHistory, dpsState, isBuffer, buffResults) {
    const detailView = document.getElementById('detail-view');
    detailView.innerHTML = `
        <div class="detail-grid">
            <div class="back-button-container">
                <button class="back-button">← Back</button>
            </div>
            <div class="detail-widget detail-widget-profile">
                <div class="character-canvas" id="character-canvas-container"></div>
                <div id="set-info-container" class="detail-widget" style="margin-top: 24px;"></div>
            </div>
            <div id="dps-or-buff-widget-area"></div>
            <div class="detail-widget detail-widget-fame">
                <h3 class="widget-title">Fame Trend</h3>
                <div id="fame-chart-container" style="width: 100%; height: 265px;">
                    <canvas id="fame-chart"></canvas>
                </div>
            </div>
            <div class="detail-widget detail-widget-history">
                 <h3 class="widget-title">Equipment History</h3>
                 <div id="history-panel"></div>
            </div>
        </div>
    `;

    renderCharacterCanvas(profile, equipment);
    renderSetItems(setItemInfo);
    renderFameChart(fameHistory);
    await renderHistoryPanel(gearHistory);

    const dpsOrBuffWidgetArea = document.getElementById('dps-or-buff-widget-area');
    if (dpsOrBuffWidgetArea) {
        dpsOrBuffWidgetArea.innerHTML = ''; // Clear previous content
        let widgetToRender;
        if (isBuffer) {
            widgetToRender = renderBuffCalculatorWidget(buffResults);
        } else {
            widgetToRender = renderDpsCalculatorWidget(profile, equipment, setItemInfo, dpsState, isBuffer);
        }
        dpsOrBuffWidgetArea.appendChild(widgetToRender);
    }
}


function renderCharacterCanvas(profile, equipmentList) {
    const container = document.getElementById('character-canvas-container');
    container.style.width = '492px';
    container.style.height = '354px';
    container.style.position = 'relative';

    container.innerHTML = `
        <img class="background" src="assets/image/background.png" alt="Background" style="width:100%; height:100%; position:absolute; z-index:0; border-radius:8px;">
        <img class="character-sprite" src="assets/characters/${profile.jobName}.png"
             style="position:absolute; bottom:0; left:50%; transform:translateX(-50%); height:${250 * SCALE * 0.75}px; z-index:1;" />
        <div id="equipment-layer" style="position:absolute; width:100%; height:100%; z-index:2;"></div>
        <canvas id="reinforce-canvas" width="492" height="354" style="position:absolute; left:0; top:0; z-index:5;"></canvas>
        <canvas id="text-canvas" width="492" height="354" style="position:absolute; left:0; top:0; z-index:4;"></canvas>
    `;

    const eqLayer = document.getElementById("equipment-layer");

    if (Array.isArray(equipmentList)) {
        equipmentList.forEach(eq => {
            const slotKey = (eq.slotName || eq.slotId).replace(/[\s\/]/g, "");
            if (!SLOT_POSITION[slotKey]) return;
            const [x, y] = SLOT_POSITION[slotKey];
            const iconSize = 28 * SCALE;

            const itemEl = document.createElement("div");
            itemEl.style.cssText = `position:absolute; left:${x * SCALE}px; top:${y * SCALE}px; width:${iconSize}px; height:${iconSize}px;`;

            itemEl.innerHTML = `
                <img src="https://img-api.dfoneople.com/df/items/${eq.itemId}" style="width:100%; height:100%; position:absolute; z-index:2;">
                <img src="assets/equipments/edge/${eq.itemRarity}.png" style="width:100%; height:100%; position:absolute; z-index:3;">
            `;

            if (eq.upgradeInfo) {
                const { itemName, itemRarity: fusionRarity, setItemName } = eq.upgradeInfo;
                const baseRarity = eq.itemRarity;
                const distKeywords = ["Elegance", "Desire", "Betrayal"];
                const keywordMatch = setItemName ? SET_CATEGORIES.find(k => setItemName.includes(k)) : null;

                const fusionIconWrapper = document.createElement('div');
                fusionIconWrapper.style.cssText = `position:absolute; right:0; top:0; z-index:4;`;

                if (keywordMatch) {
                    fusionIconWrapper.innerHTML = `<img src="assets/sets/${fusionRarity}/${keywordMatch}.png" style="width:${27 * SCALE * 0.75}px; height:${12 * SCALE * 0.75}px;">`;
                } else if (distKeywords.some(word => itemName.includes(word))) {
                    fusionIconWrapper.innerHTML = `<img src="assets/fusions/${baseRarity}/Dist.png" style="width:${27 * SCALE * 0.75}px; height:${12 * SCALE * 0.75}px;">`;
                } else {
                    fusionIconWrapper.style.width = `${28 * SCALE * 0.75}px`;
                    fusionIconWrapper.style.height = `${13 * SCALE * 0.75}px`;
                    fusionIconWrapper.innerHTML = `
                        <img src="assets/fusions/${baseRarity}/Base.png" style="width:100%; height:100%; position:absolute; left:0; top:0;">
                        <img src="assets/fusions/${fusionRarity}/Core.png" style="width:100%; height:100%; position:absolute; left:0; top:0;">
                    `;
                }
                itemEl.appendChild(fusionIconWrapper);
            }

            const tuneLevel = eq.tune?.level || 0;
            if (tuneLevel >= 1 && tuneLevel <= 3) {
                const tuneSize = [8 * SCALE, 10 * SCALE];
                const tuneImg = document.createElement("img");
                tuneImg.src = `assets/equipments/etc/tune${tuneLevel}.png`;
                tuneImg.style.position = "absolute";
                tuneImg.style.width = `${tuneSize[0]}px`;
                tuneImg.style.height = `${tuneSize[1]}px`;
                tuneImg.style.left = `${iconSize - tuneSize[0] - 1}px`;
                tuneImg.style.top = `${iconSize - tuneSize[1]}px`;
                tuneImg.style.zIndex = "3";
                itemEl.appendChild(tuneImg);
            }

            eqLayer.appendChild(itemEl);
        });
    }

    drawReinforceText(Array.isArray(equipmentList) ? equipmentList : []);
    drawCharacterText(profile);
}


function renderSetItems(setItemInfo) {
    const container = document.getElementById("set-info-container");
    container.innerHTML = "";
    if (!Array.isArray(setItemInfo) || setItemInfo.length === 0) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'block';

    setItemInfo.forEach(item => {
        const rarityName = item.setItemRarityName ?? "";
        let rarityStyle = `color: ${rarityColors[Object.keys(rarityColors).find(key => rarityName.includes(key)) || "None"]};`;
        if (rarityName === "Primeval") {
            rarityStyle = `background: linear-gradient(to bottom, #57e95b, #3a8390); -webkit-background-clip: text; -webkit-text-fill-color: transparent;`;
        }

        container.innerHTML += `
            <div style="text-align:center;">
                <div style="font-family: var(--font-dfo); font-size:22px; font-weight:700; color:#eee; margin-bottom:4px;">${item.setItemName ?? ''}</div>
                <div style="display:flex; align-items:center; justify-content:center; gap:8px;">
                    <img src="${getSetIconPath(item.setItemName)}" alt="${item.setItemName ?? ''}" style="height: 24px;">
                    <span style="font-size:16px; font-weight:500; ${rarityStyle}">${rarityName}</span>
                </div>
                <div style="font-size:14px; color:var(--color-text-secondary); margin-top:2px;">(${item.active?.setPoint?.current ?? 0})</div>
            </div>
        `;
    });
}

function renderFameChart(records, hoverX = null, hoverY = null) {
    const container = document.getElementById("fame-chart-container");
    const canvas = document.getElementById("fame-chart");
    if (!canvas || !container) return;

    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const style = getComputedStyle(document.documentElement);
    const accentColor = style.getPropertyValue('--color-accent-blue').trim();
    const gridColor = `rgba(78, 143, 248, 0.1)`;
    const textColor = style.getPropertyValue('--color-text-primary').trim();

    const paddingX = 40;
    const paddingY = 30;

    if (!records || records.length === 0) {
        ctx.fillStyle = "#aaa";
        ctx.font = `11px 'Noto Sans KR', sans-serif`;
        ctx.textAlign = "center";
        ctx.fillText("No fame history", canvas.width / 2, canvas.height / 2);
        return;
    }

    records.sort((a, b) => new Date(a.date) - new Date(b.date));
    const fames = records.map(r => r.fame);
    const rawFameMin = Math.min(...fames);
    const rawFameMax = Math.max(...fames);

    let fameMin, fameMax;
    if (rawFameMin === rawFameMax) {
        fameMin = rawFameMin - 10;
        fameMax = rawFameMax + 10;
    } else {
        const famePadding = (rawFameMax - rawFameMin) * 0.15;
        fameMin = rawFameMin - famePadding;
        fameMax = rawFameMax + famePadding;
    }
    const fameRange = fameMax - fameMin;

    const chartWidth = canvas.width - paddingX * 2;
    const chartHeight = canvas.height - paddingY * 2;

    const points = records.map((r, i) => {
        const t = records.length === 1 ? 0.5 : i / (records.length - 1);
        const x = paddingX + t * chartWidth;
        const y = (records.length === 1) ? canvas.height / 2 : paddingY + (1 - (r.fame - fameMin) / fameRange) * chartHeight;
        return { x, y, fame: r.fame, date: r.date };
    });

    ctx.font = `11px 'Noto Sans KR', sans-serif`;
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";

    let step = fameRange <= 100 ? 10 : fameRange <= 1000 ? 100 : fameRange <= 3000 ? 200 : 1000;
    const firstLabel = Math.floor(fameMin / step) * step;
    const lastLabel = Math.ceil(fameMax / step) * step;

    for (let value = firstLabel; value <= lastLabel; value += step) {
        if (value < fameMin || value > fameMax) continue;
        const y = paddingY + (1 - (value - fameMin) / fameRange) * chartHeight;
        ctx.strokeStyle = gridColor;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(paddingX, y);
        ctx.lineTo(canvas.width - paddingX, y);
        ctx.stroke();
        ctx.fillStyle = textColor;
        ctx.fillText(value.toLocaleString(), paddingX - 6, y);
    }

    ctx.strokeStyle = accentColor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(paddingX, paddingY);
    ctx.lineTo(paddingX, canvas.height - paddingY);
    ctx.moveTo(paddingX, canvas.height - paddingY);
    ctx.lineTo(canvas.width - paddingX, canvas.height - paddingY);
    ctx.stroke();

    ctx.font = `11px 'Noto Sans KR', sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    points.forEach(pt => {
        const d = new Date(pt.date);
        const label = `${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}`;
        ctx.fillStyle = textColor;
        ctx.fillText(label, pt.x, canvas.height - paddingY + 4);
    });

    ctx.strokeStyle = accentColor;
    ctx.lineWidth = 4;
    ctx.beginPath();
    points.forEach((pt, i) => i === 0 ? ctx.moveTo(pt.x, pt.y) : ctx.lineTo(pt.x, pt.y));
    ctx.stroke();

    let hovered = null;
    points.forEach(pt => {
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 4, 0, 2 * Math.PI);
        ctx.fillStyle = accentColor;
        ctx.shadowColor = accentColor;
        ctx.shadowBlur = 6;
        ctx.fill();
        ctx.shadowBlur = 0;
        if (hoverX !== null && Math.hypot(pt.x - hoverX, pt.y - hoverY) < 8) {
            hovered = pt;
        }
    });

    if (hovered) {
        const d = new Date(hovered.date);
        const dateStr = d.toLocaleDateString("en-US", { year: "numeric", month: "2-digit", day: "2-digit" });
        const fameStr = hovered.fame?.toLocaleString() ?? '-';
        const tooltipLines = [`${dateStr}`, `Fame: ${fameStr}`];
        ctx.font = `bold 11px 'Noto Sans KR', sans-serif`;
        ctx.textBaseline = "top";
        ctx.textAlign = "left";
        const padding = 6;
        const lineHeight = 18;
        const width = Math.max(...tooltipLines.map(t => ctx.measureText(t).width));
        const height = tooltipLines.length * lineHeight;
        let boxX = hovered.x + 10;
        const boxY = hovered.y - height - 10;
        if (boxX + width + padding * 2 > canvas.width) {
            boxX = hovered.x - (width + padding * 2) - 10;
        }
        ctx.fillStyle = "rgba(0, 0, 0, 0.85)";
        ctx.fillRect(boxX, boxY, width + padding * 2, height + padding);
        ctx.strokeStyle = accentColor;
        ctx.strokeRect(boxX, boxY, width + padding * 2, height + padding);
        ctx.fillStyle = "#ffffff";
        ctx.textAlign = "left";
        tooltipLines.forEach((line, i) => {
            ctx.fillText(line, boxX + padding, boxY + padding + i * lineHeight);
        });
    }

    canvas.onmousemove = (e) => {
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        renderFameChart(records, mx, my);
    };
    canvas.onmouseleave = () => {
        renderFameChart(records, null, null);
    };
}

async function renderHistoryPanel(gearHistory) {
    const panel = document.getElementById("history-panel");
    if (!gearHistory || gearHistory.length === 0) {
        panel.innerHTML = `<div class="history-empty">No equipment history.</div>`;
        return;
    }

    panel.innerHTML = '';

    const famePromises = gearHistory.flatMap(entry => [
        ...entry.before.map(item => api.getItemFame(item.itemId)),
        ...entry.after.map(item => api.getItemFame(item.itemId))
    ]);
    const fameResults = await Promise.all(famePromises);
    let fameIndex = 0;

    const groupedByDate = gearHistory.reduce((acc, entry) => {
        (acc[entry.date] = acc[entry.date] || []).push(...entry.before.map((b, i) => ({ before: b, after: entry.after[i] })));
        return acc;
    }, {});

    Object.keys(groupedByDate).sort().reverse().forEach(date => {
        const dateStr = date.substring(5).replace('-', '/');
        const dateHeader = document.createElement('div');
        dateHeader.className = 'history-date-header';
        dateHeader.textContent = `${dateStr}`;
        panel.appendChild(dateHeader);

        groupedByDate[date].forEach(change => {
            const beforeFame = fameResults[fameIndex++];
            const afterFame = fameResults[fameIndex++];

            const beforeIcon = change.before.itemId
                ? `https://img-api.dfoneople.com/df/items/${change.before.itemId}`
                : `assets/equipments/null/${change.before.slotName.replace(/[\s\/]/g, "")}.png`;
            const afterIcon = change.after.itemId
                ? `https://img-api.dfoneople.com/df/items/${change.after.itemId}`
                : `assets/equipments/null/${change.after.slotName.replace(/[\s\/]/g, "")}.png`;

            const itemRow = document.createElement('div');
            itemRow.className = 'history-item';

            let fameIndicator = '';
            if (beforeFame != null && afterFame != null && beforeFame !== afterFame) {
                const isUp = afterFame > beforeFame;
                fameIndicator = `<img src="assets/image/${isUp ? 'up' : 'down'}.png" class="fame-indicator">`;
            }

            itemRow.innerHTML = `
                <div style="position: relative;" class="history-icon-wrapper">
                    <img src="${beforeIcon}" class="history-icon">
                </div>
                <div class="history-arrow">→</div>
                <div style="position: relative;" class="history-icon-wrapper">
                    <img src="${afterIcon}" class="history-icon">
                    ${fameIndicator}
                </div>
            `;
            panel.appendChild(itemRow);
        });
    });
}

async function drawCharacterText(profile) {
    const canvas = document.getElementById("text-canvas");
    if(!canvas) return;
    const ctx = canvas.getContext("2d");
    const font = new FontFace("GulimIndex", "url(font/gulim_index_2.ttf)");
    await font.load();
    document.fonts.add(font);

    ctx.font = `${10 * SCALE}px GulimIndex`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";

    const centerX = canvas.width / 2;
    const firstline = 124 * SCALE;
    const linespacing = 12 * SCALE;

    function drawTextWithOutline(text, y, color) {
        ctx.lineWidth = 4.5;
        ctx.strokeStyle = "black";
        ctx.strokeText(text, centerX, y);
        ctx.fillStyle = color;
        ctx.fillText(text, centerX, y);
    }

    drawTextWithOutline(profile.adventureName ?? '-', firstline, "#7db88a");
    drawTextWithOutline(`Lv.${profile.level} ${profile.characterName}`, firstline + linespacing, "#b6aa8f");
    drawTextWithOutline(`[${profile.jobGrowName}]`, firstline + linespacing * 2, "#A0844B");

    const fameText = profile.fame?.toLocaleString() ?? '-';
    const fameY = firstline + linespacing * 3;
    const iconW = 15 * SCALE * 0.75;
    const iconH = 13 * SCALE * 0.75;
    const padding = 3 * SCALE;

    const fameIcon = new Image();
    fameIcon.src = "assets/image/fame.png";
    fameIcon.onload = () => {
        const textMetrics = ctx.measureText(fameText);
        const textWidth = textMetrics.width;
        const textHeight = textMetrics.actualBoundingBoxAscent + textMetrics.actualBoundingBoxDescent;

        const totalWidth = iconW + padding + textWidth;
        const startX = (canvas.width - totalWidth) / 2;
        const textX = startX + iconW + padding;

        const textCenterY = fameY + textHeight / 2 + (2 * SCALE);
        const iconY = textCenterY - iconH / 2;

        ctx.drawImage(fameIcon, startX, iconY, iconW, iconH);

        ctx.textAlign = "left";
        ctx.lineWidth = 3;
        ctx.strokeStyle = "black";
        ctx.strokeText(fameText, textX, fameY);
        ctx.fillStyle = "#81C784";
        ctx.fillText(fameText, textX, fameY);
        ctx.textAlign = "center";
    };
}

function drawReinforceText(equipmentList) {
    const canvas = document.getElementById("reinforce-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    function drawText(x, y, text, color, scaleFactor = 1) {
        const fontSize = Math.floor(9 * SCALE * scaleFactor);
        ctx.font = `${fontSize}px gulim, sans-serif`;
        ctx.lineWidth = 4 * scaleFactor;
        ctx.strokeStyle = "black";
        ctx.strokeText(text, x, y);
        ctx.fillStyle = color;
        ctx.fillText(text, x, y);
    }

    ctx.textBaseline = "top";
    ctx.textAlign = "left";

    equipmentList.forEach(eq => {
        const slotKey = (eq.slotName || eq.slotId).replace(/[\s\/]/g, "");
        if (!SLOT_POSITION[slotKey]) return;

        const [baseX, baseY] = SLOT_POSITION[slotKey];
        const reinforce = eq.reinforce || 0;
        const isAmp = eq.amplificationName != null;
        const reinforceColor = isAmp ? "#FF00FF" : "#68D5ED";

        if (slotKey !== "Title" && (reinforce > 0 || isAmp)) {
            const scaleFactor = (slotKey === "SecondaryWeapon") ? 0.75 : 1;
            const x = baseX * SCALE;
            const y = baseY * SCALE;
            drawText(x, y, `+${reinforce}`, reinforceColor, scaleFactor);
        }
    });
}

export function switchView(view) {
    document.getElementById('main-view').style.setProperty('display', view === 'main' ? 'grid' : 'none', 'important');
    document.getElementById('detail-view').style.setProperty('display', view === 'detail' ? 'grid' : 'none', 'important');
}

export function setLoading(isLoading) {
    document.getElementById('loading-spinner').style.display = isLoading ? 'block' : 'none';
}

export function showMoreResultsIndicator(hasMore) {
    const existingIndicator = document.getElementById('load-more-indicator');
    if (hasMore && !existingIndicator) {
        const indicator = document.createElement('div');
        indicator.id = 'load-more-indicator';
        indicator.style.cssText = `
            text-align: center;
            color: var(--color-text-secondary);
            margin-top: 20px;
            font-size: 0.9em;
            padding-bottom: 20px;
        `;
        document.getElementById('results-wrapper').appendChild(indicator);
    } else if (!hasMore && existingIndicator) {
        existingIndicator.remove();
    }
}