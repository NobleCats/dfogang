// ===================================
//          app.js
// ===================================
import * as api from './api.js';
import * as ui from './ui.js';

const state = {
    isLoading: false,
    view: 'main',
    searchTerm: '',
    server: 'cain',
    searchResults: [],
    characterDetail: {
        profile: null,
        equipment: null,
        fameHistory: null,
        gearHistory: null,
    }
};

const serverSelect = document.getElementById('server-select');
const searchInput = document.getElementById('search-input');
const searchButton = document.getElementById('search-button');
const resultsDiv = document.getElementById('results');
const detailView = document.getElementById('detail-view');

function render() {
    ui.setLoading(state.isLoading);
    ui.switchView(state.view);

    if (state.view === 'main') {
        resultsDiv.innerHTML = '';
        if (state.searchResults.length > 0) {
            state.searchResults.forEach(profile => {
                const card = ui.createCharacterCard(profile, state.searchTerm);
                resultsDiv.appendChild(card);
            });
        } else if (state.searchTerm) {
             resultsDiv.innerHTML = `<div style="color:#f66;">No characters found for "${state.searchTerm}".</div>`;
        }
    } else if (state.view === 'detail' && state.characterDetail.profile) {
        ui.renderCharacterDetail(
            state.characterDetail.profile,
            state.characterDetail.equipment,
            state.characterDetail.fameHistory,
            state.characterDetail.gearHistory
        );
    }
}

function updateURL(view, server, name) {
    const params = new URLSearchParams();
    params.set('view', view);
    params.set('server', server);
    params.set('name', name);
    history.pushState({ view, server, name }, '', `?${params.toString()}`);
}

async function performSearch(server, name) {
    state.isLoading = true;
    state.searchTerm = name;
    state.server = server;
    render();
    
    await api.logSearch(server, name);
    state.searchResults = await api.searchCharacters(server, name);
    
    state.isLoading = false;
    render();
}

async function showCharacterDetail(server, name) {
    state.isLoading = true;
    state.view = 'detail';
    render();
    
    const [profile, equipmentResponse, fameHistory, gearHistory] = await Promise.all([
        api.getCharacterProfile(server, name),
        api.getCharacterEquipment(server, name),
        api.getFameHistory(server, name),
        api.getGearHistory(server, name),
    ]);
    
    if (profile && equipmentResponse) {
        // [FIXED] Pass the unwrapped equipment object to avoid confusion
        state.characterDetail = { 
            profile, 
            equipment: equipmentResponse.equipment, 
            fameHistory: fameHistory?.records, 
            gearHistory 
        };
    } else {
        alert('Failed to load character details.');
        state.view = 'main';
    }

    state.isLoading = false;
    render();
}

function handleSearchClick() {
    const server = serverSelect.value;
    const name = searchInput.value.trim();
    if (!name) {
        alert("Please enter a name!");
        return;
    }
    updateURL('main', server, name);
    performSearch(server, name);
}

function handleCardClick(event) {
    const card = event.target.closest('.card');
    if (!card) return;
    const { characterName, serverId } = card.dataset;
    updateURL('detail', serverId, characterName);
    showCharacterDetail(serverId, characterName);
}

function handleGoBack() {
    state.view = 'main';
    state.characterDetail = { profile: null, equipment: null, fameHistory: null, gearHistory: null };
    updateURL('main', state.server, state.searchTerm);
    render();
}

window.onpopstate = (event) => {
    if (event.state) {
        const { view, server, name } = event.state;
        if (view === 'detail') {
            showCharacterDetail(server, name);
        } else {
            performSearch(server, name);
        }
    } else {
        state.view = 'main';
        state.searchTerm = '';
        state.searchResults = [];
        searchInput.value = '';
        render();
    }
};

async function init() {
    searchButton.addEventListener('click', handleSearchClick);
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handleSearchClick();
    });
    resultsDiv.addEventListener('click', handleCardClick);
    detailView.addEventListener('click', (e) => {
        if (e.target.classList.contains('back-button')) {
            handleGoBack();
        }
    });

    const params = new URLSearchParams(window.location.search);
    const view = params.get('view');
    const server = params.get('server');
    const name = params.get('name');

    if (name && server) {
        searchInput.value = name;
        serverSelect.value = server;

        if (view === 'detail') {
            await showCharacterDetail(server, name);
        } else {
            await performSearch(server, name);
        }
    }
}

document.addEventListener('DOMContentLoaded', init);
