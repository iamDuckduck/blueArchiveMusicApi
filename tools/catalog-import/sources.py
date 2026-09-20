"""Read source evidence; source failures and uncertain credits remain visible."""

import json
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
    if not isinstance(value, str):
        raise ValueError("Expected a source URL string.")
    return "https:" + value if value.startswith("//") else value


def kivo_media_url(value):
    url = absolute_url(value)
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname != "static.kivo.wiki" or parsed.username
            or parsed.port not in {None, 443}):
        raise ValueError("Expected a public HTTPS file on static.kivo.wiki.")
    return url


def source_json(url, headers, timeout):
    # A source redirect must not silently change the host being read.
    response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
    response.raise_for_status()
    if 300 <= response.status_code < 400:
        raise ValueError("The source redirected the request. Open its reference manually.")
    return response.json()


def fetch_kivo(track_id):
    if type(track_id) is not int or track_id < 1:
        raise ValueError("Choose a positive Kivo track ID.")
    payload = source_json(KIVO_API.format(track_id), HEADERS, (10, 30))
    if not isinstance(payload, dict):
        raise ValueError("Kivo returned an unexpected record.")
    data = payload.get("data")
    if (payload.get("success") is not True or not isinstance(data, dict)
            or type(data.get("id")) is not int or data["id"] != track_id):
        raise ValueError("Kivo returned an unexpected record.")
    if not isinstance(data.get("title"), str) or not data["title"].strip():
        raise ValueError("Kivo returned a record without a title.")
    for field in ("introduction", "author", "album", "cover", "file"):
        if data.get(field) is not None and not isinstance(data[field], str):
            raise ValueError(f"Kivo returned an invalid {field} field.")
    return data


def cv_names(text):
    if not isinstance(text, str) or not re.search(r"[（(]\s*CV", text, re.I):
        return ""
    # Keep one language block rather than treating translated names as new performers.
    blocks = re.findall(r"[《〈]([^》〉]+)[》〉]", text)
    for block in blocks or [text]:
        matches = re.findall(r"([^、,;\n()（）]+)[（(]\s*CV\s*[.:：]?\s*([^()（）]+)[）)]", block, re.I)
        if matches:
            return "\n".join(dict.fromkeys(f"{name.strip()} (CV: {actor.strip()})" for name, actor in matches))
    return ""


def suggestions_from_kivo(data):
    result = {"title": data["title"]}
    introduction = content_text(data.get("introduction") or "")
    performers = cv_names(introduction)
    if performers:
        result["performers"] = performers
    # A generic author stays in evidence. Only an explicit role label suggests composer.
    composers = [value.strip() for value in re.findall(
        r"(?m)^[ \t]*(?:作曲|Composer)[ \t]*[:：][ \t]*([^\n]+)$", introduction, re.I) if value.strip()]
    if composers:
        result["composer"] = "\n".join(dict.fromkeys(composers))
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
            if self.parts and self.parts[-1] != "\n":
                self.parts.append("\n")
        elif tag in {"td", "th"}:
            self.parts.append("\t")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        elif tag in {"p", "div", "tr", "li"} and self.parts and self.parts[-1] != "\n":
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def content_text(value):
    if isinstance(value, str):
        # GameKee may serialize its editor document inside content_json.
        if value.lstrip().startswith(("{", "[")):
            try:
                decoded = json.loads(value)
                if isinstance(decoded, (dict, list)):
                    return content_text(decoded)
            except ValueError:
                pass
        parser = PlainText()
        parser.feed(value)
        return unescape("".join(parser.parts)).strip()
    if isinstance(value, dict):
        return "\n".join(filter(None, (content_text(value[k]) for k in ("content", "content_json", "text", "children", "ops", "insert") if k in value)))
    if isinstance(value, list):
        return "\n".join(filter(None, map(content_text, value)))
    return ""


def gamekee_evidence(text):
    """Label explicit article lines for human comparison, never automatic edits.

    Combined/ambiguous labels such as 作词/作曲 are intentionally not assigned a
    role. Dates remain source text, not inferred release dates for every track.
    """
    evidence = {"credits": [], "performers": cv_names(text), "release_dates": []}
    roles = {"composer": r"作曲|Composer", "artist": r"演唱|歌唱|Vocals?|Artists?"}
    for line in text.splitlines():
        line = line.strip()
        for role, labels in roles.items():
            match = re.fullmatch(rf"(?:{labels})[ ]*(?:[:：]|\t)[ \t]*(\S.*)", line, re.I)
            if match:
                item = {"role": role, "value": match.group(1).strip(), "line": line}
                if item not in evidence["credits"]:
                    evidence["credits"].append(item)
        match = re.fullmatch(r"(?:发行日期|發行日期|発売日|Release date)[ ]*(?:[:：]|\t)[ \t]*(\S.*)", line, re.I)
        if match:
            item = {"value": match.group(1).strip(), "line": line}
            if item not in evidence["release_dates"]:
                evidence["release_dates"].append(item)
    return evidence


def fetch_gamekee(page_url=GAMEKEE_PAGE):
    result = {"url": page_url, "checked_at": now(), "status": "failed", "text": "", "error": ""}
    if page_url == "":
        result.update(status="missing_reference", error="No GameKee reference selected. Add a matching article only if one is known.")
        return result
    try:
        match = re.fullmatch(r"https://www\.gamekee\.com/ba/([1-9]\d*)\.html", page_url) if isinstance(page_url, str) else None
        if not match:
            raise ValueError("Choose this release's GameKee reference (https://www.gamekee.com/ba/<id>.html). No default match is assumed.")
        payload = source_json("https://www.gamekee.com/v1/content/detail/" + match.group(1),
                              HEADERS | {"game-alias": "ba", "Lang": "zh-cn", "X-Requested-With": "XMLHttpRequest"}, (10, 20))
        if (not isinstance(payload, dict) or type(payload.get("code")) is not int
                or payload["code"] != 0 or not isinstance(payload.get("data"), dict)):
            raise ValueError("GameKee returned an unexpected article response.")
        data = payload["data"]
        game = data.get("game") or {}
        if (type(data.get("id")) is not int or data["id"] != int(match.group(1))
                or not isinstance(data.get("title"), str) or not data["title"].strip()
                or not isinstance(game, dict) or game.get("alias", "ba") != "ba"):
            raise ValueError("GameKee returned an article that does not match the selected reference.")
        result["raw"] = data
        result["article"] = {"id": data["id"], "title": data["title"], "updated_at": data.get("updated_at")}
        # The API summary is often truncated and collapses adjacent role labels.
        # Retain it separately even on CDN failure; never treat it as full content.
        result["summary"] = content_text(data.get("summary"))[:10000]
        text = content_text(data.get("content") or data.get("content_json"))
        if not text and data.get("content_cdn"):
            url = absolute_url(data["content_cdn"])
            parsed = urlparse(url)
            if (parsed.scheme != "https" or parsed.hostname != "api-cdn.gamekee.com"
                    or parsed.username or parsed.port not in {None, 443}):
                raise ValueError("GameKee returned an unexpected content host.")
            content = source_json(url, HEADERS, (10, 20))
            result["content_raw"] = content
            text = content_text(content)
        if not text:
            raise ValueError("The article response has no readable content. Open the source to review it manually.")
        result.update(status="ready", text=text[:80000], truncated=len(text) > 80000,
                      evidence=gamekee_evidence(text[:80000]), error="")
    except (requests.RequestException, ValueError) as error:
        result["error"] = str(error)
    return result
