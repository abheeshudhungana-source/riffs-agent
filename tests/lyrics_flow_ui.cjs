// Exercise the application's actual handlers and lyric renderer with a tiny DOM
// double. This is a deterministic integration check, not visual browser QA.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { checkpoint, approved } = JSON.parse(fs.readFileSync(0, 'utf8'));
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const between = (start, end) => {
  const begin = html.indexOf(start);
  const finish = html.indexOf(end, begin);
  assert(begin >= 0 && finish > begin, `Missing application boundary: ${start}`);
  return html.slice(begin, finish);
};
const elements = new Map();
function $(id) {
  if (!elements.has(id)) {
    const classes = new Set(['hidden']);
    elements.set(id, {
      value: '', checked: false, disabled: false, innerHTML: '', textContent: '',
      listeners: {},
      addEventListener(event, listener) { this.listeners[event] = listener; },
      classList: {
        add: value => classes.add(value), remove: value => classes.delete(value),
        contains: value => classes.has(value),
        toggle(value, on) { if (on ?? !classes.has(value)) classes.add(value); else classes.delete(value); },
      },
    });
  }
  return elements.get(id);
}
const calls = [], playback = [], actions = [];
let responder = async url => ({ ok: true, json: async () => ({ data: url === '/api/generate' ? checkpoint : approved }) });
const context = vm.createContext({
  $, console, pendingVocalData: null, selectedGenres: [], MIN_BPM: 60, MAX_BPM: 200,
  state: { takes: [], lockedTracks: [], groove: 'straight', currentTake: 1 },
  document: { querySelectorAll: () => [] }, window: {},
  chordsInput: { value: 'Am - F - C - G' }, bpmInput: { value: '110' },
  keySelect: { value: 'Am' }, styleInput: { value: 'Warm soul' },
  modalError: $('modal-error'), btnConfirm: $('btn-confirm-synthesize'),
  validateChords: () => ({ ok: true }), activeInstruments: () => ['bass_guitar', 'rhythm_guitar', 'cymbals'],
  getAuthHeaders: async () => ({}),
  closeModal() {},
  startAudioPlayback(score, bpm) { playback.push({ score, bpm }); },
  async fetch(url, options) {
    calls.push({ url, body: JSON.parse(options.body) });
    return responder(url, options);
  },
  dispatch(action) {
    actions.push(action);
    if (action.type === 'GENERATE_FAIL') throw new Error(JSON.stringify(action.error));
    if (action.type === 'GENERATE_SUCCESS') {
      context.state.takes = [{ id: 1, payload: action.data }];
      context.renderLyrics(action.data);
    }
  },
});
vm.runInContext(between('    function renderLyrics(payload)', '    function render()'), context);
vm.runInContext(between('    function escapeLyrics(value)', '    function openModal()'), context);
vm.runInContext(between('    // Confirm & Synthesize (', '    // Groove Preset listeners'), context);
const click = id => $(id).listeners.click();

