// -------------------
//      app.js
// (메인 로직 및 상태 관리)
// -------------------
import * as api from './api.js';
import * as ui from './ui.js';

// 애플리케이션 상태
const state = {
    isLoading: false,
    view: 'main', // 'main' or 'detail'
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

// DOM 요소
const serverSelect = document.getElementById('server-select');
const searchInput = document.getElementById('search-input');
const searchButton = document.getElementById('search-button');
const resultsDiv = document.getElementById('results');
const detailView = document.getElementById('detail-view');

// 렌더링 함수: 상태에 따라 UI를 업데이트하는 유일한 통로
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

// ---- 로직 함수들 ----

// URL 상태를 업데이트하고 history에 푸시하는 함수
function updateURL(view, server, name) {
    const params = new URLSearchParams();
    params.set('view', view);
    params.set('server', server);
    params.set('name', name);
    history.pushState({ view, server, name }, '', `?${params.toString()}`);
}

// 검색 수행
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

// 캐릭터 상세 정보 표시
async function showCharacterDetail(server, name) {
    state.isLoading = true;
    state.view = 'detail';
    render();
    
    const [profile, equipment, fameHistory, gearHistory] = await Promise.all([
        api.getCharacterProfile(server, name),
        api.getCharacterEquipment(server, name),
        api.getFameHistory(server, name),
        api.getGearHistory(server, name),
    ]);
    
    if (profile && equipment) {
        state.characterDetail = { profile, equipment, fameHistory: fameHistory?.records, gearHistory };
    } else {
        alert('Failed to load character details.');
        state.view = 'main'; // 실패 시 메인으로 복귀
    }

    state.isLoading = false;
    render();
}

// ---- 이벤트 핸들러 ----

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
    // URL을 검색 결과 화면으로 되돌리거나 메인으로 보냄
    updateURL('main', state.server, state.searchTerm);
    render();
}

// 브라우저 뒤로가기/앞으로가기 처리
window.onpopstate = (event) => {
    if (event.state) {
        const { view, server, name } = event.state;
        if (view === 'detail') {
            showCharacterDetail(server, name);
        } else {
            performSearch(server, name);
        }
    } else {
        // 초기 상태로 복귀
        state.view = 'main';
        state.searchTerm = '';
        state.searchResults = [];
        searchInput.value = '';
        render();
    }
};

// --- 초기화 ---
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

    // 페이지 로드 시 URL 파라미터 확인 및 처리
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