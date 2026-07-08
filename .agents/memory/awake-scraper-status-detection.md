---
name: Awake-Bot scraper status detection
description: Rule for how "Completed/Ongoing/Added" status must be derived in the 9jarocks/NaijaPrey/Nkiri/Dramakey scrapers.
---

Status ("Added"/"Ongoing"/"Completed") must only be set from an explicit
`Status: <value>` label found on the page (regex `Status\s*:?\s*(Ongoing|Completed?|Airing)`,
normalized via `Normalizer.normalize_status`). Never re-introduce a naive
full-page substring search for the word "complete" — synopsis text, related-post
widgets, and ads on 9jarocks/NaijaPrey contain that word unrelated to airing
status, which caused ongoing series to be wrongly marked "Completed".

**Why:** User-reported bug (2026-07-08): 9jarocks series showed "Completed" for
shows that were still airing/"Added". Traced to `re.search(r'\bcomplete\b|\bcompleted\b', full_text)`
matching anywhere in the entry-content text. Nkiri/Dramakey already used the
stricter label-based regex and the user confirmed it works correctly, so the
same pattern was applied to ninejarocks.py and naijaprey.py.

**How to apply:** When touching status detection in any of the four scrapers
(`ninejarocks.py`, `naijaprey.py`, `nkiri_dramakey.py`), keep the label-based
regex as the only text-based source of truth. NaijaPrey's separate
declared-episode-count-vs-scraped-count fallback (structural, not text search)
is fine to keep as an independent path to "Completed".