(async () => {
  $('select-lyrics-lang').value = 'en';
  $('select-vocal-style').value = 'soulful_lead';
  await click('btn-confirm-synthesize');
  assert.equal(calls[0].body.lyrics_prompt, 'Warm soul');
  assert.equal(calls.length, 1);
  assert.equal(playback.length, 0, 'No vocal/audio playback before review');
  assert.equal($('checkpoint-prompt').textContent, checkpoint.lyrics_prompt);
  assert($('checkpoint-context').textContent.includes(checkpoint.vocal_style.replaceAll('_', ' ')));
  for (const bar of checkpoint.lyrics_draft.bars) {
    assert($('checkpoint-lyrics-preview').innerHTML.includes(`BAR ${bar.bar}`));
    assert($('checkpoint-lyrics-preview').innerHTML.includes(bar.chord));
  }
  // Changing transient form inputs cannot change signed approval context.
  context.chordsInput.value = 'C - D - Em - F';
  context.styleInput.value = 'Changed form prompt';
  $('select-lyrics-lang').value = 'ja';
  $('select-vocal-style').value = 'rap_lead';
  $('checkpoint-ack').checked = true;
  await click('btn-approve-vocals');
  const approval = calls.at(-1);
  assert.equal(approval.url, '/api/vocals/approve');
  for (const field of ['prompt', 'lyrics_prompt', 'lyrics_language', 'vocal_style', 'key', 'bpm', 'groove', 'seed']) {
    assert.equal(approval.body[field], checkpoint[field], field);
  }
  assert.equal(approval.body.chords, checkpoint.chords.join(' - '));
  assert.deepEqual(approval.body.instruments, checkpoint.instruments);
  assert.equal(approval.body.token, checkpoint.vocal_confirmation_token);
  assert.deepEqual(approval.body.edited_lyrics, checkpoint.lyrics_draft.bars.map(bar => bar.text));
  assert.deepEqual(context.state.takes[0].payload.lyrics, approved.lyrics);
  assert(!$('view-lyrics').classList.contains('hidden'));
  for (const bar of approved.lyrics) {
    const rendered = $('lyrics-lines-container').innerHTML;
    assert(rendered.includes(`data-bar="${bar.bar}"`));
    assert(rendered.includes(context.escapeLyrics(bar.text)));
    assert(rendered.includes(context.escapeLyrics(bar.chord)));
  }

  // Cancellation publishes only the checkpoint's instrumental take.
  context.showVocalCheckpoint(checkpoint);
  const beforeCancel = calls.length;
  await click('btn-cancel-vocals');
  assert.equal(calls.length, beforeCancel);
  assert.equal(context.state.takes[0].payload.lyrics, null);
  assert.equal(context.state.takes[0].payload.score, checkpoint.score);
  assert(!context.state.takes[0].payload.stems.some(stem => stem.lane === 'vocal_lead'));

  // Edited text must be checked again and sent with its fresh token.
  context.showVocalCheckpoint(checkpoint);
  const edited = structuredClone(checkpoint);
  edited.lyrics_draft.bars[0].text = 'A fresh line for this verse';
  edited.vocal_confirmation_token = 'fresh-edited-token';
  $('checkpoint-lyrics-edit').value = edited.lyrics_draft.bars.map(bar => bar.text).join('\n');
  $('checkpoint-ack').checked = true;
  responder = async url => ({ ok: true, json: async () => ({ data: url === '/api/generate' ? edited :
    { ...approved, lyrics: edited.lyrics_draft.bars } }) });
  const beforeEdit = calls.length;
  await click('btn-approve-vocals');
  assert.equal(calls[beforeEdit].url, '/api/generate');
  assert.equal(calls[beforeEdit].body.vocal_approved, false);
  assert.equal(calls[beforeEdit + 1].url, '/api/vocals/approve');
  assert.equal(calls[beforeEdit + 1].body.token, 'fresh-edited-token');
  assert.equal(calls[beforeEdit + 1].body.edited_lyrics[0], edited.lyrics_draft.bars[0].text);

  context.showVocalCheckpoint(checkpoint);
  $('checkpoint-ack').checked = true;
  $('checkpoint-lyrics-edit').value = 'one line\n\nthird\nfourth';
  const beforeBlank = calls.length;
  await click('btn-approve-vocals');
  assert.equal(calls.length, beforeBlank, 'Do not silently remove blank lyric bars');
  assert($('modal-error').textContent.includes('nonempty'));

  context.renderLyrics({ ...approved, lyrics: [{ bar: 1, chord: 'Am', text: 'A < B & "C"' }] });
  assert($('lyrics-lines-container').innerHTML.includes('A &lt; B &amp; &quot;C&quot;'));
  console.log('lyrics flow passed: default, checkpoint context, approval/rendering, edits, cancellation');
})().catch(error => { console.error(error); process.exitCode = 1; });
