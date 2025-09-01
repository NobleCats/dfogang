// ===================================
//         cheaters.js
// ===================================
import * as api from './api.js';
import * as ui from './ui.js';

const elements = {
    cardGrid: document.getElementById('cheater-card-grid'),
    loader: document.getElementById('loader'),
    noResults: document.getElementById('no-results')
};

const state = {
    cheaters: []
};

async function fetchAndDisplayCheaters() {
    ui.setLoading(true);
    elements.noResults.style.display = 'none';

    try {
        const response = await api.getCheaters();
        if (response && response.cheaters) {
            state.cheaters = response.cheaters;
            if (state.cheaters.length > 0) {
                renderCheaters(state.cheaters);
            } else {
                elements.noResults.textContent = "No cheaters found yet.";
                elements.noResults.style.display = 'block';
            }
        } else {
            elements.noResults.textContent = "Failed to load cheaters. Please try again later.";
            elements.noResults.style.display = 'block';
        }
    } catch (error) {
        console.error("Error fetching cheaters:", error);
        elements.noResults.textContent = "An error occurred while fetching data.";
        elements.noResults.style.display = 'block';
    } finally {
        ui.setLoading(false);
    }
}

function renderCheaters(cheaters) {
    elements.cardGrid.innerHTML = '';
    cheaters.forEach(character => {
        const cardHtml = ui.renderCharacterCard(character);
        elements.cardGrid.insertAdjacentHTML('beforeend', cardHtml);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    fetchAndDisplayCheaters();
});