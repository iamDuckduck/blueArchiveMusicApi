const $ = selector => document.querySelector(selector);
let catalog;
let polling = false;
let releaseIdentity = crypto.randomUUID();
const requestedView = new URLSearchParams(location.search).get("view");
let view = ["all", "new", "saved", "skipped"].includes(requestedView) ? requestedView : "all";
const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[c]);
const decisionLabels = {included:"Included for review", review:"Needs review", skipped:"Skipped", grouping:"Source grouping", linked:"Linked to existing collection"};
const kindLabels = {release_candidate:"Candidate collection", source_grouping:"Broad source group", unresolved:"Unidentified source group"};

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function render() {
  if (!catalog) return;
  $("#scan-status").textContent = catalog.scan.message;
  $("#scan").disabled = catalog.scan.running;
  const query = $("#filter").value.toLowerCase();
  const visible = CatalogHome.rows(catalog).filter(row => CatalogHome.matches(row, view, query));
  const albums = visible.filter(row => !CatalogHome.isGroup(row));
  const groups = visible.filter(CatalogHome.isGroup);
  for (const button of document.querySelectorAll("[data-view]")) button.setAttribute("aria-pressed", String(button.dataset.view === view));
  $("#candidates").innerHTML = (albums.map(renderRow).join("") || '<p>No matching albums. Scan Kivo or change the filters.</p>') +
    (groups.length ? `<details><summary>Source groups and linked labels (${groups.length})</summary>${groups.map(renderRow).join("")}</details>` : "");
}

function renderRow({candidate:c, review, title}) {
  if (!c) return `<section class="panel"><h2>${escapeHtml(title)}</h2><p>Saved draft · ${review.track_count} tracks</p><a class="button primary" href="${escapeHtml(review.url)}">Continue review</a></section>`;
  const canReview = c.kind === "release_candidate" && c.decision !== "grouping" && !c.redirect_to;
  const primary = c.redirect_to ? `<a class="button secondary" href="/albums/${c.redirect_to}/">Open linked review</a>` : !canReview ? "" : review ?
    `<a class="button primary" href="${escapeHtml(review.url)}">Continue review</a>` : `<button class="button primary" data-start ${catalog.scan.running ? "disabled" : ""}>Start review</button>`;
  return `
    <section class="panel" data-candidate="${c.id}">
      <h2>${escapeHtml(title || "Unidentified source group")}</h2>
      <p>${review ? "Saved draft" : "Not started"} · ${c.track_count} source tracks · <strong>${escapeHtml(decisionLabels[c.decision])}</strong>${!c.seen_in_latest_scan && !c.manual ? " · Not seen in latest scan (retained)" : ""}</p>
      ${primary}
      <details><summary>Source and decisions</summary>
      <p>${escapeHtml(c.source_album)} · ${escapeHtml(kindLabels[c.kind])} · ${c.mapped_track_count} mapped tracks</p>
      <div class="album-actions">
        <button class="button primary" data-decision="included" ${catalog.scan.running || c.kind !== "release_candidate" || c.redirect_to || c.decision === "included" ? "disabled" : ""}>Include for review</button>
        <button class="button quiet" data-decision="skipped" ${catalog.scan.running || c.redirect_to || c.decision === "skipped" ? "disabled" : ""}>Skip</button>
        <button class="button quiet" data-decision="grouping" ${catalog.scan.running || c.redirect_to || c.decision === "grouping" ? "disabled" : ""}>Source grouping</button>
        <button class="button quiet" data-decision="review" ${catalog.scan.running || c.redirect_to || c.decision === "review" ? "disabled" : ""}>Needs review</button>
        <button class="button secondary" data-evidence>Inspect source tracks</button>
      </div>
      <p class="helper">Inclusion is saved for preparation. Publication still requires a later review and publish action.</p>
      <div class="mapping"></div><pre class="source-evidence" hidden></pre></details>
    </section>`;
}

