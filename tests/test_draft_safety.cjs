// Core draft and timeout behavior; no browser, layout checks, or dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup() {
    const elements = Object.fromEntries(['mic', 'text', 'send', 'status', 'hint', 'submit'].map(id => [id, {
        value: '', disabled: false, classList: {toggle() {}}, setAttribute() {}
    }]));
    const timers = new Map();
    let recognition, visibility, fetchImpl;
    class Recognition {
        constructor() { recognition = this; }
        start() { this.onstart(); }
        stop() { this.onend(); }
        abort() { this.onend(); }
    }
    const document = {querySelector: selector => elements[selector.slice(1)], addEventListener: (_, callback) => { visibility = callback; }};
    vm.runInNewContext(fs.readFileSync('voice_receiver/static/receiver.js', 'utf8'), {
        document,
        window: {SpeechRecognition: Recognition}, navigator: {language: 'en-US', userAgent: 'Android'}, token: 'test-token',
        AbortController,
        setTimeout: (callback, delay) => { const id = {}; timers.set(id, {callback, delay}); return id; },
        clearTimeout: id => timers.delete(id),
        fetch: (...args) => fetchImpl(...args)
    });
    return {
        elements, get recognition() { return recognition; },
        edit(value) { elements.text.value = value; elements.text.oninput?.(); },
        result(value) { recognition.onresult({results: [[{transcript: value}]]}); },
        hide() { document.hidden = true; visibility(); },
        fetch(callback) { fetchImpl = callback; },
        timeout(delay) {
            const entry = [...timers].find(([, timer]) => timer.delay === delay);
            assert.ok(entry, `A ${delay}ms timeout must be scheduled`);
            timers.delete(entry[0]);
            entry[1].callback();
        },
        timers
    };
}

async function flush() { for (let i = 0; i < 8; i++) await Promise.resolve(); }

const cases = {
    async 'manual edits survive late recognition results'() {
        const app = setup();
        app.elements.mic.onclick();
        app.result('old phrase');
        app.edit('My corrected phrase');
        app.result('old phrase corrected by the speech service');
        assert.equal(app.elements.text.value, 'My corrected phrase');
        app.elements.mic.onclick();
        app.result('new phrase');
        assert.equal(app.elements.text.value, 'My corrected phrase new phrase');
    },
    async 'a new draft survives a pending Send'() {
        const app = setup();
        let finish, payload;
        app.fetch((_, options) => {
            payload = JSON.parse(options.body);
            return new Promise(resolve => { finish = resolve; });
        });
        app.edit('First draft');
        const sending = app.elements.send.onclick();
        await flush();
        app.edit('Next draft');
        assert.equal(app.elements.mic.disabled, true, 'Keep dictation stopped until Send finishes');
        finish({ok: true, json: async () => ({ok: true})});
        await sending;
        assert.equal(payload.text, 'First draft');
        assert.equal(app.elements.text.value, 'Next draft');
        assert.equal(app.elements.send.disabled, false);
    },
    async 'editing back to the sent text still preserves the draft'() {
        const app = setup();
        let finish;
        app.fetch(() => new Promise(resolve => { finish = resolve; }));
        app.edit('Same words');
        const sending = app.elements.send.onclick();
        await flush();
        app.edit('Changed');
        app.edit('Same words');
        finish({ok: true, json: async () => ({ok: true})});
        await sending;
        assert.equal(app.elements.text.value, 'Same words');
    },
    async 'a missing recognition end preserves text and releases Send'() {
        const app = setup();
        let requests = 0;
        app.fetch(() => { requests++; });
        app.elements.mic.onclick();
        app.result('Keep this draft');
        app.recognition.stop = () => {};
        app.recognition.abort = () => {};
        const stalled = app.recognition;
        const sending = app.elements.send.onclick();
        app.hide(); // A second stop must not replace the Send waiter.
        app.timeout(3000);
        await sending;
        stalled.onresult({results: [[{transcript: 'Late result'}]]});
        assert.equal(app.elements.text.value, 'Keep this draft');
        assert.equal(requests, 0, 'Do not send if final recognition did not finish');
        assert.equal(app.elements.send.disabled, false);
        assert.equal(app.elements.mic.disabled, false);
        assert.match(app.elements.status.textContent, /microphone.*timed out/i);
        app.elements.mic.onclick();
        stalled.onend();
        stalled.onresult({results: [[{transcript: 'Old session result'}]]});
        app.result('New speech');
        assert.equal(app.elements.text.value, 'Keep this draft New speech', 'Recovery must ignore old recognizer events');
    },
    async 'the Stop button also recovers from missing end events'() {
        const app = setup();
        app.elements.mic.onclick();
        app.result('Keep my correction');
        app.recognition.stop = () => {};
        app.elements.mic.onclick();
        app.timeout(3000);
        await flush();
        assert.equal(app.elements.mic.disabled, false);
        assert.equal(app.elements.text.value, 'Keep my correction');
        assert.match(app.elements.status.textContent, /microphone.*timed out/i);
    },
    async 'a recognition stop exception releases controls'() {
        const app = setup();
        app.elements.mic.onclick();
        app.result('Keep this too');
        app.recognition.stop = () => { throw new Error('Speech service failed'); };
        await app.elements.send.onclick();
        assert.equal(app.elements.text.value, 'Keep this too');
        assert.equal(app.elements.mic.disabled, false);
        assert.equal(app.elements.send.disabled, false);
    },
    async 'a hanging request or response body times out without deleting text'() {
        for (const bodyHangs of [false, true]) {
            const app = setup();
            app.fetch((_, {signal}) => {
                const pending = new Promise((_, reject) => signal.addEventListener('abort', () => {
                    const error = new Error('Aborted'); error.name = 'AbortError'; reject(error);
                }));
                return bodyHangs ? Promise.resolve({ok: true, json: () => pending}) : pending;
            });
            app.edit('Maybe delivered');
            const sending = app.elements.send.onclick();
            await flush();
            app.timeout(15000);
            await sending;
            assert.equal(app.elements.text.value, 'Maybe delivered');
            assert.equal(app.elements.send.disabled, false);
            assert.equal(app.elements.mic.disabled, false);
            assert.match(app.elements.status.textContent, /check.*laptop.*retry/i);
            assert.equal(app.timers.size, 0);
        }
    }
};

(async () => {
    let failed = 0;
    for (const [name, check] of Object.entries(cases)) {
        try { await check(); console.log('PASS:', name); }
        catch (error) { failed++; console.error('FAIL:', name, error); }
    }
    process.exitCode = failed ? 1 : 0;
})();
