import re
from urllib.parse import urlparse, parse_qs


class Normalizer:

    _TYPE_TAGS = (
        r'Korean|Chinese|Japanese|Thai|Filipino|Hollywood|Nollywood|'
        r'Asian|Bollywood|TV\s*Series|Drama|Movie'
    )

    @staticmethod
    def normalize_title(title: str, mode: str = "series") -> str:
        """Normalize a scraped title.

        mode="movie": keep "Title (Year)"; numbered sequels become "Title part N"
        (year is dropped for sequels since the number already disambiguates).
        mode="series": strip year/season/status suffixes entirely, leaving just
        the bare series title.
        """
        if not title:
            return ""
        title = title.strip()

        removals = [
            r'^DOWNLOAD\s+',
            r'\|\s*NaijaPrey.*$',
            r'\|\s*9jarocks.*$',
            r'\|\s*Nkiri.*$',
            r'\|\s*Dramakey.*$',
            r'\|\s*Download.*$',
            rf'\|\s*(?:{Normalizer._TYPE_TAGS}).*$',
            r'[-–]\s*NaijaPrey.*$',
            r'[-–]\s*9jarocks.*$',
            r'[-–]\s*(?:TheNkiri|Nkiri|Dramakey).*$',
            rf'[-–]\s*(?:{Normalizer._TYPE_TAGS}).*$',
            r'Download\s*$',
            r'Movie\s*Download\s*$',
            r'Series\s*Download\s*$',
            r'Free\s*Download\s*$',
        ]
        for pattern in removals:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE).strip()

        # Drop trailing site-description sentences appended after a genre tag,
        # e.g. "Deep In (Chinese Drama). DramaKey is the home of all Asian..."
        title = re.sub(r'\.\s*(?:DramaKey|TheNkiri|Nkiri|NaijaPrey|9jarocks)\b.*$', '', title, flags=re.IGNORECASE).strip()

        # Drop trailing genre/type parenthetical tags, e.g. "(Chinese Drama)", "(Hollywood Movie)"
        title = re.sub(
            r'\s*\((?:Korean|Chinese|Japanese|Thai|Filipino|Hollywood|Nollywood|'
            r'Asian|Bollywood)?\s*(?:Drama|Movie|TV\s*Series)\)\s*$',
            '', title, flags=re.IGNORECASE
        ).strip()

        if mode == "movie":
            # Numbered sequel: "Enola Holmes 3 (2026)" -> "Enola Holmes part 3"
            seq_match = re.match(
                r'^(.*\S)\s+(\d{1,2})\s*(?:\((?:19|20)\d{2}\)\s*)?$', title
            )
            if seq_match:
                base = seq_match.group(1).strip()
                num = seq_match.group(2)
                title = f"{base} part {num}"
            return re.sub(r'\s+', ' ', title).strip()

        # series: strip year and status parentheticals, then season suffix
        title = re.sub(r'\s*\(\s*(?:19|20)\d{2}\s*\)', '', title)
        title = re.sub(r'\s*\(\s*(?:Complete|Completed|Added|Ongoing)\s*\)', '', title, flags=re.IGNORECASE)
        # Strip "(Episode N Added)" / "(Episode N)" status parentheticals
        title = re.sub(r'\s*\(\s*Episode\s+\d+\s*(?:Added|Ongoing|Complete|Completed)?\s*\)', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s+Season\s+\d+.*$', '', title, flags=re.IGNORECASE)
        # Strip "S01" / "S1" style season abbreviations
        title = re.sub(r'\s+S\d{1,2}\b.*$', '', title, flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', title).strip()

    @staticmethod
    def normalize_year(year: str) -> str:
        if not year:
            return ""
        match = re.search(r'\b(19|20)\d{2}\b', str(year))
        return match.group(0) if match else year.strip()

    @staticmethod
    def normalize_genre(genre: str) -> str:
        if not genre:
            return ""
        parts = re.split(r'[,|/]', genre)
        parts = [p.strip() for p in parts if p.strip()]
        return ", ".join(parts)

    @staticmethod
    def normalize_language(lang: str) -> str:
        if not lang:
            return ""
        return lang.strip()

    @staticmethod
    def normalize_season(season: str) -> str:
        if not season:
            return ""
        match = re.search(r'(\d+)', str(season))
        return match.group(1) if match else season.strip()

    @staticmethod
    def normalize_episodes(episodes: list) -> list:
        if not episodes:
            return []
        seen = set()
        unique = []
        for ep in episodes:
            key = ep.get("episode", "")
            if key not in seen:
                seen.add(key)
                unique.append(ep)
        try:
            unique.sort(key=lambda e: int(re.search(r'\d+', str(e.get("episode", "0"))).group()))
        except Exception:
            pass
        return unique

    @staticmethod
    def normalize_status(text: str) -> str:
        if not text:
            return ""
        t = text.strip().lower()
        if "complet" in t:
            return "Completed"
        if "ongoing" in t or "airing" in t:
            return "Ongoing"
        if "added" in t:
            return "Added"
        return text.strip()

    @staticmethod
    def normalize_synopsis(text: str) -> str:
        if not text:
            return ""
        text = Normalizer.strip_html(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    @staticmethod
    def normalize_youtube(url: str) -> str:
        if not url:
            return ""
        try:
            patterns = [
                r'(?:youtube\.com/embed/|youtu\.be/|youtube\.com/watch\?v=)([A-Za-z0-9_\-]{11})',
                r'youtube\.com/v/([A-Za-z0-9_\-]{11})',
            ]
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return f"https://www.youtube.com/watch?v={match.group(1)}"
        except Exception:
            pass
        return ""

    @staticmethod
    def strip_html(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', ' ', str(text))
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&quot;', '"', text)
        text = re.sub(r'&#\d+;', '', text)
        return text.strip()

    @staticmethod
    def remove_empty_fields(data: dict) -> dict:
        if not isinstance(data, dict):
            return data
        result = {}
        for k, v in data.items():
            if v is None:
                continue
            if isinstance(v, str) and not v.strip():
                continue
            if isinstance(v, list):
                cleaned = []
                for item in v:
                    if isinstance(item, dict):
                        cleaned_item = Normalizer.remove_empty_fields(item)
                        if cleaned_item:
                            cleaned.append(cleaned_item)
                    elif item is not None and str(item).strip():
                        cleaned.append(item)
                if cleaned:
                    result[k] = cleaned
            elif isinstance(v, dict):
                cleaned = Normalizer.remove_empty_fields(v)
                if cleaned:
                    result[k] = cleaned
            else:
                result[k] = v
        return result
