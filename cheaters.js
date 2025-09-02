document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = 'https://api.dfogang.com';

    const elements = {
        cheaterResults: document.getElementById('cheater-results'),
        cardGrid: document.getElementById('cheater-card-grid'),
        loader: document.getElementById('cheater-loader'),
        noResults: document.getElementById('cheater-no-results')
    };

    let state = {
        cheaterData: []
    };

    function createCheaterCard(profile) {
        const spritePath = `assets/characters/${profile.jobName}.png`;

        const card = document.createElement('div');
        card.className = 'card';

        card.dataset.characterName = profile.characterName;
        card.dataset.serverId = profile.serverId;

        card.innerHTML = `
            <div style="position: absolute; top: 16px; right: 16px; text-align: right; z-index: 10;">
                <div style="font-size: 0.8em; color:var(--color-text-secondary);">${profile.serverId}</div>
                <div style="font-size: 0.7em; color:#ff4444; margin-top:4px;">Flagged</div>
            </div>
            <div class="character-sprite-container"> 
                <img src="${spritePath}" alt="${profile.jobName}"> 
            </div>
            <div style="color:var(--color-text-secondary); font-weight:500;">${profile.adventureName ?? '-'}</div>
            <div style="font-family: var(--font-display); color:#eee; font-size:1.8em; font-weight:600;">
                ${profile.characterName ?? '-'}
            </div>
            <div style="color:#A0844B; font-size:0.8em;">[${profile.jobGrowName ?? '-'}]</div>
            <div style="margin-top:6px; font-size:0.8em; color:var(--color-text-secondary);">
                Flagged at: ${new Date(profile.flagged_at).toLocaleString()}
            </div>
        `;
        return card;
    }

    async function fetchAndDisplayCheaters() {
        setLoading(true);
        try {
            const url = `${API_BASE_URL}/api/v1/cheaters`;
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const data = await response.json();
            if (data.cheaters && data.cheaters.length > 0) {
                state.cheaterData = data.cheaters;
                renderCheaterCards(data.cheaters);
            } else {
                showNoResults();
            }
        } catch (error) {
            console.error('Error fetching cheaters:', error);
            showNoResults('Failed to load cheaters. Please try again later.');
        } finally {
            setLoading(false);
        }
    }

    function renderCheaterCards(cheaterData) {
        elements.cardGrid.innerHTML = '';
        cheaterData.forEach(item => {
            const card = createCheaterCard(item);
            elements.cardGrid.appendChild(card);
        });
    }

    function setLoading(isLoading) {
        elements.loader.style.display = isLoading ? 'block' : 'none';
        elements.cardGrid.style.display = isLoading ? 'none' : 'grid';
        if (isLoading) elements.noResults.style.display = 'none';
    }

    function showNoResults(message = 'No cheaters found.') {
        elements.cardGrid.innerHTML = '';
        elements.noResults.textContent = message;
        elements.noResults.style.display = 'block';
    }

    elements.cardGrid.addEventListener('click', (event) => {
        const card = event.target.closest('.card');
        if (!card) return;

        const characterName = card.dataset.characterName;
        const serverId = card.dataset.serverId;

        if (!characterName || !serverId) return;

        const baseUrl = window.location.origin;
        const newUrl = `${baseUrl}/?view=detail&server=${serverId}&name=${characterName}`;

        window.location.href = newUrl;
    });

    function initializePage() {
        fetchAndDisplayCheaters();
    }

    initializePage();
});
