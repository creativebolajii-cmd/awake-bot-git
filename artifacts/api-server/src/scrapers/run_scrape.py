import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.ninejarocks import scrape as scrape_ninejarocks  # noqa: E402
from scrapers.naijaprey import scrape as scrape_naijaprey  # noqa: E402
from scrapers.nkiri_dramakey import scrape as scrape_nkiri_dramakey  # noqa: E402


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        print(json.dumps({"error": "Invalid request payload"}))
        return

    source = (payload.get("source") or "").strip().lower()
    url = (payload.get("url") or "").strip()
    mode = (payload.get("mode") or "").strip().lower()
    site = (payload.get("site") or "").strip().lower()

    try:
        if source == "9jarocks":
            result = scrape_ninejarocks(url, mode)
        elif source == "naijaprey":
            result = scrape_naijaprey(url, mode)
        elif source == "nkiri-dramakey":
            result = scrape_nkiri_dramakey(url, mode, site)
        else:
            result = {"error": "Unknown source"}
    except Exception as exc:
        result = {"error": f"DOWNLOAD RESOLUTION FAILED: {exc}"}

    print(json.dumps(result))


if __name__ == "__main__":
    main()
