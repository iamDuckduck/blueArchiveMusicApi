let review;
let pending = { album: {}, tracks: {} };
let saving = false;
let polling = false;
let showMatchingFields = false;
let publicationConfirmation = null;
const $ = (selector, root = document) => root.querySelector(selector);
const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[c]);
const statusLabels = {pending:"Not prepared", ready:"Ready", failed:"Needs attention", running:"Preparing", excluded:"Excluded", review:"Needs review", included:"Included", skipped:"Skipped"};
const reviewPrefix = document.body.dataset.reviewPrefix || "";

async function api(path, method = "GET", body) {
  const response = await fetch(reviewPrefix + path, {method, headers: body === undefined ? {} : {"Content-Type":"application/json"}, body: body === undefined ? undefined : JSON.stringify(body)});
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
  const input = type === "textarea" ? `<textarea ${attributes} rows="3">${escapeHtml(value)}</textarea>` : `<input ${attributes} type="${type}" ${type === "number" ? `min="1" max="${name === "display_order" ? 999999 : 999}"` : 'maxlength="20000"'} value="${escapeHtml(value)}">`;
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
      <div class="track-order wide">${field(track.id, "display_order", "Display order", f.display_order, "number")}${field(track.id, "disc", "Official disc (if known)", f.disc, "number")}${field(track.id, "position", "Official track (if known)", f.position, "number")}
        <label>Music type<select data-track-id="${track.id}" data-track-field="kind"><option value="vocal">Vocal</option><option value="instrumental">Instrumental</option><option value="bgm">Background music</option><option value="unsure">Needs checking</option><option value="drama">Spoken drama</option></select></label>
      </div>
      <p class="helper wide">Display order controls the album's app sequence. Match the known release order; leave unknown official disc/track numbers blank.</p>
      ${creditEditor(track.id, "group", "Credited artists / groups", "The credited artist or unit, such as Veritas. A group is optional for a solo character song.")}
      ${creditEditor(track.id, "composer", "Composers", "Who composed the music. Add a separate entry for each composer.")}
      ${creditEditor(track.id, "performers", "Characters and voice actors", "The individual participants on this track. Each row keeps a character and their voice actor together; fill the names you know.")}
      <div class="wide">${field(track.id, "notes", "Your notes / manual corrections", f.notes, "textarea")}</div>
    </div>
    <div class="audio-area"></div><div class="track-warnings"></div><div class="source-proposals"></div>
    <details><summary>Compare source information</summary><div class="evidence-grid"><div><h4>Kivo description &amp; original fields</h4><a class="kivo-link text-link" target="_blank" rel="noopener noreferrer">Open source record ↗</a><pre class="kivo-evidence"></pre></div><div><h4>Embedded audio tags</h4><pre class="tag-evidence"></pre></div></div><p class="helper">Credits are suggestions. A source’s generic author field is not automatically a composer.</p></details>`;
  return element;
}

function setBadge(element, status, customLabel) {
  element.classList.remove("pending", "ready", "failed", "running", "excluded", "review", "included", "skipped");
  element.classList.add("badge", status);
  element.textContent = customLabel || statusLabels[status] || status;
}

function renderPublished(state) {
  const publication = state.publication;
  $("#check-published").disabled = state.job.running || !publication.enabled;
  $("#publish-destination").textContent = publication.enabled ? `Destination: ${publication.destination}` : "Publication is not configured.";
  const destination = publication.destinations?.[publication.destination];
  const observed = destination?.observed || {};
  const conflict = destination?.conflict;
  $("#published-panel").classList.toggle("has-conflict", !!conflict);
  $("#published-heading").textContent = conflict ? `Publishing paused: this ${conflict === "album" ? "album" : "track"} changed` : "Compare with published content";
  $("#published-explanation").textContent = conflict
    ? "The published version changed since your last review. This record was not overwritten. Compare the differences below; your draft is safe."
    : "Check the published version before your next upload. Checking or reviewing a version does not publish anything.";
  const attempt = publication.attempt;
  const progress = $("#publication-progress");
  progress.hidden = !attempt || attempt.destination !== publication.destination;
  $("#progress-explanation").hidden = progress.hidden;
  if (!progress.hidden) {
    const statusNames = {not_sent:"Not sent", sending:"Sending", saved:"Saved", unchanged:"Already matches", conflict:"Conflict", failed:"Unconfirmed · check / retry"};
    progress.innerHTML = attempt.records.map(item => {
      const status = item.status === "sending" && !(state.job.running && state.job.action === "publish") ? "failed" : item.status;
      return `<li class="progress-${status}"><span>${escapeHtml(item.record === "album" ? "Album" : state.tracks.find(t => t.id === item.record)?.fields.title || `Track ${item.record}`)}</span><strong>${escapeHtml(statusNames[status])}</strong></li>`;
    }).join("");
  }
  const container = $("#published-comparison");
  const comparison = Object.entries(observed).map(([record, current]) => {
    const local = record === "album" ? state.album : state.tracks.find(t => t.id === record);
    return {record, current, title:local.fields.title, fields:local.fields, media:record === "album" ? local.cover.files : local.media,
      rows:publicationRows(record, state, current), accepted:Object.hasOwn(destination.receipts, record) && destination.receipts[record].revision === current.revision};
  });
  const serialized = JSON.stringify({comparison, conflict, showMatchingFields, publicationConfirmation});
  if (container.dataset.rendered !== serialized) {
    const openTechnical = new Set([...container.querySelectorAll("details[open]")].map(item => item.dataset.technical));
    container.replaceChildren(...comparison.map(({record, current, title, fields, media, rows, accepted}) => {
      const card = document.createElement("article");
      card.className = "published-record";
      const differences = rows.filter(row => !row.same);
      const unknown = differences.filter(row => row.unknown).length;
      const changed = differences.length - unknown;
      const summary = `${changed} ${changed === 1 ? "difference" : "differences"}${unknown ? ` · ${unknown} media ${unknown === 1 ? "check" : "checks"} needed` : ""}`;
      const visibleRows = showMatchingFields ? rows : differences;
      const confirming = publicationConfirmation?.record === record && publicationConfirmation.revision === current.revision;
      card.innerHTML = `<div class="comparison-record-heading"><h3>${record === "album" ? "Album" : "Track"}: ${escapeHtml(title)}</h3><span class="badge ${accepted ? "ready" : record === conflict ? "warning" : ""}">${accepted ? "Version reviewed" : current.exists ? summary : "Not published here"}</span></div>
        ${visibleRows.length ? `<table class="comparison-table"><caption class="sr-only">Published values compared with your saved draft</caption><thead><tr><th scope="col">Field</th><th scope="col">Published value</th><th scope="col">Your saved draft</th></tr></thead><tbody>${visibleRows.map(row => `<tr class="${row.same ? "matching-row" : "changed-row"}"><th scope="row">${escapeHtml(row.label)}</th><td>${escapeHtml(row.published)}</td><td>${escapeHtml(row.draft)}</td></tr>`).join("")}</tbody></table>` : '<p class="helper">No differences in the compared fields. Technical details are available below.</p>'}
        <div class="comparison-actions"><button class="button primary" type="button" data-edit-draft="${escapeHtml(record)}">Edit my draft</button><button class="button secondary" type="button" data-review-version="${escapeHtml(record)}" ${accepted ? "disabled" : ""}>${accepted ? "Version reviewed" : "Keep my values for next publish"}</button></div>
        <p class="helper">${accepted ? "Nothing was published by reviewing this version. Re-select prepared tracks and publish separately when ready." : "Edit your draft to preserve published corrections, or deliberately keep your own values. Neither action publishes."}</p>
        ${confirming ? `<div class="version-confirmation" role="group" aria-label="Confirm reviewed version"><strong>Use this published version as your new starting point?</strong><p>Your draft stays unchanged. A later publish can replace the published values above. ${record === "album" ? "All track selections will be cleared" : "This track will be deselected"} so you can review before publishing.</p><button class="button secondary" type="button" data-confirm-version="${escapeHtml(record)}">Confirm reviewed version</button><button class="button quiet" type="button" data-cancel-version>Cancel</button></div>` : ""}
        <details data-technical="${escapeHtml(record)}" ${openTechnical.has(record) ? "open" : ""}><summary>Technical details</summary><div class="evidence-grid"><div><h4>Published snapshot</h4><pre>${escapeHtml(JSON.stringify(current, null, 2))}</pre></div><div><h4>Local fields and media</h4><pre>${escapeHtml(JSON.stringify({fields, media}, null, 2))}</pre></div></div></details>`;
      return card;
    }));
    if (!comparison.length) container.innerHTML = '<p class="comparison-empty">No published snapshot checked yet. Use “Check published state” to compare without uploading.</p>';
    container.dataset.rendered = serialized;
  }
  for (const button of container.querySelectorAll("button")) {
    const record = button.dataset.reviewVersion;
    button.disabled = state.job.running || !!(record && Object.hasOwn(destination.receipts, record) && destination.receipts[record].revision === observed[record].revision);
  }
}

function renderSuggestions(card, track, busy) {
  const pending = track.pending_suggestions || {};
  const container = $(".source-proposals", card);
  const serialized = JSON.stringify({pending, fields:track.fields});
  if (container.dataset.rendered !== serialized) {
    container.replaceChildren();
    if (Object.keys(pending).length) {
      const heading = document.createElement("h4");
      heading.textContent = "Incoming source changes — your reviewed values are unchanged";
      container.append(heading);
      for (const [source, fields] of Object.entries(pending)) for (const [field, value] of Object.entries(fields)) {
        const row = document.createElement("div");
        row.innerHTML = `<p>${escapeHtml(source)} · ${escapeHtml(field)}</p><div class="evidence-grid">
          <div><h4>Reviewed</h4><pre>${escapeHtml(JSON.stringify(track.fields[field], null, 2))}</pre></div>
          <div><h4>Incoming</h4><pre>${escapeHtml(JSON.stringify(value, null, 2))}</pre></div></div>
          <button type="button" class="button secondary" data-suggestion-choice="use" data-source="${escapeHtml(source)}" data-field="${escapeHtml(field)}" data-track-id="${track.id}">Use suggestion</button>
          <button type="button" class="button quiet" data-suggestion-choice="keep" data-source="${escapeHtml(source)}" data-field="${escapeHtml(field)}" data-track-id="${track.id}">Keep reviewed value</button>`;
        container.append(row);
      }
      const keep = document.createElement("button");
      keep.type = "button";
      keep.className = "button secondary";
      keep.dataset.suggestionChoice = "keep";
      keep.dataset.trackId = track.id;
      keep.textContent = "Keep all reviewed values for this track";
      container.append(keep);
    }
    container.dataset.rendered = serialized;
  }
  for (const button of container.querySelectorAll("button")) button.disabled = busy;
}

function render(state) {
  review = state;
  const busy = state.job.running;
  const album = state.album;
  setBadge($("#album-status"), album.decision);
  $("#album-heading").textContent = album.fields.title;
  $(".album-summary").textContent = `${state.tracks.length} known source / reference tracks`;
  $("#release-link").href = state.release_reference;
  $("#release-link").hidden = !state.release_reference;
  $("#release-note").hidden = !state.release_reference;
  for (const input of document.querySelectorAll("[data-album-field]")) {
    if (!(input.dataset.albumField in pending.album)) input.value = album.fields[input.dataset.albumField] ?? "";
  }
  $("#fetch").disabled = busy;
  $("#fetch").textContent = state.tracks.some(t => t.source) ? "Reload Kivo details" : "Load Kivo details";
  $("#include").disabled = busy || album.decision === "included";
  $("#include").textContent = album.decision === "included" ? "Album included ✓" : "Include album";
  $("#skip").disabled = busy || album.decision === "skipped";
  $("#prepare").disabled = busy || album.decision !== "included";
  $("#refresh-media").disabled = busy || album.decision !== "included";
  $("#prepare").textContent = busy && state.job.action === "prepare" ? "Preparing files…" : "Prepare / retry tracks";
  const cover = album.cover;
  const publication = state.publication || {status:"pending", message:"Not published.", enabled:false};
  renderPublished(state);
  $("#publish-message").textContent = publication.message;
  const selectedTracks = state.tracks.filter(t => t.included && t.publish_selected && t.source_id);
  $("#publish").disabled = busy || !publication.enabled || album.decision !== "included" || cover.status !== "ready" || !selectedTracks.length || selectedTracks.some(t => t.media.status !== "ready");
  $("#publish").textContent = busy && state.job.action === "publish" ? "Publishing…" : publication.status === "ready" ? "Publish again safely" : "Publish reviewed album";
  $("#job-message").textContent = state.job.message;
  $("#cover-status").textContent = cover.error ? "Cover: " + cover.error + (cover.status === "ready" ? " Previous validated cover retained." : "") : cover.status === "ready" ? "Cover ready · original preserved · 400 px and 800 px copies saved" : "Cover: " + (statusLabels[cover.status] || cover.status);
  if (cover.status === "ready") {
    const coverKey = cover.files["400"].sha256;
    if ($("#cover-art").dataset.key !== coverKey) {
      const image = document.createElement("img");
      image.src = cover.preview_url + "?v=" + coverKey;
      image.alt = album.fields.title;
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
    renderSuggestions(card, track, busy);
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
    if (track.index_warning) warnings.push(track.index_warning);
    if (track.missing_index) warnings.push("Not in the latest source index. Saved track, files and publication are retained.");
    if (track.fields.position == null) warnings.push("Official track number is unknown; the app will use display order without inventing a track number.");
    if (track.source_error) warnings.push("Kivo: " + track.source_error + (track.source ? " Saved source information is retained." : ""));
    if (track.media.error) warnings.push("Preparation: " + track.media.error);
    if (!track.fields.composer.length) warnings.push("Composer not filled yet. File tags may help after preparation, or you can add it manually.");
    if (track.fields.kind === "drama" && track.included) warnings.push("Marked as spoken drama. Uncheck this track to exclude it from preparation.");
    const container = $(".track-warnings", card);
    container.replaceChildren(...warnings.map(message => { const p = document.createElement("p"); p.className = "warning-text"; p.textContent = message; return p; }));
    $(".kivo-link", card).href = `https://api.kivo.wiki/api/v1/musics/${track.source_id}`;
    $(".kivo-evidence", card).textContent = JSON.stringify({detail:track.source, index:track.index, incomingIndex:track.pending_index}, null, 2);
    $(".tag-evidence", card).textContent = Object.keys(track.tags).length ? JSON.stringify(track.tags, null, 2) : "Audio tags are read after the file is downloaded and validated.";
  }
  const g = state.gamekee;
  setBadge($("#gamekee-status"), g.status, {pending:"Not checked", ready:"Available", failed:"Manual reference available"}[g.status]);
  $("#gamekee-message").textContent = g.status === "failed" ? "The automatic check could not read this page. You can open it and enter the details manually. " + g.error : g.status === "ready" ? "Source text is saved below. Compare it with the track credits before making corrections." : "The matching album is checked when you load sources.";
  $("#gamekee-link").href = g.url;
  $("#gamekee-link").hidden = !g.url;
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
  const suggestion = event.target.closest("[data-suggestion-choice]");
  if (suggestion) {
    const track = review.tracks.find(t => t.id === suggestion.dataset.trackId);
    const {source, field, suggestionChoice} = suggestion.dataset;
    const proposals = source ? {[source]:{[field]:track.pending_suggestions[source][field]}} : track.pending_suggestions;
    act(`/api/tracks/${track.id}/suggestions`, {proposals, choice:suggestionChoice});
    return;
  }
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
$("#refresh-media").addEventListener("click", () => act("/api/jobs/refresh"));
$("#publish").addEventListener("click", () => act("/api/jobs/publish"));
$("#check-published").addEventListener("click", () => act("/api/jobs/published"));
$("#show-matching").addEventListener("change", event => {
  showMatchingFields = event.target.checked;
  renderPublished(review);
});
$("#published-comparison").addEventListener("click", async event => {
  const button = event.target.closest("button");
  if (!button) return;
  if (button.hasAttribute("data-edit-draft")) {
    const record = button.dataset.editDraft;
    const input = record === "album" ? $("#album-title") : $(`#track-${record} [data-track-field="title"]`);
    input.scrollIntoView({block:"center"}); input.focus();
    notice("Edit and save your draft, then return to the comparison to review the published version. Nothing has been published.");
    return;
  }
  try {
    if (button.hasAttribute("data-review-version")) {
      await saveEdits();
      const record = button.dataset.reviewVersion;
      const current = review.publication.destinations[review.publication.destination].observed[record];
      publicationConfirmation = {record, revision:current.revision};
      renderPublished(review);
      $("[data-confirm-version]").focus();
    } else if (button.hasAttribute("data-cancel-version")) {
      const record = publicationConfirmation.record;
      publicationConfirmation = null;
      renderPublished(review);
      $(`[data-review-version="${record}"]`).focus();
    } else if (button.hasAttribute("data-confirm-version")) {
      await saveEdits();
      const state = await api("/api/publication/baseline", "POST", publicationConfirmation);
      publicationConfirmation = null;
      render(state);
      $("#published-panel").focus({preventScroll:true});
    }
  } catch (error) { notice(error.message, true); }
});
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
