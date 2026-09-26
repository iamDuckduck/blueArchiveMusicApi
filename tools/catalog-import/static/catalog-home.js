/* Pure list projection: candidate IDs connect drafts; titles are only display/search text. */
const CatalogHome = {
  rows(catalog) {
    const reviews = new Map(catalog.reviews.map(review => [review.id, review]));
    const rows = catalog.candidates.map(candidate => {
      const review = reviews.get(candidate.id);
      reviews.delete(candidate.id);
      return {candidate, review, title: review ? review.title : candidate.source_album};
    });
    for (const review of reviews.values()) rows.push({review, title: review.title});
    return rows;
  },
  isGroup(row) {
    return Boolean(row.candidate && (row.candidate.kind !== "release_candidate" || row.candidate.decision === "grouping" || row.candidate.redirect_to));
  },
  matches(row, view, query) {
    const decision = row.candidate ? row.candidate.decision : row.review.decision;
    if (view === "saved" && !row.review) return false;
    if (view === "new" && (row.review || decision !== "review")) return false;
    if (view === "skipped" && decision !== "skipped") return false;
    return `${row.title} ${row.candidate?.source_album || ""} ${decision}`.toLowerCase().includes(query.toLowerCase());
  }
};
if (typeof module !== "undefined") module.exports = CatalogHome;
