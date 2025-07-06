// ranking.js
document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = 'https://api.dfogang.com';
    const CLASSES = {
        "Slayer (M)": ["Neo: Blade Master", "Neo: Soul Bender", "Neo: Berserker", "Neo: Asura", "Neo: Ghostblade"],
        "Slayer (F)": ["Neo: Sword Master", "Neo: Demon Slayer", "Neo: Vagabond", "Neo: Dark Templar", "Neo: Spectre"],
        "Fighter (M)": ["Neo: Nen Master", "Neo: Striker", "Neo: Brawler", "Neo: Grappler"],
        "Fighter (F)": ["Neo: Nen Master", "Neo: Striker", "Neo: Brawler", "Neo: Grappler"],
        "Mage (M)": ["Neo: Elemental Bomber", "Neo: Glacial Master", "Neo: Blood Mage", "Neo: Swift Master", "Neo: Dimension Walker"],
        "Mage (F)": ["Neo: Elementalist", "Neo: Summoner", "Neo: Witch", "Neo: Battle Mage", "Neo: Enchantress"],
        "Priest (M)": ["Neo: Crusader", "Neo: Monk", "Neo: Exorcist", "Neo: Avenger"],
        "Priest (F)": ["Neo: Crusader", "Neo: Inquisitor", "Neo: Shaman", "Neo: Mistress"],
        "Gunner (M)": ["Neo: Ranger", "Neo: Launcher", "Neo: Mechanic", "Neo: Spitfire", "Neo: Blitz"],
        "Gunner (F)": ["Neo: Ranger", "Neo: Launcher", "Neo: Mechanic", "Neo: Spitfire"],
        "Thief": ["Neo: Rogue", "Neo: Necromancer", "Neo: Kunoichi", "Neo: Shadow Dancer"],
        "Agent": ["Neo: Secret Agent", "Neo: Troubleshooter", "Neo: Hitman", "Neo: Specialist"],
        "Knight": ["Neo: Elven Knight", "Neo: Chaos", "Neo: Dragon Knight", "Neo: Lightbringer"],
        "Demonic Lancer": ["Neo: Vanguard", "Neo: Skirmisher", "Neo: Impaler", "Neo: Dragoon"],
        "Creator": ["Neo: Creator"],
        "Dark Knight": ["Neo: Dark Knight"],
        "Archer": ["Neo: Muse", "Neo: Traveler", "Neo: Hunter", "Neo: Vigilante"],
    };
    const BUFFER_CLASSES = ['Neo: Enchantress', 'Neo: Crusader', 'Neo: Muse'];

    const elements = {
        classGrid: document.getElementById('class-grid'),
        rankingResults: document.getElementById('ranking-results'),
        rankingTitle: document.getElementById('ranking-title'),
        cardGrid: document.getElementById('ranking-card-grid'),
        loader: document.getElementById('loader'),
        noResults: document.getElementById('no-results'),
        pagination: document.getElementById('pagination'),
        btnSortByScore: document.getElementById('sort-by-score'),
        btnSortByFame: document.getElementById('sort-by-fame'),
    };

    let state = { jobName: null, sortBy: 'dps', page: 1, limit: 12, totalPages: 1, isBuffer: false };

    const rarityColors = { "None": "#FFFFFF", "Rare": "#B36BFF", "Unique": "#FF00FF", "Legendary": "#FF7800", "Epic": "#FFB400" };
    const SET_CATEGORIES = ["Dragon", "Magic", "Alpha", "Shadow", "Ethereal", "Valkyrie", "Nature", "Fairy", "Energy", "Serendipity", "Cleansing", "Gold", "Tales"];
    
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

    function createCharacterCard(profile, dpsToShow, isBuffer) {
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
        card.className = `card ${isBuffer ? 'is-buffer' : ''}`;
        
        const scoreValue = isBuffer ? (profile.total_buff_score != null ? profile.total_buff_score.toLocaleString() : 'N/A') : (dpsToShow != null ? dpsToShow.toLocaleString() : 'N/A');
        const scoreDisplay = `<span class="card-score-value">${scoreValue}</span>`;

        card.innerHTML = `
            <div style="position: absolute; top: 16px; right: 16px; text-align: right; z-index: 10;">
                <div style="font-size: 0.8em; color:var(--color-text-secondary);">${profile.serverId}</div>
                <div style="display:flex; align-items:center; justify-content: flex-end; margin-top:4px;">
                    <img src="assets/image/fame.png" alt="Fame" style="width:15px; height:13px; margin-right:4px;">
                    <span style="color:var(--color-fame); font-size:0.9em; font-weight: 500;">${(profile.fame || 0).toLocaleString()}</span>
                </div>
            </div>
            <div class="character-sprite-container"> <img src="${spritePath}" alt="${profile.jobName}"> </div>

            <div style="color:var(--color-text-secondary); font-weight:500;">${profile.adventureName ?? '-'}</div>
            <div style="font-family: var(--font-display); color:#eee; font-size:1.8em; font-weight:600;">${profile.characterName ?? '-'}</div>
            <div style="color:#A0844B; font-size:0.8em;">[${profile.jobGrowName ?? '-'}]</div>
            <div style="display: flex; align-items: center; gap: 2px;"> <img src="${setIconPath}" alt="Set Icon"> <span style="${rarityStyle};"> ${rarityName}</span>
                ${profile.setPoint > 0 ? `<span style="color:#aaa; font-size: 0.9em; margin-left: 4px;">(${profile.setPoint})</span>` : ''}
            </div>

            <div style="display: flex; align-items: center; gap: 6px; font-family: var(--font-dfo);">
                <span style="font-size: 1em; margin-top: 2.1px; color: var(--color-text-secondary);">${isBuffer ? 'Buff Score' : 'DPS Score'}</span>
                ${scoreDisplay}
            </div>
        `;
        return card;
    }

    async function fetchAndDisplayRankings() {
        if (!state.jobName) return;
        setLoading(true);
        try {
            const url = `${API_BASE_URL}/api/v1/ranking/${encodeURIComponent(state.jobName)}?sort_by=${state.sortBy}&page=${state.page}&limit=${state.limit}`;
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            
            const data = await response.json();
            
            if (data.ranking && data.ranking.length > 0) {
                renderRankingCards(data.ranking);
                renderPagination(data.pagination);
            } else {
                showNoResults();
            }
        } catch (error) {
            console.error('Error fetching rankings:', error);
            showNoResults('Failed to load data. Please try again later.');
        } finally {
            setLoading(false);
        }
    }

    function renderRankingCards(rankingData) {
        elements.cardGrid.innerHTML = '';
        rankingData.forEach(item => {
            const scoreToShow = state.isBuffer ? item.total_buff_score : item.dps_normalized;
            const profileData = { ...item };
            if (!profileData.jobName && state.jobName) {
                 profileData.jobName = state.jobName.includes(': ') ? state.jobName.split(': ')[1] : state.jobName;
            }
            const card = createCharacterCard(profileData, scoreToShow, state.isBuffer);
            elements.cardGrid.appendChild(card);
        });
    }

    function renderPagination({ current_page, total_pages }) {
        state.totalPages = total_pages;
        elements.pagination.innerHTML = '';
        if (total_pages <= 0) return;

        elements.pagination.innerHTML = `
            <button id="prev-page" ${current_page === 1 ? 'disabled' : ''}>&lt;</button>
            <span>${current_page} / ${total_pages}</span>
            <button id="next-page" ${current_page === total_pages ? 'disabled' : ''}>&gt;</button>
        `;

        document.getElementById('prev-page').addEventListener('click', () => { if(state.page > 1) { state.page--; fetchAndDisplayRankings(); } });
        document.getElementById('next-page').addEventListener('click', () => { if(state.page < state.totalPages) { state.page++; fetchAndDisplayRankings(); } });
    }
    
    function setLoading(isLoading) {
        elements.loader.style.display = isLoading ? 'block' : 'none';
        elements.cardGrid.style.display = isLoading ? 'none' : 'grid';
        elements.pagination.style.display = isLoading ? 'none' : 'flex';
        if (isLoading) elements.noResults.style.display = 'none';
    }

    function renderClassGrid() {
        elements.classGrid.innerHTML = '';
        Object.values(CLASSES).flat().forEach(jobName => {
            const card = document.createElement('div');
            card.className = 'class-card';
            card.textContent = jobName;
            card.dataset.jobName = jobName;
            card.addEventListener('click', () => handleClassSelect(jobName));
            elements.classGrid.appendChild(card);
        });
    }

    function handleClassSelect(jobName) {
        state.jobName = jobName;
        state.page = 1;
        state.isBuffer = BUFFER_CLASSES.includes(jobName);
        state.sortBy = state.isBuffer ? 'buff_score' : 'dps';
        
        updateSortButtonsText();
        updateActiveSortButton();
        fetchAndDisplayRankings();

        elements.classGrid.style.display = 'none';
        elements.rankingResults.style.display = 'block';
        elements.rankingTitle.textContent = `${jobName} Ranking`;
        window.scrollTo(0, 0);
    }

    function updateSortButtonsText() {
        elements.btnSortByScore.textContent = state.isBuffer ? "Buff Score" : "Damage";
    }

    function updateActiveSortButton() {
        const scoreSortValue = state.isBuffer ? 'buff_score' : 'dps';
        elements.btnSortByScore.classList.toggle('active', state.sortBy === scoreSortValue);
        elements.btnSortByFame.classList.toggle('active', state.sortBy === 'fame');
    }

    function showNoResults(message = 'No ranking data found for this class.') {
        elements.cardGrid.innerHTML = '';
        elements.pagination.innerHTML = '';
        elements.noResults.textContent = message;
        elements.noResults.style.display = 'block';
    }

    elements.btnSortByScore.addEventListener('click', () => {
        const newSortBy = state.isBuffer ? 'buff_score' : 'dps';
        if (state.sortBy === newSortBy) return;
        state.sortBy = newSortBy;
        state.page = 1;
        updateActiveSortButton();
        fetchAndDisplayRankings();
    });

    elements.btnSortByFame.addEventListener('click', () => {
        if (state.sortBy === 'fame') return;
        state.sortBy = 'fame';
        state.page = 1;
        updateActiveSortButton();
        fetchAndDisplayRankings();
    });

    renderClassGrid();
});