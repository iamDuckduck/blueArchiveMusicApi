let review;
let pending = { album: {}, tracks: {} };
let saving = false;
let polling = false;
const $ = (selector, root = document) => root.querySelector(selector);
const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[c]);
const statusLabels = {pending:"Not prepared", ready:"Ready", failed:"Needs attention", running:"Preparing", excluded:"Excluded", review:"Needs review", included:"Included", skipped:"Skipped"};

async function api(path, method = "GET", body) {
  const response = await fetch(path, {method, headers: body === undefined ? {} : {"Content-Type":"application/json"}, body: body === undefined ? undefined : JSON.stringify(body)});
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
  return result;
}

function notice(message, error = false) {
  const element = $("#notice");
  element.textContent = message;
  element.className = error ? "error" : "";
  element.hidden = false;
}

function dirty() {
  return Object.keys(pending.album).length > 0 || Object.values(pending.tracks).some(fields => Object.keys(fields).length > 0);
}

function updateSaveStatus() {
  $("#save").disabled = !dirty() || saving;
  $("#save").textContent = saving ? "Saving…" : "Save changes";
  $("#save-status").textContent = saving ? "Saving your review…" : dirty() ? "You have unsaved changes" : "All changes saved locally";
}

function field(trackId, name, label, value, type = "text") {
  const attributes = `data-track-id="${trackId}" data-track-field="${name}"`;
  const input = type === "textarea" ? `<textarea ${attributes} rows="3">${escapeHtml(value)}</textarea>` : `<input ${attributes} type="${type}" ${type === "number" ? 'min="1" max="999"' : 'maxlength="20000"'} value="${escapeHtml(value)}">`;
  return `<label>${label}${input}</label>`;
}

function creditEditor(trackId, name, title, help) {
  const addLabel = {group:"Add artist / group", composer:"Add composer", performers:"Add character / voice actor"}[name];
  return `<fieldset class="credit-editor${name === "performers" ? " wide" : ""}" data-credit-field="${name}" data-track-id="${trackId}">
    <legend${name === "performers" ? ' class="performer-label"' : ""}>${title}</legend>
    <p class="helper">${help}</p><div class="credit-rows"></div>
    <button type="button" class="button secondary" data-add-credit>${addLabel}</button>
  </fieldset>`;
}

function creditRow(name, entry) {
  const row = document.createElement("div");
  row.className = "credit-row" + (name === "performers" ? " participant-row" : "");
  const input = (part, label, value) => `<label>${label}<input data-credit-part="${part}" maxlength="20000" value="${escapeHtml(value)}"></label>`;
  row.innerHTML = name === "performers"
    ? input("character", "Character", entry.character) + input("voice_actor", "Voice actor (CV)", entry.voice_actor)
    : input("name", name === "composer" ? "Composer name" : "Artist / group name", entry);
  row.innerHTML += '<button type="button" class="button quiet" data-remove-credit>Remove</button>';
  return row;
}

function renderCredits(editor, entries) {
  const serialized = JSON.stringify(entries);
  if (editor.dataset.rendered === serialized) return;
  $(".credit-rows", editor).replaceChildren(...entries.map(entry => creditRow(editor.dataset.creditField, entry)));
  editor.dataset.rendered = serialized;
}

function captureCredits(editor) {
  const name = editor.dataset.creditField;
  const entries = [...editor.querySelectorAll(".credit-row")].map(row => name === "performers"
    ? {character: $('[data-credit-part="character"]', row).value, voice_actor: $('[data-credit-part="voice_actor"]', row).value}
    : $("input", row).value);
  (pending.tracks[editor.dataset.trackId] ||= {})[name] = entries;
  editor.dataset.rendered = JSON.stringify(entries);
  updateSaveStatus();
}