async function act(path, body) {
  try { catalog = await api(path, body); render(); $("#notice").hidden = true; return true; }
  catch (error) { $("#notice").textContent = error.message; $("#notice").hidden = false; return false; }
}

$("#create-release").addEventListener("submit", async event => {
  event.preventDefault();
  const fields = new FormData(event.target);
  if (await act("/api/catalog/releases", {id:releaseIdentity, title:fields.get("title"), category:fields.get("category"), reference:fields.get("reference"), official:fields.has("official")})) {
    releaseIdentity = crypto.randomUUID();
    event.target.reset();
  }
});

$("#scan").addEventListener("click", () => act("/api/catalog/scan", {}));
$("#filter").addEventListener("input", render);
for (const button of document.querySelectorAll("[data-view]")) button.addEventListener("click", () => {
  view = button.dataset.view;
  history.replaceState(null, "", view === "all" ? "/catalog" : `/catalog?view=${view}`);
  render();
});
$("#candidates").addEventListener("click", async event => {
  const button = event.target.closest("button");
  if (!button) return;
  const section = button.closest("[data-candidate]");
  if (button.hasAttribute("data-start")) {
    const identity = section.dataset.candidate;
    if (await act(`/api/catalog/${identity}/decision`, {decision:"included"})) location.href = `/albums/${identity}/`;
    return;
  }
  if (button.dataset.decision) return act(`/api/catalog/${section.dataset.candidate}/decision`, {decision:button.dataset.decision});
  if (button.hasAttribute("data-map") || button.hasAttribute("data-link")) {
    const target = section.querySelector("[data-target]").value;
    const track_ids = Array.from(section.querySelectorAll("[data-source-track]:checked"), input => Number(input.value));
    const action = button.hasAttribute("data-map") ? "map" : "link";
    return act(`/api/catalog/${section.dataset.candidate}/${action}`, {target, track_ids});
  }
  if (button.hasAttribute("data-evidence")) {
    try {
      const item = await api(`/api/catalog/${section.dataset.candidate}`);
      const evidence = section.querySelector("pre");
      evidence.textContent = JSON.stringify({changes:item.changes, tracks:item.records, previous:item.previous_records}, null, 2);
      evidence.hidden = false;
      const targets = catalog.candidates.filter(c => c.id !== item.id && c.kind === "release_candidate" && !c.redirect_to && c.decision !== "grouping");
      section.querySelector(".mapping").innerHTML = `<fieldset><legend>Map source tracks to an identified release</legend>
        <label>Target release<select data-target><option value="">Choose an existing release</option>${targets.map(c => `<option value="${c.id}">${escapeHtml(c.source_album)}</option>`).join("")}</select></label>
        ${item.records.map(t => `<label class="checkbox-row"><input type="checkbox" data-source-track value="${t.id}"> #${t.id} ${escapeHtml(t.title)}</label>`).join("")}
        <button type="button" class="button primary" data-map>Map selected tracks</button>
        ${item.kind === "release_candidate" && !item.manual && !item.redirect_to ? '<button type="button" class="button quiet" data-link>Same release / renamed label: link to target</button>' : ""}
        <p class="helper">Mapping retains the source and creates unselected track appearances in the target review. Linking is only for the same release, not another edition; existing saved reviews are never merged or deleted.</p>
      </fieldset>`;
    } catch (error) { $("#notice").textContent = error.message; $("#notice").hidden = false; }
  }
});

async function refresh() {
  if (polling) return;
  polling = true;
  try {
    const next = await api("/api/catalog");
    // Keep an expanded source panel intact while the saved catalog is unchanged.
    if (JSON.stringify(next) !== JSON.stringify(catalog)) { catalog = next; render(); }
  } catch (error) { $("#notice").textContent = error.message; $("#notice").hidden = false; }
  finally { polling = false; }
}
refresh();
setInterval(refresh, 1800);
