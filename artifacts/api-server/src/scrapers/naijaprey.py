import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from scrapers.normalizer import Normalizer

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.naijaprey.tv/",
}

META_BOUNDARIES = re.compile(
    r'^(Genre|Stars?|Release\s*Date|Country|Ratings?|Language|Subtitles?|Source|Runtime|Episodes?|Cast)\s*:',
    re.IGNORECASE
)

FINAL_HOSTS = {"wildshare.net", "gofile.io", "megaup.net", "krakenfiles.com"}
SKIP_LINK_TEXT = re.compile(r'how\s*to\s*download|learn\s*how|can.*download|navigate|menu|home|search', re.IGNORECASE)


def _fetch_soup(url: str, session: requests.Session) -> BeautifulSoup | None:
    try:
        resp = session.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # Only remove scripts/styles
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup
    except Exception:
        return None


def _get_entry(soup: BeautifulSoup):
    entry = soup.find("div", class_=re.compile(r"entry-content", re.I))
    if not entry:
        entry = soup.find("article")
    return entry


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


def _get_poster(soup: BeautifulSoup) -> str:
    try:
        # Priority: og:image, then first large image in entry-content
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            raw = og["content"]
            # Recover full-size from thumbnail (strip -WxH suffix)
            cleaned = re.sub(r'-\d+x\d+(\.\w+)$', r'\1', raw)
            return cleaned

        entry = _get_entry(soup)
        if entry:
            for img in entry.find_all("img", src=True):
                src = img["src"]
                # Skip tiny thumbnails
                if re.search(r'-\d{2,3}x\d{2,3}\.', src):
                    continue
                if "gravatar" in src or "avatar" in src:
                    continue
                return src
    except Exception:
        pass
    return ""


def _get_synopsis_and_meta(soup: BeautifulSoup) -> tuple:
    """Returns (synopsis_str, meta_dict).
    Synopsis = all <p> text before the first metadata field.
    Meta = fields after the boundary."""
    synopsis_parts = []
    meta = {}
    in_synopsis = True

    KEY_MAP = {
        "genre": "_awpt_genre",
        "stars": "_awpt_stars",
        "star": "_awpt_stars",
        "cast": "_awpt_stars",
        "release_date": "_awpt_release_date",
        "country": "_awpt_country",
        "ratings": "_awpt_ratings",
        "rating": "_awpt_ratings",
        "language": "_awpt_language",
        "subtitles": "_awpt_subtitles",
        "subtitle": "_awpt_subtitles",
        "source": "_awpt_source",
        "runtime": "_awpt_duration",
        "episodes": "_awpt_total_episodes",
        "episode": "_awpt_total_episodes",
    }

    try:
        entry = _get_entry(soup)
        if not entry:
            return "", meta

        for el in entry.descendants:
            if not hasattr(el, "get_text"):
                continue
            # Only process block-level elements
            if el.name not in ("p", "div", "span", "li", "h2", "h3", "h4"):
                continue
            # Skip if this element has block children (avoid double-processing)
            if el.find(["p", "div"]):
                continue

            text = el.get_text(strip=True)
            if not text:
                continue

            # Check if this looks like a metadata field
            field_match = re.match(
                r'^(Genre|Stars?|Cast|Release\s*Date|Country|Ratings?|Language|'
                r'Subtitles?|Source|Runtime|Episodes?)\s*:\s*(.+)',
                text, re.IGNORECASE | re.DOTALL
            )
            if field_match:
                in_synopsis = False
                key = field_match.group(1).strip().lower().replace(" ", "_")
                val = field_match.group(2).strip().split("\n")[0].strip()
                if key in KEY_MAP:
                    meta[KEY_MAP[key]] = val
            elif in_synopsis:
                # Skip ads/noise
                if re.search(r'advertisement|allow\s*ads|popup|sponsored', text, re.IGNORECASE):
                    continue
                if len(text) > 25:
                    synopsis_parts.append(text)

    except Exception:
        pass

    synopsis = " ".join(synopsis_parts)
    return Normalizer.normalize_synopsis(synopsis), meta


def _get_trailer(soup: BeautifulSoup) -> str:
    try:
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "") or iframe.get("data-src", "")
            if "youtube" in src or "youtu.be" in src:
                return Normalizer.normalize_youtube(src)
        for a in soup.find_all("a", href=re.compile(r"youtube|youtu\.be", re.I)):
            href = a.get("href", "")
            if href:
                return Normalizer.normalize_youtube(href)
    except Exception:
        pass
    return ""


def _resolve_url(url: str, session: requests.Session, hops: int = 3) -> str:
    """Follow redirects up to `hops` times to find the final file URL."""
    if not url or hops <= 0:
        return url or ""
    try:
        parsed = urlparse(url)
        # If already at final host, return
        if any(h in parsed.netloc for h in FINAL_HOSTS):
            return url
        # Try HEAD for redirect
        try:
            resp = session.head(url, headers=HEADERS, timeout=12,
                                allow_redirects=False, stream=True)
            loc = resp.headers.get("Location", "")
            if loc:
                return _resolve_url(urljoin(url, loc), session, hops - 1)
        except Exception:
            pass
        # Try GET and look for a link to the final host
        try:
            resp = session.get(url, headers=HEADERS, timeout=12)
            page_soup = BeautifulSoup(resp.text, "lxml")
            for a in page_soup.find_all("a", href=True):
                href = a["href"]
                if any(h in href for h in FINAL_HOSTS):
                    return href
            # Any outbound http link that isn't an intermediate
            for a in page_soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("http") and href != url:
                    return _resolve_url(href, session, hops - 1)
        except Exception:
            pass
    except Exception:
        pass
    return url


