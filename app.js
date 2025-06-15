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
    },
    // [NEW] DPS 계산기 상태 추가
    dps: {
        options: {
            cleansing_cdr: true,
            weapon_cdr: false,
            average_set_dmg: false,
        },
        result: null,
        isCalculating: false,
    }
};

const serverSelect = document.getElementById('server-select');
const searchInput = document.getElementById('search-input');
const searchButton = document.getElementById('search-button');
const resultsDiv = document.getElementById('results');
const detailView = document.getElementById('detail-view');

function render() {
    ui.setLoading(state.isLoading || state.dps.isCalculating);
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
        // [MODIFIED] DPS 결과도 렌더링 함수에 전달
        ui.renderCharacterDetail(
            state.characterDetail.profile,
            state.characterDetail.equipment,
            state.characterDetail.setItemInfo,
            state.characterDetail.fameHistory,
            state.characterDetail.gearHistory,
            state.dps // DPS 상태 전체를 전달
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
    // [NEW] 상세 보기로 전환 시 DPS 옵션 초기화
    state.dps.options = { cleansing_cdr: true, weapon_cdr: false, average_set_dmg: false };
    render();
    
    const [profile, equipmentResponse, fameHistory, gearHistory, dpsResult] = await Promise.all([
        api.getCharacterProfile(server, name),
        api.getCharacterEquipment(server, name),
        api.getFameHistory(server, name),
        api.getGearHistory(server, name),
        api.getCharacterDps(server, name, state.dps.options)
    ]);
    
    if (profile && equipmentResponse) {
        const equipment = equipmentResponse.equipment;
        state.characterDetail = { 
            profile, 
            equipment: equipment?.equipment,
            setItemInfo: equipment?.setItemInfo,
            fameHistory: fameHistory?.records, 
            gearHistory 
        };
        // [NEW] 가져온 DPS 결과 저장
        state.dps.result = dpsResult;
    } else {
        alert('Failed to load character details.');
        state.view = 'main';
    }

    state.isLoading = false;
    render();
}

async function recalculateDps() {
    if (!state.characterDetail.profile) return;
    
    state.dps.isCalculating = true;
    render(); // 로딩 스피너 표시

    const { server, characterName } = state.characterDetail.profile;
    const newDpsResult = await api.getCharacterDps(server, characterName, state.dps.options);
    state.dps.result = newDpsResult;

    state.dps.isCalculating = false;
    render(); // 새로운 DPS 값으로 UI 업데이트
}

function handleDpsToggleClick(event) {
    const toggle = event.target.closest('[data-dps-option]');
    if (!toggle) return;

    const optionName = toggle.dataset.dpsOption;
    const optionValue = toggle.dataset.dpsValue === 'true';

    // 이미 선택된 옵션이면 무시
    if (state.dps.options[optionName] === optionValue) return;

    state.dps.options[optionName] = optionValue;
    recalculateDps();
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
    state.characterDetail = { profile: null, equipment: null, setItemInfo: null, fameHistory: null, gearHistory: null };
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
    detailView.addEventListener('click', (e) => {
        if (e.target.closest('.dps-toggle-switch')) {
            handleDpsToggleClick(e);
        }
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
