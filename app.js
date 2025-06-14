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
        setItemInfo: null,
        fameHistory: null,
        gearHistory: null,
    }
};

function setState(newState) {
    Object.assign(state, newState);
    ui.render(state);
}

const serverSelect = document.getElementById('server-select');
const searchInput = document.getElementById('search-input');
const searchButton = document.getElementById('search-button');
const resultsDiv = document.getElementById('results');
const detailView = document.getElementById('detail-view');

function updateURL(view, server, name) {
    const params = new URLSearchParams();
    params.set('view', view);
    params.set('server', server);
    params.set('name', name);
    history.pushState({ view, server, name }, '', `?${params.toString()}`);
}

async function performSearch(server, name) {
    setState({ isLoading: true, searchTerm: name, server: server });
    await api.logSearch(server, name);
    const results = await api.searchCharacters(server, name);
    setState({ isLoading: false, searchResults: results });
}

async function showCharacterDetail(server, name) {
    setState({ isLoading: true, view: 'detail' });
    
    const [profile, equipmentResponse, fameHistory, gearHistory] = await Promise.all([
        api.getCharacterProfile(server, name),
        api.getCharacterEquipment(server, name),
        api.getFameHistory(server, name),
        api.getGearHistory(server, name),
    ]);
    
    if (profile && equipmentResponse) {
        const equipment = equipmentResponse.equipment;
        setState({
            isLoading: false,
            characterDetail: { 
                profile, 
                equipment: equipment?.equipment,
                setItemInfo: equipment?.setItemInfo,
                fameHistory: fameHistory?.records, 
                gearHistory 
            }
        });
    } else {
        alert('Failed to load character details.');
        setState({ isLoading: false, view: 'main' });
    }
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
    setState({
        view: 'main',
        characterDetail: { profile: null, equipment: null, setItemInfo: null, fameHistory: null, gearHistory: null }
    });
    updateURL('main', state.server, state.searchTerm);
}

window.onpopstate = (event) => {
    if (event.state) {
        const { view, server, name } = event.state;
        if (view === 'detail') {
            showCharacterDetail(server, name);
        } else {
            setState({ view: 'main', server, searchTerm: name });
            performSearch(server, name);
        }
    } else {
        setState({
            view: 'main',
            searchTerm: '',
            searchResults: [],
            server: 'cain'
        });
        searchInput.value = '';
        serverSelect.value = 'cain';
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
