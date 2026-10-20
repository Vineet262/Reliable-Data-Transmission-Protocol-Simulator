/**
 * learning.js
 * Interactive quiz reveal toggles and networking concept navigation.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Reveal quiz answers on click
    const quizButtons = document.querySelectorAll('.btn-reveal-answer');
    quizButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const answerId = btn.getAttribute('data-target');
            const answerEl = document.getElementById(answerId);
            if (!answerEl) return;

            if (answerEl.classList.contains('show')) {
                answerEl.classList.remove('show');
                btn.innerHTML = '<i class="bi bi-eye me-1"></i> Reveal Answer';
            } else {
                answerEl.classList.add('show');
                btn.innerHTML = '<i class="bi bi-eye-slash me-1"></i> Hide Answer';
            }
        });
    });

    // Quick filter for topics in learning center
    const searchInput = document.getElementById('conceptSearch');
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            const query = searchInput.value.toLowerCase().trim();
            const cards = document.querySelectorAll('.concept-card');
            cards.forEach(card => {
                const text = card.textContent.toLowerCase();
                card.closest('.concept-wrapper').style.display = text.includes(query) ? '' : 'none';
            });
        });
    }
});
