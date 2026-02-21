/**
 * LLM chat interface.
 * Stuurt berichten naar /api/llm/chat en toont responses + acties.
 */

function initChat() {
    // Chat is al functioneel via inline handlers in HTML
}

async function sendChat() {
    const input = document.getElementById('chat-text');
    const message = input.value.trim();
    if (!message) return;

    input.value = '';
    addChatMessage(message, 'user');

    try {
        const resp = await fetch('/api/llm/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message }),
        });
        const data = await resp.json();

        if (data.response) {
            addChatMessage(data.response, 'assistant');
        }

        if (data.actions && data.actions.length > 0) {
            for (const action of data.actions) {
                const msg = `[${action.tool}] ${action.result?.message || 'uitgevoerd'}`;
                addChatMessage(msg, 'action');
            }
        }
    } catch (e) {
        addChatMessage('Fout: kon niet verbinden met server', 'assistant');
    }
}

function addChatMessage(text, role) {
    const container = document.getElementById('chat-messages');
    if (!container) return;

    const div = document.createElement('div');
    div.className = `chat-msg ${role}`;
    div.textContent = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}