def _find_download_links(soup: BeautifulSoup, session: requests.Session, base_url: str) -> list:
    """Find download buttons/links, resolve to final URLs."""
    links = []
    seen = set()
    try:
        entry = _get_entry(soup)
        if not entry:
            return links

        for a in entry.find_all("a", href=True):
            href = a.get("href", "").strip()
            text = a.get_text(strip=True)
            if not href or href == "#":
                continue
            if SKIP_LINK_TEXT.search(text):
                continue
            # Look for download-intent links
            if not re.search(r'download|episode\s*\d+|ep\s*\d+|season\s*\d+', text, re.IGNORECASE):
                # Also accept links that go to plausible download hosts
                if not re.search(r'naijaprey|np-downloader|wildshare|gofile|mega', href, re.IGNORECASE):
                    continue
            if href in seen:
                continue
            seen.add(href)

            abs_href = urljoin(base_url, href)
            final_url = _resolve_url(abs_href, session)

            quality_match = re.search(r'(\d{3,4}p)', text)
            quality = quality_match.group(1) if quality_match else (text or "Download")
            links.append({"quality": quality, "link": final_url})
    except Exception:
        pass
    return links


def _find_episodes(soup: BeautifulSoup, session: requests.Session, base_url: str) -> tuple:
    """Find episode links and resolve to final URLs."""
    episodes = []
    status = "Added"
    seen_eps = set()
    try:
        entry = _get_entry(soup)
        if not entry:
            return episodes, status

        full_text = entry.get_text()
        declared_total = None
        declared_match = re.search(r'Episodes?\s*:\s*(\d+)', full_text, re.IGNORECASE)
        if declared_match:
            declared_total = int(declared_match.group(1))

        # Only trust an explicit "Status: Completed/Ongoing/Airing" label.
        # A bare substring search for "complete" anywhere in the free-text
        # entry (synopsis, related posts, ads, etc.) caused false positives
        # — shows still airing were being marked "Completed".
        status_match = re.search(r'Status\s*:?\s*(Ongoing|Completed?|Airing)', full_text, re.IGNORECASE)
        if status_match:
            status = Normalizer.normalize_status(status_match.group(1))

        for a in entry.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a.get("href", "").strip()
            if not href or href == "#":
                continue
            if SKIP_LINK_TEXT.search(text):
                continue
            ep_match = re.search(r'[Ee]pisode\s*(\d+)|[Ee][Pp]\.?\s*(\d+)', text)
            if not ep_match:
                continue
            ep_num = int(ep_match.group(1) or ep_match.group(2))
            if ep_num in seen_eps:
                continue
            seen_eps.add(ep_num)
            abs_href = urljoin(base_url, href)
            final_url = _resolve_url(abs_href, session)
            episodes.append({"episode": ep_num, "title": text, "url": final_url})

        if status != "Completed" and declared_total is not None and len(episodes) > 0:
            if len(episodes) >= declared_total:
                status = "Completed"
    except Exception:
        pass

    episodes = Normalizer.normalize_episodes(episodes)
    return episodes, status


def scrape(url: str, mode: str) -> dict:
    try:
        session = requests.Session()
        soup = _fetch_soup(url, session)
        if not soup:
            return {"error": "DOWNLOAD RESOLUTION FAILED"}

        title_raw         = _get_title(soup)
        synopsis, meta    = _get_synopsis_and_meta(soup)
        poster            = _get_poster(soup)
        trailer           = _get_trailer(soup)

        if not title_raw or not synopsis:
            return {"error": "DOWNLOAD RESOLUTION FAILED"}

        if mode == "movie":
            download_links = _find_download_links(soup, session, url)
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
                "_awpt_ratings":      meta.get("_awpt_ratings", ""),
                "_awpt_language":     meta.get("_awpt_language", ""),
                "_awpt_subtitles":    meta.get("_awpt_subtitles", ""),
                "_awpt_source":       meta.get("_awpt_source", "naijaprey"),
                "_awpt_duration":     meta.get("_awpt_duration", ""),
                "_awpt_status":       "Movie",
                "_awpt_download_link": download_links,
                "_awpt_additional_info": {},
            }
        else:
            episodes, status = _find_episodes(soup, session, url)
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
                "_awpt_ratings":      meta.get("_awpt_ratings", ""),
                "_awpt_language":     meta.get("_awpt_language", ""),
                "_awpt_subtitles":    meta.get("_awpt_subtitles", ""),
                "_awpt_source":       meta.get("_awpt_source", "naijaprey"),
                "_awpt_total_episodes": str(len(episodes)),
                "_awpt_status":       Normalizer.normalize_status(status),
                "_awpt_season":       season_match.group(1) if season_match else "",
                "_awpt_episodes":     episodes,
                "_awpt_additional_info": {},
            }

        final = Normalizer.remove_empty_fields(result)
        final["_awpt_trailer_url"] = final.get("_awpt_trailer_url", "")
        return final

    except Exception:
        return {"error": "DOWNLOAD RESOLUTION FAILED"}