function createTrack(track) {
  const element = document.createElement("section");
  element.className = "panel track-panel" + (track.id === "drama" ? " reference-track" : "");
  element.id = `track-${track.id}`;
  const f = track.fields;
  const header = `<div class="track-header"><span class="track-number">${escapeHtml(f.position)}</span><div class="track-heading"><h3 class="track-title">${escapeHtml(f.title)}</h3><div class="track-meta"></div></div><span class="badge track-status"></span></div>`;
  if (track.id === "drama") {
    element.innerHTML = header + '<p class="helper">Spoken drama · kept here as a release reference. Excluded from music preparation.</p>';
    return element;
  }
  element.innerHTML = header + `
    <label class="inclusion"><input type="checkbox" data-inclusion="${track.id}"> Include this music track in preparation</label>
    <label class="inclusion"><input type="checkbox" data-publication="${track.id}"> Publish this reviewed track (after preparation)</label>
    <div class="track-fields">
      <div class="wide">${field(track.id, "title", "Track title", f.title)}</div>
      <div class="track-order wide">${field(track.id, "disc", "Disc", f.disc, "number")}${field(track.id, "position", "Track", f.position, "number")}
        <label>Music type<select data-track-id="${track.id}" data-track-field="kind"><option value="vocal">Vocal</option><option value="instrumental">Instrumental</option><option value="bgm">Background music</option><option value="unsure">Needs checking</option><option value="drama">Spoken drama</option></select></label>
      </div>
      ${creditEditor(track.id, "group", "Credited artists / groups", "The credited artist or unit, such as Veritas. A group is optional for a solo character song.")}
      ${creditEditor(track.id, "composer", "Composers", "Who composed the music. Add a separate entry for each composer.")}
      ${creditEditor(track.id, "performers", "Characters and voice actors", "The individual participants on this track. Each row keeps a character and their voice actor together; fill the names you know.")}
      <div class="wide">${field(track.id, "notes", "Your notes / manual corrections", f.notes, "textarea")}</div>
    </div>
    <div class="audio-area"></div><div class="track-warnings"></div>
    <details><summary>Compare source information</summary><div class="evidence-grid"><div><h4>Kivo description &amp; original fields</h4><a class="kivo-link text-link" target="_blank" rel="noopener noreferrer">Open source record ↗</a><pre class="kivo-evidence"></pre></div><div><h4>Embedded audio tags</h4><pre class="tag-evidence"></pre></div></div><p class="helper">Credits are suggestions. A source’s generic author field is not automatically a composer.</p></details>`;
  return element;
}

function setBadge(element, status, customLabel) {
  element.classList.remove("pending", "ready", "failed", "running", "excluded", "review", "included", "skipped");
  element.classList.add("badge", status);
  element.textContent = customLabel || statusLabels[status] || status;
}

