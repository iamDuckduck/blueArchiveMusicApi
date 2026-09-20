/* Translate backend fields into the same vocabulary as the saved review. */
function publicationRows(record, state, current) {
  const local = record === "album" ? state.album : state.tracks.find(track => track.id === record);
  const fields = local.fields;
  const rows = [];
  const display = value => Array.isArray(value) ? (value.length ? value.join("\n") : "None")
    : value == null ? "Not provided" : value === "" ? "Empty" : String(value);
  const add = (label, published, draft) => rows.push({label,
    published: current.exists ? display(published) : "Not published",
    draft: display(draft), same: current.exists && JSON.stringify(published) === JSON.stringify(draft)});
  if (record === "album") {
    for (const [label, published, draft] of [["Title", "title", "title"], ["Category", "category", "category"],
      ["Release date", "releaseDate", "release_date"], ["Notes", "description", "notes"]]) {
      add(label, current.metadata[published], draft === "title" ? fields.title.trim() : draft === "release_date" ? fields[draft] || null : fields[draft]);
    }
  } else {
    for (const [label, published, draft] of [["Title", "title", "title"], ["Disc number", "disc", "disc"],
      ["Track number", "position", "position"], ["Display order", "displayOrder", "display_order"],
      ["Music type", "kind", "kind"], ["Notes", "description", "notes"]]) add(label, current.metadata[published], draft === "title" ? fields.title.trim() : fields[draft]);
    const performers = fields.performers.map(item => [item.character.trim(), item.voice_actor.trim()].filter(Boolean).join(" / "));
    const names = list => [...new Set(list.map(name => name.trim()).filter(Boolean))].sort();
    const draftCredits = {ARTIST: names([...fields.group, ...(fields.kind === "instrumental" ? [] : performers)]),
      COMPOSER: names(fields.composer), ASSOCIATED: fields.kind === "instrumental" ? names(performers) : []};
    for (const [type, label] of [["ARTIST", "Artists / performers"], ["COMPOSER", "Composers"], ["ASSOCIATED", "Associated characters / voices"]]) {
      add(label, names((current.metadata.credits || []).filter(credit => credit.type === type).map(credit => credit.name)), draftCredits[type]);
    }
  }
  const media = (label, key, prepared) => {
    if (!key && !prepared?.sha256) return;
    const match = typeof key === "string" ? key.match(/\/([0-9a-f]{64})\.[a-z0-9]+$/) : null;
    const same = !!match && prepared?.sha256 === match[1];
    rows.push({label, published: key ? "Stored file" : "No file", draft: !prepared?.sha256 ? "Not prepared"
      : same ? "Same file content" : match ? "Different file content" : "Prepared · comparison unavailable", same, unknown:!!key && !match});
  };
  if (record === "album") {
    for (const [label, key, size] of [["Original cover", "coverOriginal", "original"], ["400 px cover", "cover400", "400"], ["800 px cover", "cover800", "800"], ["Displayed cover", "coverImage", "800"]]) {
      media(label, current.media[key], local.cover.files?.[size]);
    }
  } else {
    media("Audio", current.media.audio, local.media);
    media("Track cover", current.media.image, state.album.cover.files?.["400"]);
  }
  return rows;
}
if (typeof module !== "undefined") module.exports = {publicationRows};
