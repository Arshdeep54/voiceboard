// Core dictation behavior; no browser, layout checks, or dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const android = process.argv[2] === 'android';

const elements = Object.fromEntries(['mic', 'text', 'send', 'status', 'hint', 'submit'].map(id => [id, {
    value: '', classList: {toggle() {}}, setAttribute() {}
}]));
let recognition, restart, payload;
class Recognition {
    constructor() { recognition = this; }
    start() { this.onstart(); }
    stop() {
        if (this.lastPhrase) this.onresult({results: [result(this.lastPhrase, true)]});
        this.onend();
    }
}
function result(transcript, isFinal = false) {
    return Object.assign([{transcript}], {isFinal});
}
vm.runInNewContext(fs.readFileSync('voice_receiver/static/receiver.js', 'utf8'), {
    document: {querySelector: selector => elements[selector.slice(1)], addEventListener() {}},
    window: {SpeechRecognition: Recognition}, navigator: {language: 'en-US', userAgent: android ? 'Mozilla/5.0 (Linux; Android 15) Chrome/140' : 'Mozilla/5.0 (X11; Linux x86_64) Chrome/140'}, token: 'test-token',
    AbortController,
    setTimeout: callback => { restart = callback; return 1; }, clearTimeout: () => { restart = null; },
    fetch: async (_, options) => { payload = JSON.parse(options.body); return {ok: true, json: async () => ({ok: true})}; }
});

(async () => {
    if (android) {
        elements.mic.onclick();
        const results = [];
        for (const transcript of ['hi', 'hi that is', 'hi that is live', 'hi that is live writing']) {
            // Chromium Android promotes partials to separate finals in continuous mode.
            if (recognition.continuous) results.push(result(transcript, true));
            else results.splice(0, results.length, result(transcript));
            recognition.onresult({results});
        }
        assert.equal(elements.text.value, 'hi that is live writing', 'Android partial snapshots must not accumulate');
        elements.mic.onclick();
    }
    elements.text.value = 'Existing text.';
    elements.mic.onclick();
    recognition.onresult({results: [result('hello')]});
    assert.equal(elements.text.value, 'Existing text. hello', 'Partial speech must appear before a final result');
    assert.equal(recognition.continuous, !android);
    assert.equal(recognition.interimResults, true);
    recognition.onresult({results: [result('hello world')]});
    assert.equal(elements.text.value, 'Existing text. hello world', 'Revised partial text must replace, not append');
    recognition.onresult({results: [result('Hello world.', true), result('next')]});
    recognition.onresult({results: [result('Hello world.', true), result('next thought')]});
    assert.equal(elements.text.value, 'Existing text. Hello world. next thought');
    recognition.onresult({results: [result('Hello world.', true)]});
    assert.equal(elements.text.value, 'Existing text. Hello world.', 'Withdrawn partials must disappear');
    recognition.onend();
    restart();
    recognition.onresult({results: [result('Hello world.', true)]});
    assert.equal(elements.text.value, 'Existing text. Hello world. Hello world.', 'Intentional repeated speech must survive a restart');
    recognition.onend();
    restart();
    recognition.onresult({results: [result('Final wor')]});
    recognition.lastPhrase = 'Final words.';
    await elements.send.onclick();
    assert.equal(payload.text, 'Existing text. Hello world. Hello world. Final words.', 'Send must wait for the final corrected result');
    assert.equal(elements.text.value, '');
    assert.equal(restart, null, 'Send must cancel automatic restart');
    console.log(`PASS (${android ? 'Android' : 'desktop'}): live partials, corrections, cumulative results, restarts, repeated speech, and final text on Send.`);
    if (!android) execFileSync(process.execPath, [__filename, 'android'], {stdio: 'inherit'});
})().catch(error => { console.error(error); process.exitCode = 1; });
