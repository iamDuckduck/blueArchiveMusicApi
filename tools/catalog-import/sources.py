"""Two source readers for the first album; failures remain visible to review."""

import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests

from store import now

KIVO_API = "https://api.kivo.wiki/api/v1/musics/{}"
GAMEKEE_PAGE = "https://www.gamekee.com/ba/691994.html"
HEADERS = {"User-Agent": "BlueArchiveCatalogReview/0.1 (local operator tool)"}


def absolute_url(value):
    return "https:" + value if value.startswith("//") else value


def kivo_media_url(value):
    url = absolute_url(value)
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "static.kivo.wiki" or parsed.username:
        raise ValueError("Expected a public HTTPS file on static.kivo.wiki.")
    return url


def fetch_kivo(track_id):
    response = requests.get(KIVO_API.format(track_id), headers=HEADERS, timeout=(10, 30))
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data")
    if payload.get("success") is not True or not isinstance(data, dict) or data.get("id") != track_id:
        raise ValueError("Kivo returned an unexpected record.")
    if not data.get("title"):
        raise ValueError("Kivo returned a record without a title.")
    return data


def cv_names(text):
    # Keep one language block rather than treating translated names as new performers.
    blocks = re.findall(r"[《〈]([^》〉]+)[》〉]", text)
    for block in blocks or [text]:
        matches = re.findall(r"([^、,;\n()（）]+)[（(]\s*CV\s*[.:：]?\s*([^()（）]+)[）)]", block, re.I)
        if matches:
            return "\n".join(dict.fromkeys(f"{name.strip()} (CV: {actor.strip()})" for name, actor in matches))
    return ""


def suggestions_from_kivo(data):
    result = {"title": data["title"]}
    introduction = data.get("introduction", "")
    performers = cv_names(introduction)
    if performers:
        result["performers"] = performers
    # A generic author stays in evidence. Only an explicit role label suggests composer.
    composer = re.search(r"(?m)^\s*(?:作曲|Composer)\s*[:：]\s*(.+)$", introduction, re.I)
    if composer:
        result["composer"] = composer.group(1).strip()
    return result


def suggestions_from_tags(tags):
    result = {}
    for source, field in [("title", "title"), ("composer", "composer")]:
        if tags.get(source):
            result[field] = tags[source]
    for source, field in [("track", "position"), ("disc", "disc")]:
        first = tags.get(source, "").split("/", 1)[0]
        if first.isdigit() and 1 <= int(first) <= 999:
            result[field] = int(first)
    credit = tags.get("album_artist", tags.get("artist", ""))
    performers = cv_names(credit)
    if performers:
        result["performers"] = performers
    if credit:
        # Keep the tag's artist/group label as a suggestion, not a composer inference.
        result["group"] = credit.split("《", 1)[0].strip()
    return result


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        elif tag in {"p", "div", "tr", "br", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def content_text(value):
    if isinstance(value, str):
        parser = PlainText()
        parser.feed(value)
        return unescape("".join(parser.parts)).strip()
    if isinstance(value, dict):
        return "\n".join(filter(None, (content_text(value[k]) for k in ("content", "text", "children", "ops", "insert") if k in value)))
    if isinstance(value, list):
        return "\n".join(filter(None, map(content_text, value)))
    return ""


def fetch_gamekee(page_url=GAMEKEE_PAGE):
    result = {"url": page_url, "checked_at": now(), "status": "failed", "text": ""}
    try:
        match = re.fullmatch(r"https://www\.gamekee\.com/ba/(\d+)\.html", page_url)
        if not match:
            raise ValueError("Choose this release's GameKee reference (https://www.gamekee.com/ba/<id>.html). No default match is assumed.")
        response = requests.get("https://www.gamekee.com/v1/content/detail/" + match.group(1),
                                headers=HEADERS | {"game-alias": "ba", "Lang": "zh-cn", "X-Requested-With": "XMLHttpRequest"},
                                timeout=(10, 20), allow_redirects=False)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0 or not isinstance(payload.get("data"), dict):
            raise ValueError("GameKee returned an unexpected article response.")
        data = payload["data"]
        result["raw"] = data
        text = content_text(data.get("content") or data.get("content_json"))
        if not text and data.get("content_cdn"):
            url = absolute_url(data["content_cdn"])
            if urlparse(url).scheme != "https" or urlparse(url).hostname != "api-cdn.gamekee.com":
                raise ValueError("GameKee returned an unexpected content host.")
            response = requests.get(url, headers=HEADERS, timeout=(10, 20))
            response.raise_for_status()
            content = response.json()
            result["content_raw"] = content
            text = content_text(content)
        if not text:
            raise ValueError("The article response has no readable content. Open the source to review it manually.")
        result.update(status="ready", text=text[:80000], error="")
    except (requests.RequestException, ValueError) as error:
        result["error"] = str(error)
    return result
