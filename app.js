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
    allSearchResults: [],
    displayedResults: [],
    resultsPerPage: 8,
    resultsPerScroll: 4,
    searchResults: [],
    characterDetail: {
        profile: null,
        equipment: null,
        setItemInfo: null,
        fameHistory: null,
        gearHistory: null,
        isBuffer: false,
        buffData: null,
    },
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
let mainViewDpsOptions = null;
const resultsWrapper = document.getElementById('results-wrapper');

function render() {
    ui.setLoading(state.isLoading || state.dps.isCalculating);
    ui.switchView(state.view);

    if (state.view === 'main') {
        ui.renderMainDpsOptions(mainViewDpsOptions, state.dps.options);

        const resultsSection = document.querySelector('.results-section');
        const announcementSection = document.querySelector('.announcement-section');
        if (!state.searchTerm || (state.searchTerm && !state.isLoading && state.allSearchResults.length === 0)) {
            if (resultsSection) {
                resultsSection.style.display = 'none';
            }
            if (announcementSection) {
                announcementSection.style.display = 'block';
            }
        } else {
            if (resultsSection) {
                resultsSection.style.display = 'block';
            }
            if (announcementSection) {
                announcementSection.style.display = 'none';
            }
            resultsDiv.innerHTML = '';

            if (state.displayedResults.length > 0) {
                state.displayedResults.forEach(profile => {
                    const dpsToShow = (profile.dps && typeof profile.dps === 'object')
                        ? (state.dps.options.average_set_dmg ? profile.dps.normalized : profile.dps.normal)
                        : null;

                    const card = ui.createCharacterCard(profile, state.searchTerm, dpsToShow, profile.is_buffer);
                    resultsDiv.appendChild(card);
                });
            } else if (state.searchTerm && state.isLoading) {
                resultsDiv.innerHTML = `<div style="color:var(--color-text-secondary);">Searching for "${state.searchTerm}"...</div>`;
            } else if (state.searchTerm && !state.isLoading && state.allSearchResults.length === 0) {
                resultsDiv.innerHTML = `<div style="color:#f66;">No characters found for "${state.searchTerm}".</div>`;
            }
        }
        ui.showMoreResultsIndicator(state.displayedResults.length < state.allSearchResults.length);

    } else if (state.view === 'detail' && state.characterDetail.profile) {
        ui.renderCharacterDetail(
            state.characterDetail.profile,
            state.characterDetail.equipment,
            state.characterDetail.setItemInfo,
            state.characterDetail.fameHistory,
            state.characterDetail.gearHistory,
            state.dps,
            state.characterDetail.isBuffer,
            state.characterDetail.buffData 
        );
    }
}

function updateURL(view, server, name) {
    const params = new URLSearchParams();
    params.set('view', view);
    params.set('server', server);
    params.set('name', name);
    params.set('average_set_dmg', state.dps.options.average_set_dmg.toString());
    history.pushState({ view, server, name, average_set_dmg: state.dps.options.average_set_dmg }, '', `?${params.toString()}`);
}

async function performSearch(server, name) {
    state.isLoading = true;
    state.searchTerm = name;
    state.server = server;
    state.allSearchResults = [];
    state.displayedResults = [];
    render();

    const announcementSection = document.querySelector('.announcement-section');
    if (announcementSection) {
        announcementSection.style.display = 'none';
    }

    await api.logSearch(server, name);
    const results = await api.searchCharacters(server, name, state.dps.options.average_set_dmg);

    state.allSearchResults = results;
    state.displayedResults = results.slice(0, state.resultsPerPage);

    state.isLoading = false;
    render();
}

function loadMoreResults() {
    if (state.isLoading) return;
    if (state.displayedResults.length >= state.allSearchResults.length) return;

    state.isLoading = true;
    render();

    setTimeout(() => {
        const nextStartIndex = state.displayedResults.length;
        const nextEndIndex = nextStartIndex + state.resultsPerScroll;
        const newResults = state.allSearchResults.slice(nextStartIndex, nextEndIndex);

        state.displayedResults.push(...newResults);
        state.isLoading = false;
        render();
    }, 300);
}



function handleScroll() {
    const scrollHeight = document.documentElement.scrollHeight;
    const scrollTop = document.documentElement.scrollTop || document.body.scrollTop;
    const clientHeight = document.documentElement.clientHeight;

    if (scrollTop + clientHeight >= scrollHeight - 100) {
        loadMoreResults();
    }
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

    let isBuffer = false;
    let dpsResult = null;
    let buffData = null;

    if (profile && profile.characterId) {
        const buffSkillInfo = await api.getCharacterBuffSkill(server, profile.characterId);
        const bufferSkills = ["Divine Invocation", "Valor Blessing", "Forbidden Curse", "Lovely Tempo"];
        const buffSkillName = buffSkillInfo?.skill?.buff?.skillInfo?.name;
        if (buffSkillName && bufferSkills.some(skill => buffSkillName.includes(skill))) {
            isBuffer = true;
            buffData = await api.getCharacterBuffPower(server, profile.characterId); 
        } else {
            dpsResult = await api.getCharacterDps(server, name, state.dps.options);
        }
    }

    if (profile && equipmentResponse) {
        const equipment = equipmentResponse.equipment;
        state.characterDetail = {
            profile: { ...profile, server: server, characterName: name },
            equipment: equipment?.equipment,
            setItemInfo: equipment?.setItemInfo,
            fameHistory: fameHistory?.records,
            gearHistory,
            isBuffer: isBuffer,
            buffData: buffData,
        };
        state.dps.result = dpsResult;
    } else {
        console.error('Failed to load character details.');
        state.view = 'main';
    }

    state.isLoading = false;
    render();
}

