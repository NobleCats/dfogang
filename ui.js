// ===================================
//          ui.js
// (Handles DOM manipulation and rendering)
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
    "Nature", "Fairy", "Energy", "Serendipity", "Cleansing", "Gold"
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

export function createCharacterCard(profile, searchName) {
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
    card.innerHTML = `
        <div style="position: absolute; top: 10px; right: 10px; text-align: right;">
            <div style="font-size: 0.75em; color:#d2d2d2;">${profile.serverId}</div>
            <div style="display:flex; align-items:center; margin-top:4px;">
                <img src="assets/image/fame.png" alt="Fame" style="width:15px; height:13px; margin-right:4px;">
                <span style="color:#3ba042; font-size:0.8em;">${profile.fame?.toLocaleString() ?? '-'}</span>
            </div>
        </div>
        <img src="${spritePath}" alt="${profile.jobName}" style="width:200px; height:230px; object-fit:contain; margin-bottom:12px;">
        <div style="color:${profile.adventureName === searchName ? '#3ba042' : '#7db88a'};">${profile.adventureName ?? '-'}</div>
        <div style="color:#eee; font-size:1.8em; font-weight:600;">${profile.characterName ?? '-'}</div>
        <div style="color:#A0844B; font-size:0.8em;">[${profile.jobGrowName ?? '-'}]</div>
        <div style="display: flex; align-items: center; gap: 2px; margin-top: 10px;">
            <img src="${setIconPath}" alt="Set Icon" style="transform: scale(0.666); padding-top:10px;">
            <span style="${rarityStyle}; margin: 10px 0;">${rarityName}</span>
            ${profile.setPoint > 0 ? `<span style="color:#aaa; font-size: 0.9em; margin-left: 4px;">(${profile.setPoint})</span>` : ''}
        </div>
    `;
    return card;
}

export async function renderCharacterDetail(profile, equipment, fameHistory, gearHistory) {
    const detailView = document.getElementById('detail-view');
    detailView.innerHTML = `
        <div style="padding: 24px 32px 10px; display: flex; justify-content: flex-start;">
            <button class="back-button">← Back</button>
        </div>
        <div class="detail-grid">
            <div class="detail-widget detail-widget-profile">
                <div class="character-canvas" id="character-canvas-container"></div>
                <div id="set-info-container" class="detail-widget" style="margin-top: 24px;"></div>
            </div>
            <div class="detail-widget detail-widget-history">
                 <h3 class="widget-title">Equipment History</h3>
                 <div id="history-panel"></div>
            </div>
            <div class="detail-widget detail-widget-fame">
                <h3 class="widget-title">Fame Trend</h3>
                <canvas id="fame-chart"></canvas>
            </div>
        </div>
    `;

    renderCharacterCanvas(profile, equipment?.equipment);
    renderSetItems(equipment?.setItemInfo);
    renderFameChart(fameHistory);
    await renderHistoryPanel(gearHistory);
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
                    fusionIconWrapper.innerHTML = `<img src="assets/sets/${fusionRarity}/Dist.png" style="width:${27 * SCALE * 0.75}px; height:${12 * SCALE * 0.75}px;">`;
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
        const rarityName = item.setItemRarityName ?? "None";
        let rarityStyle = `color: ${rarityColors[Object.keys(rarityColors).find(key => rarityName.includes(key)) || "None"]};`;
        if (rarityName === "Primeval") {
            rarityStyle = `background: linear-gradient(to bottom, #57e95b, #3a8390); -webkit-background-clip: text; -webkit-text-fill-color: transparent;`;
        }

        container.innerHTML += `
            <div style="text-align:center;">
                <div style="font-family: var(--font-display); font-size:20px; font-weight:600; color:#eee; margin-bottom:4px;">${item.setItemName}</div>
                <div style="display:flex; align-items:center; justify-content:center; gap:8px;">
                    <img src="${getSetIconPath(item.setItemName)}" alt="${item.setItemName}" style="height: 24px;">
                    <span style="font-size:16px; font-weight:500; ${rarityStyle}">${rarityName}</span>
                </div>
                <div style="font-size:14px; color:var(--color-text-secondary); margin-top:2px;">(${item.active?.setPoint?.current ?? 0})</div>
            </div>
        `;
    });
}

function renderFameChart(records) {
    const canvas = document.getElementById("fame-chart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

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
        ctx.strokeStyle = "rgba(72,191,240,0.1)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(paddingX, y);
        ctx.lineTo(canvas.width - paddingX, y);
        ctx.stroke();
        ctx.fillStyle = "#eee";
        ctx.fillText(value.toLocaleString(), paddingX - 6, y);
    }

    ctx.strokeStyle = "#48bfe3";
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
        ctx.fillStyle = "#eee";
        ctx.fillText(label, pt.x, canvas.height - paddingY + 4);
    });

    ctx.strokeStyle = "#4cc9f0";
    ctx.lineWidth = 4;
    ctx.beginPath();
    points.forEach((pt, i) => i === 0 ? ctx.moveTo(pt.x, pt.y) : ctx.lineTo(pt.x, pt.y));
    ctx.stroke();

    points.forEach(pt => {
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 4, 0, 2 * Math.PI);
        ctx.fillStyle = "#4cc9f0";
        ctx.shadowColor = "#4cc9f0";
        ctx.shadowBlur = 6;
        ctx.fill();
        ctx.shadowBlur = 0;
    });
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
        dateHeader.textContent = `--- ${dateStr} ---`;
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
                <img src="${beforeIcon}" class="history-icon">
                <div class="history-arrow">→</div>
                <div style="position: relative;">
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
        ctx.fillStyle = "#3ba042";
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
    document.getElementById('main-view').style.display = view === 'main' ? 'flex' : 'none';
    document.getElementById('detail-view').style.display = view === 'detail' ? 'grid' : 'none';
}

export function setLoading(isLoading) {
    document.getElementById('loading-spinner').style.display = isLoading ? 'block' : 'none';
}