/* ============================================================
   app.js — AwakeMovies Scraper Frontend Logic
   Handles: URL detection, API calls, result rendering
   ============================================================ */


/* ── 1. Configuration ───────────────────────────────────────────────────────
   Replace API_BASE_URL with your deployed Render URL once live.
   Leave it empty ("") to call the same origin (useful if you proxy the API).
   ─────────────────────────────────────────────────────────────────────── */
const API_BASE_URL = "https://your-awake-bot-api.onrender.com"; // ← change this


/* ── 2. Source detection map ────────────────────────────────────────────────
   Maps URL keywords → API endpoint + display label.
   Mirrors the keyword logic used by the Python scrapers on the server.
   ─────────────────────────────────────────────────────────────────────── */
const SOURCES = [
  {
    keywords:  ["9jarocks"],
    id:        "9jarocks",
    label:     "9jarocks",
    endpoint:  "/api/scrape/9jarocks",
    needsSite: false,           // no "site" dropdown needed
  },
  {
    keywords:  ["naijaprey"],
    id:        "naijaprey",
    label:     "NaijaPrey",
    endpoint:  "/api/scrape/naijaprey",
    needsSite: false,
  },
  {
    keywords:  ["nkiri", "thenkiri", "dramakey"],
    id:        "nkiri-dramakey",
    label:     "Nkiri / Dramakey",
    endpoint:  "/api/scrape/nkiri-dramakey",
    needsSite: true,            // show site dropdown (nkiri / dramakey)
  },
];

/* ── 3. DOM element references ──────────────────────────────────────────── */
const urlInput        = document.getElementById("url-input");
const sourceBadge     = document.getElementById("source-badge");
const btnMovie        = document.getElementById("btn-movie");
const btnSeries       = document.getElementById("btn-series");
const siteSelectorRow = document.getElementById("site-selector-row");
const siteSelect      = document.getElementById("site-select");
const scrapeBtn       = document.getElementById("scrape-btn");
const btnSpinner      = document.getElementById("btn-spinner");
const btnLabel        = document.getElementById("btn-label");
const errorMsg        = document.getElementById("error-msg");
const resultSection   = document.getElementById("result-section");

/* Result sub-elements */
const resultPoster      = document.getElementById("result-poster");
const posterPlaceholder = document.getElementById("poster-placeholder");
const resultTitle       = document.getElementById("result-title");
const resultBadges      = document.getElementById("result-badges");
const resultSynopsis    = document.getElementById("result-synopsis");
const resultDetails     = document.getElementById("result-details");
const downloadSection   = document.getElementById("download-section");
const downloadLinks     = document.getElementById("download-links");
const episodesSection   = document.getElementById("episodes-section");
const episodesList      = document.getElementById("episodes-list");
const copyJsonBtn       = document.getElementById("copy-json-btn");
const dlJsonBtn         = document.getElementById("dl-json-btn");


/* ── 4. App state ───────────────────────────────────────────────────────────
   Single source of truth for the current UI state.
   ─────────────────────────────────────────────────────────────────────── */
let state = {
  mode:          "movie",   // "movie" | "series"
  detectedSource: null,     // matched SOURCES entry, or null
  lastResult:    null,      // last successful API response object
};


/* ══════════════════════════════════════════════════════════════════════════
   5. URL INPUT — detect source as the user types
   ══════════════════════════════════════════════════════════════════════ */

urlInput.addEventListener("input", () => {
  const raw = urlInput.value.trim();

  /* Try to extract a valid hostname from the typed URL */
  let hostname = "";
  try {
    hostname = new URL(raw).hostname.toLowerCase();
  } catch {
    /* Not a valid URL yet — just disable the button silently */
  }

  /* Match hostname against each source's keyword list */
  const matched = SOURCES.find(
    (src) => hostname && src.keywords.some((kw) => hostname.includes(kw))
  );

  state.detectedSource = matched ?? null;

  /* Update the badge inside the input row */
  if (matched) {
    sourceBadge.textContent = matched.label;
    sourceBadge.hidden = false;
  } else {
    sourceBadge.hidden = true;
  }

  /* Show / hide the Nkiri/Dramakey site dropdown */
  siteSelectorRow.hidden = !(matched?.needsSite);

  /* Enable the scrape button only when a source was detected */
  scrapeBtn.disabled = !matched;

  /* Clear any previous error when the user starts editing */
  hideError();
});


