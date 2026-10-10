const mic = document.querySelector('#mic');
const text = document.querySelector('#text');
const send = document.querySelector('#send');
const status = document.querySelector('#status');
const hint = document.querySelector('#hint');
const submit = document.querySelector('#submit');
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let rec, active = false, wanted = false, sessionText = '', restartTimer, finishStop, stopPromise;
let acceptResults = false, editVersion = 0;

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
        createRecognition();
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
    if (finishStop) return stopPromise;
    if (!active) return Promise.resolve();
    mic.disabled = true;
    const pending = new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
            const stalled = rec;
            rec = null; // Ignore late events; the next attempt gets a fresh recognizer.
            finishStop(new Error('Microphone stop timed out. Your text is safe; try again.'));
            try { stalled.abort(); } catch {}
        }, 3000);
        finishStop = error => {
            clearTimeout(timer);
            finishStop = null;
            active = false;
            mic.disabled = send.disabled;
            if (error) reject(error); else resolve();
        };
        try { rec.stop(); }
        catch (error) { finishStop(error); }
    });
    const stopping = pending.finally(() => {
        if (stopPromise === stopping) stopPromise = null;
    });
    stopPromise = stopping;
    return stopping;
}

function createRecognition() {
    const current = rec = new SR();
    // Chromium Android promotes partials to separate finals in continuous mode.
    rec.continuous = !/Android/i.test(navigator.userAgent);
    rec.interimResults = true;
    rec.lang = navigator.language || 'en-US';
    rec.onstart = () => {
        if (rec !== current) return;
        active = true;
        if (!wanted) { rec.stop(); return; }
        acceptResults = true;
        sessionText = text.value;
        microphoneState(true);
        msg('');
    };
    rec.onresult = event => {
        if (rec !== current || !active || !acceptResults) return;
        const phrases = [];
        for (let i = 0; i < event.results.length; i++) {
            const result = event.results[i];
            phrases.push(result[0].transcript.trim());
        }
        // Results include revised partials: replace this session rather than append each event.
        text.value = [sessionText, ...phrases].filter(Boolean).join(' ');
    };
    rec.onend = () => {
        if (rec !== current) return;
        active = false;
        mic.disabled = send.disabled;
        if (finishStop) finishStop();
        if (wanted) {
            restartTimer = setTimeout(startRecognition, 250);
        } else {
            microphoneState(false);
        }
    };
    rec.onerror = event => {
        if (rec !== current) return;
        if (event.error === 'no-speech') return;
        wanted = false;
        clearTimeout(restartTimer);
        microphoneState(false);
        msg('Speech recognition: ' + event.error, 'error');
    };
}

text.oninput = () => {
    editVersion++;
    acceptResults = false;
    if (active || wanted) stopRecording().catch(error => msg(error.message, 'error'));
};

if (SR) {
    mic.onclick = () => {
        if (wanted) {
            stopRecording().catch(error => msg(error.message, 'error'));
        } else {
            wanted = true;
            startRecognition();
        }
    };
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) stopRecording().catch(error => msg(error.message, 'error'));
    });
} else {
    mic.onclick = () => {
        text.focus();
        msg('Speech recognition unavailable — use keyboard dictation.', 'error');
    };
    hint.textContent = 'Use keyboard dictation';
}

send.onclick = async () => {
    if (send.disabled) return;
    send.disabled = true;
    let requestTimer;
    try {
        // Wait for the last phrase before taking the text to send.
        await stopRecording();
        mic.disabled = true;
        if (!text.value.trim()) { msg('Add some text first.', 'error'); return; }
        const sentText = text.value, sentVersion = editVersion;
        const controller = new AbortController();
        requestTimer = setTimeout(() => controller.abort(), 15000);
        msg('Sending…');
        const response = await fetch('/api/send', {
            method: 'POST',
            signal: controller.signal,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token, text: sentText, submit: submit.checked })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Send failed');
        if (editVersion === sentVersion && text.value === sentText) {
            text.value = '';
            sessionText = '';
        }
        msg('Sent', 'ok');
    } catch (error) {
        msg(error.name === 'AbortError' ? 'Send timed out. Your text is safe; check your laptop before retrying.' : error.message, 'error');
    } finally {
        clearTimeout(requestTimer);
        send.disabled = false;
        mic.disabled = false;
    }
};
