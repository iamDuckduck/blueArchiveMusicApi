const $ = selector => document.querySelector(selector);
const enabled = document.body.dataset.creditsEnabled === "true";
let selected = null;
let busy = false;

const aliases = () => $("#credit-aliases").value.split(/\r?\n/).map(name => name.trim()).filter(Boolean);
const dirty = () => selected !== null && JSON.stringify(aliases()) !== JSON.stringify(selected.aliases);

function notice(message, error = false) {
  $("#notice").textContent = message;
  $("#notice").className = error ? "error" : "";
  $("#notice").hidden = false;
}

function controls() {
  $("#search-credits").disabled = busy || !enabled;
  $("#credit-query").disabled = busy || !enabled;
  $("#credit-aliases").disabled = busy || !enabled;
  $("#save-aliases").disabled = busy || !enabled || !dirty();
  $("#reset-aliases").disabled = busy || !dirty();
  for (const button of document.querySelectorAll("[data-profile-id]")) button.disabled = busy;
  $("#alias-status").textContent = busy ? "Contacting the configured backend…" : dirty() ? "Unsaved edits on this page. Save explicitly to update backend search." : "No unsaved alias edits.";
}

async function api(path, method = "GET", body) {
  const response = await fetch(path, {method, headers:body === undefined ? {} : {"Content-Type":"application/json"}, body:body === undefined ? undefined : JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Backend request failed (${response.status}).`);
  return result;
}

function showProfile(profile) {
  selected = profile;
  const resultDetail = document.querySelector(`[data-profile-id="${profile.id}"] small`);
  if (resultDetail) resultDetail.textContent = `Profile #${profile.id} · ${profile.aliases.length} aliases`;
  $("#credit-empty").hidden = true;
  $("#credit-editor").hidden = false;
  $("#credit-name").textContent = profile.name;
  $("#credit-identity").textContent = `Published profile #${profile.id} · identity is unchanged by aliases`;
  $("#credit-aliases").value = profile.aliases.join("\n");
  $("#credit-context").replaceChildren();
  for (const [label, value] of [["Character", profile.characterName], ["Voice actor", profile.voiceActorName]]) {
    if (!value) continue;
    const term = document.createElement("dt"), description = document.createElement("dd");
    term.textContent = label; description.textContent = value;
    $("#credit-context").append(term, description);
  }
}

$("#credit-search").addEventListener("submit", async event => {
  event.preventDefault(); busy = true; controls();
  $("#credit-results").replaceChildren(); $("#search-status").textContent = "Searching published profiles…";
  try {
    const result = await api("/api/credits?query=" + encodeURIComponent($("#credit-query").value));
    $("#search-status").textContent = result.profiles.length ? `${result.profiles.length} profiles found (maximum 50).` : "No matching published credits.";
    for (const profile of result.profiles) {
      const row = document.createElement("li"), button = document.createElement("button"), detail = document.createElement("small");
      button.type = "button"; button.className = "button secondary"; button.dataset.profileId = profile.id;
      button.textContent = profile.name; detail.textContent = `Profile #${profile.id} · ${profile.aliases.length} aliases`;
      button.append(detail); row.append(button); $("#credit-results").append(row);
    }
  } catch (error) { $("#search-status").textContent = "Search did not complete."; notice(error.message, true); }
  finally { busy = false; controls(); }
});

$("#credit-results").addEventListener("click", async event => {
  const button = event.target.closest("[data-profile-id]");
  if (!button || busy || (dirty() && !window.confirm("Discard your unsaved alias edits and open this profile?"))) return;
  busy = true; controls();
  try { showProfile(await api(`/api/credits/${button.dataset.profileId}`)); $("#notice").hidden = true; }
  catch (error) { notice(error.message, true); }
  finally { busy = false; controls(); }
});

$("#credit-aliases").addEventListener("input", controls);
$("#reset-aliases").addEventListener("click", () => { showProfile(selected); controls(); });
$("#credit-editor").addEventListener("submit", async event => {
  event.preventDefault(); if (!selected || busy || !dirty()) return;
  busy = true; controls();
  try {
    showProfile(await api(`/api/credits/${selected.id}/aliases`, "PUT", {aliases:aliases()}));
    notice("Aliases saved to the configured backend. Music search now uses them; the profile identity and local import draft were not changed.");
  } catch (error) { notice(error.message, true); }
  finally { busy = false; controls(); }
});
window.addEventListener("beforeunload", event => { if (dirty()) { event.preventDefault(); event.returnValue = ""; } });
controls();
