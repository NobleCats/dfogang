// ===================================
//          ui.js
// ===================================
import * as components from './components.js';

function render(state) {
    setLoading(state.isLoading);
    switchView(state.view);

    if (state.view === 'main') {
        const resultsDiv = document.getElementById('results');
        resultsDiv.innerHTML = '';
        if (state.searchResults.length > 0) {
            state.searchResults.forEach(profile => {
                const card = components.createCharacterCard(profile, state.searchTerm);
                resultsDiv.appendChild(card);
            });
        } else if (state.searchTerm) {
             resultsDiv.innerHTML = `<div style="color:#f66;">No characters found for "${state.searchTerm}".</div>`;
        }
    } else if (state.view === 'detail' && state.characterDetail.profile) {
        const detailView = document.getElementById('detail-view');
        detailView.innerHTML = ''; // Clear previous detail view
        const detailElement = components.createDetailView(state.characterDetail);
        detailView.appendChild(detailElement);

        // After the main structure is in the DOM, render canvas elements
        components.renderCharacterCanvas(state.characterDetail.profile, state.characterDetail.equipment);
        components.renderFameChart(state.characterDetail.fameHistory);
        components.renderHistoryPanel(state.characterDetail.gearHistory);
        components.renderSetItems(state.characterDetail.gearHistory);
    }
}

function switchView(view) {
    document.getElementById('main-view').style.display = view === 'main' ? 'flex' : 'none';
    document.getElementById('detail-view').style.display = view === 'detail' ? 'block' : 'none';
}

function setLoading(isLoading) {
    document.getElementById('loading-spinner').style.display = isLoading ? 'block' : 'none';
}

export { render, setLoading };