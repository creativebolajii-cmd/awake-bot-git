import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
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

VALID_DOWNLOAD_DOMAIN = "downloadwella.com"
NOISE_TEXTS = re.compile(
    r"how\s+to\s+download|can'?t\s+download|cannot\s+download|"
    r"you\s+might\s+also|related\s+post|sponsored|advertisement",
    re.IGNORECASE
)


def _fetch_soup(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # Only remove scripts/styles — NO class-based cleanup
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup
    except Exception:
        return None


def _identify_site(url: str, site_hint: str = "") -> str:
    if site_hint in ("nkiri", "dramakey"):
        return site_hint
    domain = urlparse(url).netloc.lower()
    if "nkiri" in domain or "thenkiri" in domain:
        return "nkiri"
    if "dramakey" in domain:
        return "dramakey"
    return site_hint or "nkiri"


def _get_entry(soup: BeautifulSoup):
    entry = soup.find("div", class_=re.compile(r"entry-content|post-content|the-content", re.I))
    if not entry:
        entry = soup.find("article")
    return entry


_TYPE_TAGS = (
    r'Korean|Chinese|Japanese|Thai|Filipino|Hollywood|Nollywood|'
    r'Asian|Bollywood|TV\s*Series|Drama|Movie'
)


def _clean_nkiri_title(raw: str, mode: str = "series") -> str:
    """Strip nkiri/dramakey title junk: 'DOWNLOAD X | Download Y Movie' → 'X'."""
    t = raw.strip()
    # Remove leading "DOWNLOAD " prefix (case-insensitive)
    t = re.sub(r'^DOWNLOAD\s+', '', t, flags=re.IGNORECASE).strip()
    # Drop trailing site-description sentences appended after the title,
    # e.g. "Deep In (Chinese Drama). DramaKey is the home of all Asian..."
    t = re.sub(r'\.\s*(?:DramaKey|TheNkiri|Nkiri)\b.*$', '', t, flags=re.IGNORECASE).strip()
    # Remove " | Download ..." suffix
    t = re.sub(r'\s*\|\s*Download.*$', '', t, flags=re.IGNORECASE).strip()
    # Remove " | Korean Drama / Hollywood Movie / TV Series" etc.
    t = re.sub(
        rf'\s*\|\s*(?:{_TYPE_TAGS}).*$',
        '', t, flags=re.IGNORECASE
    ).strip()
    # Remove trailing genre/type parenthetical tags, e.g. "(Chinese Drama)", "(Hollywood Movie)"
    t = re.sub(
        r'\s*\((?:Korean|Chinese|Japanese|Thai|Filipino|Hollywood|Nollywood|'
        r'Asian|Bollywood)?\s*(?:Drama|Movie|TV\s*Series)\)\s*$',
        '', t, flags=re.IGNORECASE
    ).strip()
    # Remove " - TheNkiri.com / Dramakey" trailing branding
    t = re.sub(r'\s*[-–]\s*(TheNkiri|Nkiri|Dramakey).*$', '', t, flags=re.IGNORECASE).strip()

    if mode == "movie":
        seq_match = re.match(r'^(.*\S)\s+(\d{1,2})\s*(?:\((?:19|20)\d{2}\)\s*)?$', t)
        if seq_match:
            t = f"{seq_match.group(1).strip()} part {seq_match.group(2)}"
        return re.sub(r'\s+', ' ', t).strip()

    t = re.sub(r'\s*\(\s*(?:19|20)\d{2}\s*\)', '', t)
    t = re.sub(r'\s*\(\s*(?:Complete|Completed|Added|Ongoing)\s*\)', '', t, flags=re.IGNORECASE)
    # Strip "(Episode N Added)" / "(Episode N)" status parentheticals
    t = re.sub(r'\s*\(\s*Episode\s+\d+\s*(?:Added|Ongoing|Complete|Completed)?\s*\)', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+Season\s+\d+.*$', '', t, flags=re.IGNORECASE)
    # Strip "S01" / "S1" style season abbreviations
    t = re.sub(r'\s+S\d{1,2}\b.*$', '', t, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', t).strip()


def _get_title_raw(soup: BeautifulSoup) -> str:
    """Returns the raw, un-normalized title text so mode-specific
    normalization can be applied once the mode (movie/series) is known."""
    try:
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            return og["content"]
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)
    except Exception:
        pass
    return ""


def _get_poster(soup: BeautifulSoup) -> str:
    try:
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            raw = og["content"]
            if "728x90" not in raw:
                return raw
        img = soup.find("img", class_=re.compile(r"wp-post-image|featured|attachment-post", re.I))
        if img and img.get("src") and "728x90" not in img["src"]:
            return img["src"]
        entry = _get_entry(soup)
        if entry:
            for img in entry.find_all("img", src=True):
                src = img["src"]
                if "728x90" not in src and "banner" not in src.lower():
                    return src
    except Exception:
        pass
    return ""


def _get_trailer(soup: BeautifulSoup) -> str:
    try:
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "") or iframe.get("data-src", "")
            if "youtube" in src or "youtu.be" in src:
                return Normalizer.normalize_youtube(src)

        # Elementor video widgets embed the YouTube URL inside a data-settings
        # JSON attribute rather than a plain <iframe src="...">, e.g.:
        # <div class="elementor-widget-video" data-settings="{&quot;youtube_url&quot;:&quot;https:\/\/youtu.be\/XXX&quot;,...}">
        for widget in soup.find_all(class_=re.compile(r"elementor-widget-video", re.I)):
            settings_raw = widget.get("data-settings", "")
            if not settings_raw:
                continue
            m = re.search(r'"youtube_url"\s*:\s*"([^"]+)"', settings_raw)
            if m:
                youtube_url = m.group(1).replace("\\/", "/")
                if youtube_url:
                    return Normalizer.normalize_youtube(youtube_url)
    except Exception:
        pass
    return ""


def _is_spam_text(text: str) -> bool:
    """Detect SEO spam / garbled filler text inserted by nkiri/dramakey."""
    if not text:
        return True
    words = text.split()
    if not words:
        return True
    # Run-together words have very high average word length (e.g. "Iam", "buyinga")
    avg_len = sum(len(w) for w in words) / len(words)
    if avg_len > 6.5:
        return True
    # CamelCase without space is a dead giveaway: "Iam", "Ihave", "buyinga"
    if re.search(r'[a-z][A-Z]', text):
        return True
    # Transition-word padding blocks
    if re.search(r'transition\s*words|above\s*all.*therefore|for\s*instance.*however', text, re.IGNORECASE):
        return True
    return False


def _get_synopsis(soup: BeautifulSoup) -> str:
    """
    Find real synopsis. Nkiri/Dramakey inject SEO spam under the Synopsis heading —
    we scan ALL paragraphs and return the first non-spam one that looks like prose.
    """
    try:
        entry = _get_entry(soup)
        if not entry:
            return ""
        for p in entry.find_all("p"):
            text = p.get_text(strip=True)
            if len(text) < 40:
                continue
            if NOISE_TEXTS.search(text):
                continue
            if re.match(r'^(Status|Season|Episode|Download|Size|These videos|'
                        r'Nkiri|Dramakey|Join Us)', text, re.IGNORECASE):
                continue
            if _is_spam_text(text):
                continue
            return Normalizer.normalize_synopsis(text)
    except Exception:
        pass
    return ""


def _get_status(soup: BeautifulSoup) -> str:
    try:
        text = soup.get_text()
        m = re.search(r'Status\s*:?\s*(Ongoing|Completed?|Airing)', text, re.IGNORECASE)
        if m:
            return Normalizer.normalize_status(m.group(1))
    except Exception:
        pass
    return ""


def _get_download_size(soup: BeautifulSoup) -> str:
    try:
        text = soup.get_text()
        m = re.search(r'(?:videos?\s+are\s+around|size\s*:?)\s*([\d.,]+\s*(?:MB|GB))', text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        m2 = re.search(r'\b(\d{2,4}\s*(?:MB|GB))\b', text, re.IGNORECASE)
        if m2:
            return m2.group(1).strip()
    except Exception:
        pass
    return ""


def _get_season(title: str, soup: BeautifulSoup) -> str:
    m = re.search(r'Season\s*(\d+)', title, re.IGNORECASE)
    if m:
        return m.group(1)
    text = soup.get_text()
    m2 = re.search(r'Season\s*(\d+)', text, re.IGNORECASE)
    return m2.group(1) if m2 else ""


def _is_valid_dl(href: str) -> bool:
    return bool(href and VALID_DOWNLOAD_DOMAIN in href)


def _get_movie_links(soup: BeautifulSoup) -> list:
    links = []
    seen = set()
    try:
        entry = _get_entry(soup)
        if not entry:
            entry = soup
        for a in entry.find_all("a", href=True):
            href = a.get("href", "").strip()
            text = a.get_text(strip=True)
            if not _is_valid_dl(href):
                continue
            if NOISE_TEXTS.search(text):
                continue
            if href in seen:
                continue
            seen.add(href)
            quality = re.search(r'(\d{3,4}p)', text)
            links.append({
                "quality": quality.group(1) if quality else (text or "Download"),
                "link": href
            })
    except Exception:
        pass
    return links


def _ep_num_from_href(href: str) -> int | None:
    """Try to extract episode number from the download URL filename."""
    # S01E12, E12, Ep12, Episode.12
    for pat in [r'[Ss]\d+[Ee](\d+)', r'[Ee]p(?:isode)?[._\s-]?(\d+)']:
        m = re.search(pat, href)
        if m:
            return int(m.group(1))
    return None


def _get_episodes(soup: BeautifulSoup) -> list:
    """
    Collect all downloadwella.com links in order.
    Nkiri/Dramakey use Elementor buttons — episode numbers are NOT in the DOM text,
    so we extract them from the href filename (SxxExx pattern) or assign sequentially.
    """
    episodes = []
    seen_hrefs = set()

    try:
        entry = _get_entry(soup)
        if not entry:
            entry = soup

        # Collect all downloadwella links in document order
        raw_links = []
        for a in entry.find_all("a", href=True):
            href = a.get("href", "").strip()
            if not _is_valid_dl(href):
                continue
            text = a.get_text(strip=True)
            if NOISE_TEXTS.search(text):
                continue
            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)
            raw_links.append(href)

        # Try to assign episode numbers from href, fall back to sequential
        for i, href in enumerate(raw_links, start=1):
            ep_num = _ep_num_from_href(href)
            if ep_num is None:
                ep_num = i
            episodes.append({"episode": ep_num, "title": f"Episode {ep_num}", "url": href})

        # Sort by episode number and deduplicate
        episodes.sort(key=lambda e: e["episode"])
        seen_nums = set()
        deduped = []
        for ep in episodes:
            if ep["episode"] not in seen_nums:
                seen_nums.add(ep["episode"])
                deduped.append(ep)
        episodes = deduped

    except Exception:
        pass

    return episodes


def _get_meta_fields(soup: BeautifulSoup) -> dict:
    meta = {}
    try:
        text = soup.get_text(separator="\n")
        patterns = {
            "_awpt_language":     r"Language\s*:\s*(.+)",
            "_awpt_country":      r"Country\s*:\s*(.+)",
            "_awpt_genre":        r"Genre\s*:\s*(.+)",
            "_awpt_release_date": r"(?:Year|Release)\s*:\s*(.+)",
            "_awpt_stars":        r"(?:Stars?|Cast)\s*:\s*(.+)",
            "_awpt_ratings":      r"Ratings?\s*:\s*(.+)",
            "_awpt_subtitles":    r"Subtitle\s*:\s*(.+)",
        }
        for key, pattern in patterns.items():
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                val = m.group(1).strip().split("\n")[0].strip()
                meta[key] = val
    except Exception:
        pass
    return meta


def scrape(url: str, mode: str, site: str = "") -> dict:
    try:
        soup = _fetch_soup(url)
        if not soup:
            return {"error": "DOWNLOAD RESOLUTION FAILED"}

        source        = _identify_site(url, site)
        title_raw     = _get_title_raw(soup)
        synopsis      = _get_synopsis(soup)
        poster        = _get_poster(soup)
        trailer       = _get_trailer(soup)
        status        = _get_status(soup)
        download_size = _get_download_size(soup)
        season        = _get_season(title_raw, soup)
        meta          = _get_meta_fields(soup)

        if mode == "movie":
            download_links = _get_movie_links(soup)
            if not download_links:
                return {"error": "DOWNLOAD RESOLUTION FAILED"}

            title = _clean_nkiri_title(title_raw, mode="movie")
            result = {
                "_awpt_type":          "movie",
                "_awpt_title":         title,
                "_awpt_synopsis":      synopsis,
                "_awpt_poster":        poster,
                "_awpt_trailer_url":   trailer,
                "_awpt_genre":         Normalizer.normalize_genre(meta.get("_awpt_genre", "")),
                "_awpt_stars":         meta.get("_awpt_stars", ""),
                "_awpt_release_date":  Normalizer.normalize_year(meta.get("_awpt_release_date", "")),
                "_awpt_country":       meta.get("_awpt_country", ""),
                "_awpt_ratings":       meta.get("_awpt_ratings", ""),
                "_awpt_language":      meta.get("_awpt_language", ""),
                "_awpt_subtitles":     meta.get("_awpt_subtitles", ""),
                "_awpt_source":        source,
                "_awpt_file_size":     download_size,
                "_awpt_status":        "Movie",
                "_awpt_download_link": download_links,
                "_awpt_additional_info": {},
            }
        else:
            episodes = _get_episodes(soup)
            if not episodes:
                return {"error": "DOWNLOAD RESOLUTION FAILED"}

            title = _clean_nkiri_title(title_raw, mode="series")
            result = {
                "_awpt_type":           "series",
                "_awpt_title":          title,
                "_awpt_synopsis":       synopsis,
                "_awpt_poster":         poster,
                "_awpt_trailer_url":    trailer,
                "_awpt_genre":          Normalizer.normalize_genre(meta.get("_awpt_genre", "")),
                "_awpt_stars":          meta.get("_awpt_stars", ""),
                "_awpt_release_date":   Normalizer.normalize_year(meta.get("_awpt_release_date", "")),
                "_awpt_country":        meta.get("_awpt_country", ""),
                "_awpt_ratings":        meta.get("_awpt_ratings", ""),
                "_awpt_language":       meta.get("_awpt_language", ""),
                "_awpt_subtitles":      meta.get("_awpt_subtitles", ""),
                "_awpt_source":         source,
                "_awpt_total_episodes": str(len(episodes)),
                "_awpt_file_size":      download_size,
                "_awpt_status":         status or "Added",
                "_awpt_season":         season,
                "_awpt_episodes":       episodes,
                "_awpt_additional_info": {},
            }

        final = Normalizer.remove_empty_fields(result)
        final["_awpt_trailer_url"] = final.get("_awpt_trailer_url", "")
        return final

    except Exception:
        return {"error": "DOWNLOAD RESOLUTION FAILED"}
