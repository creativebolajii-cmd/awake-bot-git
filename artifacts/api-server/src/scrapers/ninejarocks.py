import re
import requests
from bs4 import BeautifulSoup
from scrapers.normalizer import Normalizer

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

VALID_DOMAIN = "loadedfiles.org"


def _fetch(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # Only remove scripts/styles — no class-based cleanup that destroys content
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup
    except Exception:
        return None


def _is_valid_link(url: str) -> bool:
    return bool(url and VALID_DOMAIN in url)


def _get_entry(soup: BeautifulSoup):
    """Find the main content container."""
    entry = soup.find("div", class_=re.compile(r"entry-content", re.I))
    if not entry:
        entry = soup.find("article")
    return entry


def _get_poster(soup: BeautifulSoup) -> str:
    try:
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return og["content"]
        img = soup.find("img", class_=re.compile(r"wp-post-image|featured", re.I))
        if img and img.get("src"):
            return img["src"]
    except Exception:
        pass
    return ""


def _get_title(soup: BeautifulSoup) -> str:
    """Returns the raw title text (no year/season normalization yet — that
    happens later once we know whether this is a movie or series)."""
    try:
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        og = soup.find("meta", property="og:title")
        if og:
            return og.get("content", "")
    except Exception:
        pass
    return ""


def _get_synopsis(soup: BeautifulSoup) -> str:
    try:
        entry = _get_entry(soup)
        if not entry:
            return ""
        for p in entry.find_all("p"):
            # Skip blockquotes (metadata) and very short text
            if p.find_parent("blockquote"):
                continue
            text = p.get_text(strip=True)
            if len(text) > 30 and not re.match(r'^(Download|Watch|Click|Share|Tags|Filed)', text, re.IGNORECASE):
                return Normalizer.normalize_synopsis(text)
    except Exception:
        pass
    return ""


def _get_trailer(soup: BeautifulSoup) -> str:
    try:
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "") or iframe.get("data-src", "")
            if "youtube" in src or "youtu.be" in src:
                return Normalizer.normalize_youtube(src)
    except Exception:
        pass
    return ""


def _get_metadata(soup: BeautifulSoup) -> dict:
    """Extract metadata from the blockquote/metadata block."""
    meta = {}
    try:
        # 9jarocks puts metadata in a <blockquote> element
        bq = soup.find("blockquote")
        if not bq:
            entry = _get_entry(soup)
            bq = entry if entry else soup
        text = bq.get_text(separator="\n")
        patterns = {
            "_awpt_title_meta": r"(?:Title|Filename)\s*:\s*(.+)",
            "_awpt_file_size":   r"Filesize\s*:\s*(.+)",
            "_awpt_duration":    r"Duration\s*:\s*(.+)",
            "_awpt_release_date":r"(?:Year|Release[- ]?[Dd]ate)\s*:\s*(.+)",
            "_awpt_country":     r"Country\s*:\s*(.+)",
            "_awpt_language":    r"Language\s*:\s*(.+)",
            "_awpt_genre":       r"Genre\s*:\s*(.+)",
            "_awpt_stars":       r"(?:Stars?|Cast)\s*:\s*(.+)",
            "_awpt_subtitles":   r"Subtitle\s*:\s*(.+)",
        }
        for key, pattern in patterns.items():
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                val = m.group(1).strip().split("\n")[0].strip()
                meta[key] = val
    except Exception:
        pass
    return meta


def _get_download_links_movie(soup: BeautifulSoup) -> list:
    """Find all DOWNLOAD links pointing to loadedfiles.org."""
    links = []
    seen = set()
    try:
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            if not _is_valid_link(href):
                continue
            if href in seen:
                continue
            text = a.get_text(strip=True)
            if "FAST SERVER" in text.upper():
                continue
            seen.add(href)
            links.append({"quality": text or "DOWNLOAD", "link": href})
    except Exception:
        pass
    return links


def _ep_num_from_href(href: str) -> int | None:
    """Try to extract episode number from a loadedfiles.org URL filename."""
    for pat in [r'[Ss]\d+[Ee](\d+)', r'[Ee]p(?:isode)?[._\s-]?(\d+)']:
        m = re.search(pat, href)
        if m:
            return int(m.group(1))
    return None


