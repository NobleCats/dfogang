// ranking.js
document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = 'https://api.dfogang.com';
    const JOB_GROUPS = {
        "Slayer (M)": ["Blade Master", "Soul Bender", "Berserker", "Asura", "Ghostblade"],
        "Slayer (F)": ["Sword Master", "Demon Slayer", "Vagabond", "Dark Templar", "Spectre"],
        "Fighter (M)": ["Nen Master", "Striker", "Brawler", "Grappler"],
        "Fighter (F)": ["Nen Master", "Striker", "Brawler", "Grappler"],
        "Mage (M)": ["Elemental Bomber", "Glacial Master", "Blood Mage", "Swift Master", "Dimension Walker"],
        "Mage (F)": ["Elementalist", "Summoner", "Witch", "Battle Mage", "Enchantress"],
        "Priest (M)": ["Crusader", "Monk", "Exorcist", "Avenger"],
        "Priest (F)": ["Crusader", "Inquisitor", "Shaman", "Mistress"],
        "Gunner (M)": ["Ranger", "Launcher", "Mechanic", "Spitfire", "Blitz"],
        "Gunner (F)": ["Ranger", "Launcher", "Mechanic", "Spitfire"],
        "Thief": ["Rogue", "Necromancer", "Kunoichi", "Shadow Dancer"],
        "Agent": ["Secret Agent", "Troubleshooter", "Hitman", "Specialist"],
        "Knight": ["Elven Knight", "Chaos", "Dragon Knight", "Lightbringer"],
        "Demonic Lancer": ["Vanguard", "Skirmisher", "Impaler", "Dragoon"],
        "Creator": ["Creator"],
        "Dark Knight": ["Dark Knight"],
        "Archer": ["Muse", "Traveler", "Hunter", "Vigilante"],
    };
    const NEO_PREFIX = "Neo: ";
    const BUFFER_CLASSES = ['Enchantress', 'Crusader', 'Muse'];

    const selectionContainer = document.getElementById('class-selection-container');
    const elements = {
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

    function updateURL(jobName) {
        const url = new URL(window.location);
        if (jobName) {
            url.searchParams.set('class', jobName);
        } else {
            url.searchParams.delete('class');
        }
        history.pushState({ jobName: jobName }, '', url);
    }

    function renderClassSelection() {
        selectionContainer.innerHTML = '';

        for (const groupName in JOB_GROUPS) {
            const groupDiv = document.createElement('div');
            groupDiv.className = 'class-group';

            const title = document.createElement('h3');
            title.className = 'class-group-title';
            title.textContent = groupName;
            groupDiv.appendChild(title);

            const gridDiv = document.createElement('div');
            gridDiv.className = 'class-grid';

            JOB_GROUPS[groupName].forEach(jobName => {
                const card = document.createElement('div');
                card.className = 'class-card';
                
                const imageName = jobName.replace(/ /g, '').toLowerCase();
                const staticImgPath = `assets/characters/${groupName}/${imageName}.png`;
                const animatedGifPath = `assets/characters/${groupName}/${imageName}.gif`;

                card.innerHTML = `
                    <div class="class-card-bg" style="background-image: url('${staticImgPath}');"></div>
                    <div class="class-card-gif" style="background-image: url('${animatedGifPath}');"></div>
                    <span class="class-card-name">${NEO_PREFIX}${jobName}</span>
                `;
                
                const fullJobName = `${NEO_PREFIX}${jobName}`;
                card.addEventListener('click', () => handleClassSelect(fullJobName));
                gridDiv.appendChild(card);
            });

            groupDiv.appendChild(gridDiv);
            selectionContainer.appendChild(groupDiv);
        }
    }

    function handleClassSelect(fullJobName) {
        if (!fullJobName) {
            selectionContainer.style.display = 'block';
            elements.rankingResults.style.display = 'none';
            updateURL(null);
            return;
        }

        state.jobName = fullJobName;
        state.page = 1;
        const baseJobName = fullJobName.replace(NEO_PREFIX, '');
        state.isBuffer = BUFFER_CLASSES.includes(baseJobName);
        state.sortBy = state.isBuffer ? 'buff_score' : 'dps';

        updateSortButtonsText();
        updateActiveSortButton();
        fetchAndDisplayRankings();

        selectionContainer.style.display = 'none';
        elements.rankingResults.style.display = 'block';
        elements.rankingTitle.textContent = `${fullJobName} Ranking`;

        updateURL(fullJobName);
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
                 const baseJobName = state.jobName.replace(NEO_PREFIX, '');
                 const jobGroup = Object.keys(JOB_GROUPS).find(group => JOB_GROUPS[group].includes(baseJobName));
                 if (jobGroup) {
                    profileData.jobName = jobGroup;
                 }
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

    window.addEventListener('popstate', (event) => {
        const params = new URLSearchParams(window.location.search);
        const classNameFromURL = params.get('class') || null;
        handleClassSelect(classNameFromURL);
    });
    window.addEventListener('popstate', (event) => {
        const jobName = event.state?.jobName || null;
        handleClassSelect(jobName);
    });

    function initializePage() {
        renderClassSelection();
        const params = new URLSearchParams(window.location.search);
        const classNameFromURL = params.get('class');

        if (classNameFromURL) {
            handleClassSelect(classNameFromURL);
        }
    }

    initializePage();
});