/* ══════════════════════════════════════════════════════════════════════════
   6. MODE TOGGLE — Movie vs Series
   ══════════════════════════════════════════════════════════════════════ */

[btnMovie, btnSeries].forEach((btn) => {
  btn.addEventListener("click", () => {
    /* Remove active class from both, add to the clicked one */
    btnMovie.classList.remove("active");
    btnSeries.classList.remove("active");
    btn.classList.add("active");

    state.mode = btn.dataset.mode; // "movie" or "series"

    /* Update button label to match selection */
    btnLabel.textContent = `Scrape ${state.mode === "movie" ? "Movie" : "Series"}`;
  });
});


/* ══════════════════════════════════════════════════════════════════════════
   7. SCRAPE — call the API and render the result
   ══════════════════════════════════════════════════════════════════════ */

scrapeBtn.addEventListener("click", async () => {
  const url    = urlInput.value.trim();
  const source = state.detectedSource;

  /* Guard: should never happen because button is disabled without a source */
  if (!source) return;

  /* Build the request body — add "site" only for nkiri-dramakey */
  const body = { url, mode: state.mode };
  if (source.needsSite && siteSelect.value) {
    body.site = siteSelect.value;
  }

  /* ── Show loading state ── */
  setLoading(true);
  hideError();
  hideResult();

  try {
    /* POST to the relevant scrape endpoint */
    const response = await fetch(`${API_BASE_URL}${source.endpoint}`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(body),
    });

    const data = await response.json();

    /* Server returned a scrape-level error (e.g. page not found on source site) */
    if (!response.ok || data.error) {
      showError(data.error || `Server error (${response.status}). Check the URL and try again.`);
      return;
    }

    /* Store result and render it */
    state.lastResult = data;
    renderResult(data);

  } catch (err) {
    /* Network failure (CORS, offline, wrong API_BASE_URL) */
    showError(
      "Could not reach the API. Make sure API_BASE_URL in app.js points to your Render service."
    );
    console.error("Scrape fetch error:", err);
  } finally {
    setLoading(false);
  }
});


/* ══════════════════════════════════════════════════════════════════════════
   8. RENDER RESULT — populate the result card from the API response
   ══════════════════════════════════════════════════════════════════════ */

