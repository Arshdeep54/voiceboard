const mic = document.querySelector('#mic');
const text = document.querySelector('#text');
const send = document.querySelector('#send');
const status = document.querySelector('#status');
const hint = document.querySelector('#hint');
const submit = document.querySelector('#submit');
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let rec, active = false, wanted = false, sessionText = '', restartTimer, finishStop;

function msg(message, kind = '') {
    status.textContent = message;
    status.className = 'status ' + kind;
}

function microphoneState(listening) {
    mic.classList.toggle('listening', listening);
    mic.setAttribute('aria-pressed', String(listening));
    mic.setAttribute('aria-label', listening ? 'Stop dictation' : 'Start dictation');
    hint.textContent = listening ? 'Tap to stop' : 'Tap to speak';
}

function startRecognition() {
    if (!wanted) return;
    try {
        rec.start();
    } catch {
        wanted = false;
        microphoneState(false);
        msg('Could not start the microphone. Try again.', 'error');
    }
}

function stopRecording() {
    wanted = false;
    clearTimeout(restartTimer);
    if (rec) microphoneState(false);
    if (!active) return Promise.resolve();
    mic.disabled = true;
    return new Promise(resolve => {
        finishStop = resolve;
        rec.stop();
    });
}

if (SR) {
    rec = new SR();
    // Chromium Android promotes partials to separate finals in continuous mode.
    rec.continuous = !/Android/i.test(navigator.userAgent);
    rec.interimResults = true;
    rec.lang = navigator.language || 'en-US';
    rec.onstart = () => {
        active = true;
        if (!wanted) { rec.stop(); return; }
        sessionText = text.value;
        microphoneState(true);
        msg('');
    };
    rec.onresult = event => {
        const phrases = [];
        for (let i = 0; i < event.results.length; i++) {
            const result = event.results[i];
            phrases.push(result[0].transcript.trim());
        }
        // Results include revised partials: replace this session rather than append each event.
        text.value = [sessionText, ...phrases].filter(Boolean).join(' ');
    };
    rec.onend = () => {
        active = false;
        mic.disabled = false;
        if (finishStop) { finishStop(); finishStop = null; }
        if (wanted) {
            restartTimer = setTimeout(startRecognition, 250);
        } else {
            microphoneState(false);
        }
    };
    rec.onerror = event => {
        if (event.error === 'no-speech') return;
        wanted = false;
        clearTimeout(restartTimer);
        microphoneState(false);
        msg('Speech recognition: ' + event.error, 'error');
    };
    mic.onclick = () => {
        if (wanted) {
            stopRecording();
        } else {
            wanted = true;
            startRecognition();
        }
    };
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) stopRecording();
    });
} else {
    mic.onclick = () => {
        text.focus();
        msg('Speech recognition unavailable — use keyboard dictation.', 'error');
    };
    hint.textContent = 'Use keyboard dictation';
}

send.onclick = async () => {
    send.disabled = true;
    try {
        // Wait for the last phrase before taking the text to send.
        await stopRecording();
        mic.disabled = true;
        if (!text.value.trim()) { msg('Add some text first.', 'error'); return; }
        msg('Sending…');
        const response = await fetch('/api/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token, text: text.value, submit: submit.checked })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Send failed');
        text.value = '';
        sessionText = '';
        msg('Sent', 'ok');
    } catch (error) {
        msg(error.message, 'error');
    } finally {
        send.disabled = false;
        mic.disabled = false;
    }
};