function render(state) {
  review = state;
  const busy = state.job.running;
  const album = state.album;
  setBadge($("#album-status"), album.decision);
  $("#album-heading").textContent = album.fields.title;
  $("#release-link").href = state.release_reference;
  for (const input of document.querySelectorAll("[data-album-field]")) {
    if (!(input.dataset.albumField in pending.album)) input.value = album.fields[input.dataset.albumField] ?? "";
  }
  $("#fetch").disabled = busy;
  $("#fetch").textContent = state.tracks.some(t => t.source) ? "Reload Kivo details" : "Load Kivo details";
  $("#include").disabled = busy || album.decision === "included";
  $("#include").textContent = album.decision === "included" ? "Album included ✓" : "Include album";
  $("#skip").disabled = busy || album.decision === "skipped";
  $("#prepare").disabled = busy || album.decision !== "included";
  $("#prepare").textContent = busy && state.job.action === "prepare" ? "Preparing files…" : "Prepare / retry tracks";
  const cover = album.cover;
  const publication = state.publication || {status:"pending", message:"Not published.", enabled:false};
  $("#publish-message").textContent = publication.message;
  const selectedTracks = state.tracks.filter(t => t.included && t.publish_selected && t.source_id);
  $("#publish").disabled = busy || !publication.enabled || album.decision !== "included" || cover.status !== "ready" || !selectedTracks.length || selectedTracks.some(t => t.media.status !== "ready");
  $("#publish").textContent = busy && state.job.action === "publish" ? "Publishing…" : publication.status === "ready" ? "Publish again safely" : "Publish reviewed album";
  $("#job-message").textContent = state.job.message;
  $("#cover-status").textContent = cover.status === "ready" ? "Cover ready · original preserved · 400 px and 800 px copies saved" : cover.error ? "Cover: " + cover.error : "Cover: " + (statusLabels[cover.status] || cover.status);
  if (cover.status === "ready") {
    const coverKey = cover.files["400"].sha256;
    if ($("#cover-art").dataset.key !== coverKey) {
      const image = document.createElement("img");
      image.src = cover.preview_url + "?v=" + coverKey;
      image.alt = "Veritas album cover";
      $("#cover-art").replaceChildren(image);
      $("#cover-art").dataset.key = coverKey;
    }
  }
  $("#tracks .loading")?.remove();
  for (const track of state.tracks) {
    let card = $(`#track-${track.id}`);
    if (!card) { card = createTrack(track); $("#tracks").append(card); }
    $(".track-title", card).textContent = track.fields.title;
    $(".track-number", card).textContent = track.fields.position ?? "—";
    setBadge($(".track-status", card), track.media.status);
    const duration = track.media.duration;
    $(".track-meta", card).textContent = track.source_id ? `Kivo #${track.source_id}${duration ? " · " + Math.floor(duration / 60) + ":" + String(Math.floor(duration % 60)).padStart(2, "0") + " · " + track.media.codec : ""}` : "Release listing · original position 3";
    if (track.id === "drama") continue;
    for (const input of card.querySelectorAll("[data-track-field]")) {
      if (!(input.dataset.trackField in (pending.tracks[track.id] || {}))) input.value = track.fields[input.dataset.trackField] ?? "";
    }
    for (const editor of card.querySelectorAll("[data-credit-field]")) {
      if (!(editor.dataset.creditField in (pending.tracks[track.id] || {}))) renderCredits(editor, track.fields[editor.dataset.creditField]);
    }
    $(".performer-label", card).textContent = track.fields.kind === "instrumental" ? "Associated characters / voice actors (no vocal performance)" : "Characters and voice actors";
    const checkbox = $("[data-inclusion]", card);
    checkbox.checked = track.included;
    checkbox.disabled = busy;
    const publicationCheckbox = $("[data-publication]", card);
    publicationCheckbox.checked = track.publish_selected;
    publicationCheckbox.disabled = busy || (!track.publish_selected && (!track.included || track.media.status !== "ready"));
    const audioArea = $(".audio-area", card);
    if (track.media.status === "ready") {
      const url = track.media.preview_url + "?v=" + track.media.sha256;
      if ($("audio", audioArea)?.getAttribute("src") !== url) {
        const audio = document.createElement("audio");
        audio.controls = true;
        audio.preload = "metadata";
        audio.src = url;
        audio.setAttribute("aria-label", "Preview " + track.fields.title);
        audioArea.replaceChildren(audio);
      }
    } else {
      const hint = document.createElement("div");
      hint.className = "audio-hint";
      hint.textContent = track.media.status === "running" ? "Downloading and validating audio…" : "Audio preview becomes available after local preparation.";
      audioArea.replaceChildren(hint);
    }
    const warnings = [];
    if (track.source_error) warnings.push("Kivo: " + track.source_error + (track.source ? " Saved source information is retained." : ""));
    if (track.media.error) warnings.push("Preparation: " + track.media.error);
    if (!track.fields.composer.length) warnings.push("Composer not filled yet. File tags may help after preparation, or you can add it manually.");
    if (track.fields.kind === "drama" && track.included) warnings.push("Marked as spoken drama. Uncheck this track to exclude it from preparation.");
    const container = $(".track-warnings", card);
    container.replaceChildren(...warnings.map(message => { const p = document.createElement("p"); p.className = "warning-text"; p.textContent = message; return p; }));
    $(".kivo-link", card).href = `https://api.kivo.wiki/api/v1/musics/${track.source_id}`;
    $(".kivo-evidence", card).textContent = track.source ? JSON.stringify(track.source, null, 2) : "Load source information to see the original record.";
    $(".tag-evidence", card).textContent = Object.keys(track.tags).length ? JSON.stringify(track.tags, null, 2) : "Audio tags are read after the file is downloaded and validated.";
  }
  const g = state.gamekee;
  setBadge($("#gamekee-status"), g.status, {pending:"Not checked", ready:"Available", failed:"Manual reference available"}[g.status]);
  $("#gamekee-message").textContent = g.status === "failed" ? "The automatic check could not read this page. You can open it and enter the details manually. " + g.error : g.status === "ready" ? "Source text is saved below. Compare it with the track credits before making corrections." : "The matching album is checked when you load sources.";
  $("#gamekee-link").href = g.url;
  $("#retry-gamekee").disabled = busy;
  $("#gamekee-evidence").hidden = !(g.text || g.cached_text);
  $("#gamekee-text").textContent = g.text || (g.cached_text ? "Previously saved content (latest fetch failed):\n\n" + g.cached_text : "");
  updateSaveStatus();
}