function renderResult(data) {
  /* ── Poster ── */
  const posterUrl = data._awpt_poster;
  if (posterUrl) {
    resultPoster.src = posterUrl;
    resultPoster.alt = data._awpt_title || "Movie poster";
    resultPoster.hidden = false;
    posterPlaceholder.hidden = true;
  } else {
    resultPoster.hidden = true;
    posterPlaceholder.hidden = false;
  }

  /* ── Title ── */
  resultTitle.textContent = data._awpt_title || "Untitled";

  /* ── Badges: type + genre ── */
  resultBadges.innerHTML = "";
  if (data._awpt_type) {
    resultBadges.appendChild(makeBadge(data._awpt_type, "primary"));
  }
  if (data._awpt_genre) {
    /* Genre can be comma-separated — show one badge per genre */
    data._awpt_genre.split(",").forEach((g) => {
      resultBadges.appendChild(makeBadge(g.trim(), "neutral"));
    });
  }

  /* ── Synopsis ── */
  resultSynopsis.textContent = data._awpt_synopsis || "";
  resultSynopsis.hidden = !data._awpt_synopsis;

  /* ── Key/value metadata table ── */
  const metaFields = [
    ["Rating",   data._awpt_ratings],
    ["Released", data._awpt_release_date],
    ["Runtime",  data._awpt_duration],
    ["Language", data._awpt_language],
    ["Country",  data._awpt_country],
    ["Stars",    data._awpt_stars],
    ["Size",     data._awpt_file_size],
    ["Status",   data._awpt_status],
    ["Season",   data._awpt_season],
    ["Episodes", data._awpt_total_episodes],
    ["Source",   data._awpt_source],
  ];

  resultDetails.innerHTML = "";
  metaFields.forEach(([label, value]) => {
    if (!value) return; // skip empty fields
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = label;
    dd.textContent = value;
    resultDetails.appendChild(dt);
    resultDetails.appendChild(dd);
  });

  /* ── Download links ── */
  const links = data._awpt_download_link;
  if (links && links.length > 0) {
    downloadLinks.innerHTML = "";
    links.forEach(({ quality, link }) => {
      const a = document.createElement("a");
      a.href      = link;
      a.target    = "_blank";
      a.rel       = "noopener noreferrer";
      a.className = "download-btn";
      /* Download icon SVG */
      a.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="7 10 12 15 17 10"/>
          <line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
        ${escapeHtml(quality || "Download")}
      `;
      downloadLinks.appendChild(a);
    });
    downloadSection.hidden = false;
  } else {
    downloadSection.hidden = true;
  }

  /* ── Episodes list (series mode) ── */
  const episodes = data._awpt_episodes;
  if (episodes && episodes.length > 0) {
    episodesList.innerHTML = "";
    episodes.forEach(({ episode, title, url: epUrl }) => {
      const li = document.createElement("li");
      li.className = "episode-item";
      li.innerHTML = `
        <span class="episode-number">${episode}</span>
        <span class="episode-title">${escapeHtml(title || `Episode ${episode}`)}</span>
        ${epUrl
          ? `<a class="episode-link" href="${escapeHtml(epUrl)}"
                target="_blank" rel="noopener noreferrer">Open ↗</a>`
          : ""}
      `;
      episodesList.appendChild(li);
    });
    episodesSection.hidden = false;
  } else {
    episodesSection.hidden = true;
  }

  /* ── Show the result card ── */
  resultSection.hidden = false;
  /* Scroll into view smoothly */
  resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
}


/* ══════════════════════════════════════════════════════════════════════════
   9. JSON EXPORT — copy or download the raw API response
   ══════════════════════════════════════════════════════════════════════ */

/* Copy JSON to clipboard */
copyJsonBtn.addEventListener("click", async () => {
  if (!state.lastResult) return;
  try {
    await navigator.clipboard.writeText(JSON.stringify(state.lastResult, null, 2));
    copyJsonBtn.textContent = "Copied!";
    setTimeout(() => (copyJsonBtn.textContent = "Copy JSON"), 2000);
  } catch {
    copyJsonBtn.textContent = "Failed to copy";
  }
});

/* Download JSON as a .json file */
dlJsonBtn.addEventListener("click", () => {
  if (!state.lastResult) return;
  const blob = new Blob(
    [JSON.stringify(state.lastResult, null, 2)],
    { type: "application/json" }
  );
  const a    = document.createElement("a");
  a.href     = URL.createObjectURL(blob);
  /* Use the movie title as the filename, fall back to "result" */
  const name = (state.lastResult._awpt_title || "result")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
  a.download = `${name}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
});


/* ══════════════════════════════════════════════════════════════════════════
   10. Helper utilities
   ══════════════════════════════════════════════════════════════════════ */

/* Show / hide the loading spinner and disable the button */
function setLoading(isLoading) {
  scrapeBtn.disabled  = isLoading;
  btnSpinner.hidden   = !isLoading;
  btnLabel.textContent = isLoading
    ? "Scraping…"
    : `Scrape ${state.mode === "movie" ? "Movie" : "Series"}`;
}

/* Display an error message below the button */
function showError(message) {
  errorMsg.textContent = message;
  errorMsg.hidden = false;
}

/* Clear the error message */
function hideError() {
  errorMsg.hidden = true;
  errorMsg.textContent = "";
}

/* Hide the result section and clear stored result */
function hideResult() {
  resultSection.hidden = true;
}

/* Create a badge <span> element */
function makeBadge(text, type) {
  const span = document.createElement("span");
  span.className = `badge badge-${type}`;
  span.textContent = text;
  return span;
}

/* Escape HTML special characters to prevent XSS when inserting user / API data */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}


/* ══════════════════════════════════════════════════════════════════════════
   11. Initialise button label on page load
   ══════════════════════════════════════════════════════════════════════ */
btnLabel.textContent = "Scrape Movie";