def _get_episodes_series(soup: BeautifulSoup) -> tuple:
    """
    On 9jarocks series pages, episodes look like:
      <p>EPISODE 1 | <a href="https://loadedfiles.org/...">DOWNLOAD</a></p>
    Both the episode label and link are in the SAME <p> tag.

    Fallback: if no labelled EPISODE paragraphs are found, collect ALL
    loadedfiles.org links in document order and number them sequentially
    (some pages omit the EPISODE label).
    """
    episodes = []
    status = "Added"
    try:
        entry = _get_entry(soup)
        if not entry:
            return episodes, status

        full_text = entry.get_text()
        if re.search(r'\bcomplete\b|\bcompleted\b', full_text, re.IGNORECASE):
            status = "Completed"

        # ── Strategy 1: EPISODE N label + loadedfiles.org link in same <p> ──
        seen_eps: set[int] = set()
        seen_hrefs: set[str] = set()
        for p in entry.find_all("p"):
            p_text = p.get_text(separator=" ", strip=True)
            ep_match = re.search(r'EPISODE\s+(\d+)', p_text, re.IGNORECASE)
            if not ep_match:
                continue
            ep_num = int(ep_match.group(1))
            if ep_num in seen_eps:
                continue
            a_tag = p.find("a", href=lambda h: h and VALID_DOMAIN in h)
            if not a_tag or a_tag["href"] in seen_hrefs:
                continue
            seen_eps.add(ep_num)
            seen_hrefs.add(a_tag["href"])
            episodes.append({
                "episode": ep_num,
                "title": f"Episode {ep_num}",
                "url": a_tag["href"],
            })

        # ── Strategy 2 fallback: collect all loadedfiles.org links in order ──
        if not episodes:
            raw: list[str] = []
            for a in entry.find_all("a", href=True):
                href = a["href"].strip()
                if _is_valid_link(href) and "FAST SERVER" not in a.get_text(strip=True).upper():
                    if href not in seen_hrefs:
                        seen_hrefs.add(href)
                        raw.append(href)
            for i, href in enumerate(raw, start=1):
                ep_num = _ep_num_from_href(href) or i
                episodes.append({"episode": ep_num, "title": f"Episode {ep_num}", "url": href})

    except Exception:
        pass

    episodes = Normalizer.normalize_episodes(episodes)
    return episodes, status


def scrape(url: str, mode: str) -> dict:
    try:
        soup = _fetch(url)
        if not soup:
            return {"error": "DOWNLOAD RESOLUTION FAILED"}

        title_raw = _get_title(soup)
        synopsis  = _get_synopsis(soup)
        poster    = _get_poster(soup)
        trailer   = _get_trailer(soup)
        meta      = _get_metadata(soup)

        # Prefer metadata title over H1 title if available
        if meta.get("_awpt_title_meta"):
            # Use H1 for display title (cleaner), meta title for filename info
            meta.pop("_awpt_title_meta", None)

        if not synopsis:
            return {"error": "DOWNLOAD RESOLUTION FAILED"}

        if mode == "movie":
            download_links = _get_download_links_movie(soup)
            if not download_links:
                return {"error": "DOWNLOAD RESOLUTION FAILED"}

            title = Normalizer.normalize_title(title_raw, mode="movie")
            result = {
                "_awpt_type": "movie",
                "_awpt_title": title,
                "_awpt_synopsis": synopsis,
                "_awpt_poster": poster,
                "_awpt_trailer_url": trailer,
                "_awpt_genre":        Normalizer.normalize_genre(meta.get("_awpt_genre", "")),
                "_awpt_stars":        meta.get("_awpt_stars", ""),
                "_awpt_release_date": Normalizer.normalize_year(meta.get("_awpt_release_date", "")),
                "_awpt_country":      meta.get("_awpt_country", ""),
                "_awpt_language":     meta.get("_awpt_language", ""),
                "_awpt_subtitles":    meta.get("_awpt_subtitles", ""),
                "_awpt_source":       "9jarocks",
                "_awpt_duration":     meta.get("_awpt_duration", ""),
                "_awpt_file_size":    meta.get("_awpt_file_size", ""),
                "_awpt_status":       "Movie",
                "_awpt_download_link": download_links,
                "_awpt_additional_info": {},
            }
        else:
            episodes, status = _get_episodes_series(soup)
            if not episodes:
                return {"error": "DOWNLOAD RESOLUTION FAILED"}

            season_match = re.search(r'Season\s*(\d+)', title_raw, re.IGNORECASE)
            title = Normalizer.normalize_title(title_raw, mode="series")
            result = {
                "_awpt_type": "series",
                "_awpt_title": title,
                "_awpt_synopsis": synopsis,
                "_awpt_poster": poster,
                "_awpt_trailer_url": trailer,
                "_awpt_genre":        Normalizer.normalize_genre(meta.get("_awpt_genre", "")),
                "_awpt_stars":        meta.get("_awpt_stars", ""),
                "_awpt_release_date": Normalizer.normalize_year(meta.get("_awpt_release_date", "")),
                "_awpt_country":      meta.get("_awpt_country", ""),
                "_awpt_language":     meta.get("_awpt_language", ""),
                "_awpt_subtitles":    meta.get("_awpt_subtitles", ""),
                "_awpt_source":       "9jarocks",
                "_awpt_total_episodes": str(len(episodes)),
                "_awpt_status":       status,
                "_awpt_season":       season_match.group(1) if season_match else "",
                "_awpt_episodes":     episodes,
                "_awpt_additional_info": {},
            }

        final = Normalizer.remove_empty_fields(result)
        # Always preserve trailer_url even when empty
        final["_awpt_trailer_url"] = final.get("_awpt_trailer_url", "")
        return final

    except Exception:
        return {"error": "DOWNLOAD RESOLUTION FAILED"}