async function recalculateDps() {
    if (!state.characterDetail.profile) return;
    if (state.characterDetail.isBuffer) { 
        console.log("Buffer character, skipping DPS recalculation.");
        return;
    }

    state.dps.isCalculating = true;
    render();

    const { server, characterName } = state.characterDetail.profile;
    const newDpsResult = await api.getCharacterDps(server, characterName, state.dps.options);
    state.dps.result = newDpsResult;

    state.dps.isCalculating = false;
    render();
}

function handleMainDpsToggleClick(event) {
    const toggle = event.target.closest('[data-dps-option]');
    if (!toggle) return;

    const optionName = toggle.dataset.dpsOption;
    const optionValue = toggle.dataset.dpsValue === 'true';

    if (state.dps.options[optionName] === optionValue) return;

    state.dps.options[optionName] = optionValue;

    if (state.searchTerm) {
        performSearch(state.server, state.searchTerm);
    }
    updateURL(state.view, state.server, state.searchTerm);
    render();
}


function handleDpsToggleClick(event) {
    const toggle = event.target.closest('[data-dps-option]');
    if (!toggle) return;

    const optionName = toggle.dataset.dpsOption;
    const optionValue = toggle.dataset.dpsValue === 'true';

    if (state.characterDetail.isBuffer) {
        console.log("Buffer character, cannot change DPS options.");
        return;
    }

    if (state.dps.options[optionName] === optionValue) return;

    state.dps.options[optionName] = optionValue;
    recalculateDps();
}

function handleSearchClick() {
    const server = serverSelect.value;
    const name = searchInput.value.trim();
    if (!name) {
        console.warn("Please enter a name!");
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
    state.characterDetail = { profile: null, equipment: null, setItemInfo: null, fameHistory: null, gearHistory: null, isBuffer: false, buffData: null };
    updateURL('main', state.server, state.searchTerm);
    render();
}

window.onpopstate = (event) => {
    if (event.state) {
        const { view, server, name, average_set_dmg } = event.state;
        if (average_set_dmg !== undefined) {
             state.dps.options.average_set_dmg = (average_set_dmg === 'true');
        }
        if (view === 'detail') {
            showCharacterDetail(server, name);
        } else {
            performSearch(server, name);
        }
    } else {
        state.view = 'main';
        state.searchTerm = '';
        state.allSearchResults = [];
        state.displayedResults = [];
        searchInput.value = '';
        state.dps.options.average_set_dmg = false;
        render();
    }
};

function setupAccordions() {
    document.querySelectorAll('.accordion-header').forEach(header => {
        header.addEventListener('click', () => {
            const content = document.getElementById(`accordion-content-${header.dataset.accordionId}`);
            if (content) {
                document.querySelectorAll('.accordion-header.active').forEach(activeHeader => {
                    if (activeHeader !== header) {
                        activeHeader.classList.remove('active');
                        const activeContent = document.getElementById(`accordion-content-${activeHeader.dataset.accordionId}`);
                        activeContent.classList.remove('open');
                        activeContent.style.maxHeight = 0;
                    }
                });

                header.classList.toggle('active');
                content.classList.toggle('open');

                if (content.classList.contains('open')) {
                    content.style.maxHeight = content.scrollHeight + "px";
                } else {
                    content.style.maxHeight = 0;
                }
            }
        });
    });
}

async function init() {
    mainViewDpsOptions = document.getElementById('main-view-dps-options');

    searchButton.addEventListener('click', handleSearchClick);
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handleSearchClick();
    });
    resultsDiv.addEventListener('click', handleCardClick);
    detailView.addEventListener('click', (e) => {
        if (e.target.classList.contains('back-button')) {
            handleGoBack();
        }
        if (e.target.closest('.dps-toggle-switch')) {
            handleDpsToggleClick(e);
        }
    });
    if (mainViewDpsOptions) {
        mainViewDpsOptions.addEventListener('click', (e) => {
            if (e.target.closest('.dps-toggle-switch')) {
                handleMainDpsToggleClick(e);
            }
        });
    }

    const resultsSection = document.querySelector('.results-section');
    if (resultsSection) {
        resultsSection.addEventListener('scroll', handleScroll);
    }

    window.addEventListener('scroll', handleScroll);

    const params = new URLSearchParams(window.location.search);
    const view = params.get('view');
    const server = params.get('server');
    const name = params.get('name');
    const average_set_dmg = params.get('average_set_dmg');

    if (average_set_dmg !== null) {
        state.dps.options.average_set_dmg = (average_set_dmg === 'true');
    }

    if (name && server) {
        searchInput.value = name;
        serverSelect.value = server;

        if (view === 'detail') {
            await showCharacterDetail(server, name);
        } else {
            await performSearch(server, name);
        }
    }
    setupAccordions();
    render();
}

document.addEventListener('DOMContentLoaded', init);