async function saveEdits() {
  if (!dirty()) return;
  if (saving) throw new Error("Your changes are still saving. Please try again in a moment.");
  const sent = structuredClone(pending);
  saving = true;
  updateSaveStatus();
  try {
    const state = await api("/api/review", "PUT", sent);
    for (const [key, value] of Object.entries(sent.album)) if (pending.album[key] === value) delete pending.album[key];
    for (const [id, fields] of Object.entries(sent.tracks)) for (const [key, value] of Object.entries(fields)) if (JSON.stringify(pending.tracks[id]?.[key]) === JSON.stringify(value)) delete pending.tracks[id][key];
    render(state);
  } finally { saving = false; updateSaveStatus(); }
}

async function act(path, body = {}) {
  try { await saveEdits(); render(await api(path, "POST", body)); $("#notice").hidden = true; }
  catch (error) { notice(error.message, true); }
}

$("#review-form").addEventListener("input", event => {
  const input = event.target;
  if (input.dataset.creditPart) captureCredits(input.closest("[data-credit-field]"));
  if (input.dataset.albumField) pending.album[input.dataset.albumField] = input.value;
  if (input.dataset.trackField) {
    const fields = pending.tracks[input.dataset.trackId] ||= {};
    fields[input.dataset.trackField] = input.type === "number" ? (input.value === "" ? null : Number(input.value)) : input.value;
  }
  updateSaveStatus();
});
$("#review-form").addEventListener("click", event => {
  const button = event.target.closest("[data-add-credit], [data-remove-credit]");
  if (!button) return;
  const editor = button.closest("[data-credit-field]");
  if (button.hasAttribute("data-add-credit")) {
    const row = creditRow(editor.dataset.creditField, editor.dataset.creditField === "performers" ? {character:"", voice_actor:""} : "");
    $(".credit-rows", editor).append(row);
    $("input", row).focus();
  } else {
    button.closest(".credit-row").remove();
    $("[data-add-credit]", editor).focus();
  }
  captureCredits(editor);
});
$("#review-form").addEventListener("change", event => {
  if (event.target.dataset.inclusion) act(`/api/tracks/${event.target.dataset.inclusion}/inclusion`, {included:event.target.checked});
  if (event.target.dataset.publication) act(`/api/tracks/${event.target.dataset.publication}/publication`, {selected:event.target.checked});
});
$("#review-form").addEventListener("submit", async event => {
  event.preventDefault();
  try { await saveEdits(); notice("Your review is saved on this computer."); }
  catch (error) { notice(error.message, true); }
});
$("#fetch").addEventListener("click", () => act("/api/jobs/fetch"));
$("#prepare").addEventListener("click", () => act("/api/jobs/prepare"));
$("#publish").addEventListener("click", () => act("/api/jobs/publish"));
$("#retry-gamekee").addEventListener("click", () => act("/api/jobs/gamekee"));
$("#include").addEventListener("click", () => act("/api/decision", {decision:"included"}));
$("#skip").addEventListener("click", () => act("/api/decision", {decision:"skipped"}));
window.addEventListener("beforeunload", event => { if (dirty()) { event.preventDefault(); event.returnValue = ""; } });

async function refresh() {
  if (polling) return;
  polling = true;
  try { render(await api("/api/review")); }
  catch (error) { notice("Cannot reach the local tool. Keep this page open if you have unsaved edits, and restart the Python app. " + error.message, true); }
  finally { polling = false; }
}
refresh();
setInterval(refresh, 1600);
