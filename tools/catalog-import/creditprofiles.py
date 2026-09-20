"""Small authenticated bridge to existing backend credit profiles; no local cache."""

from urllib.parse import urlparse

import requests


class CreditProfiles:
    def __init__(self, backend_url, api_key):
        parsed = urlparse(backend_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None or parsed.query or parsed.fragment:
            raise ValueError("Configure an HTTP(S) backend URL without embedded credentials, query, or fragment.")
        self.backend_url = backend_url.rstrip("/")
        self.api_key = api_key

    def _request(self, method, path, **kwargs):
        if not self.api_key:
            raise ValueError("Configure the development backend and import API key to manage credit aliases.")
        try:
            response = requests.request(method, self.backend_url + path,
                                        headers={"X-Admin-Api-Key": self.api_key},
                                        timeout=(5, 20), allow_redirects=False, **kwargs)
        except requests.RequestException:
            raise ValueError("The configured backend could not be reached. Your alias edits are not confirmed saved; check the profile before retrying.") from None
        if response.status_code in {401, 403}:
            raise ValueError("The backend refused access. Check the configured import API key.")
        if response.status_code == 404:
            raise ValueError("That credit profile was not found. Search the published catalog again.")
        if not 200 <= response.status_code < 300:
            raise ValueError(f"The backend did not accept this request ({response.status_code}). Check the profile and alias limits before retrying.")
        try:
            return response.json()
        except ValueError:
            raise ValueError("The backend returned an invalid credit profile response.") from None

    @staticmethod
    def _profile(value):
        if (not isinstance(value, dict) or type(value.get("id")) is not int or value["id"] < 1
                or not isinstance(value.get("name"), str) or not value["name"].strip()
                or not isinstance(value.get("aliases"), list)
                or any(not isinstance(alias, str) for alias in value["aliases"])
                or any(value.get(field) is not None and not isinstance(value[field], str)
                       for field in ["characterName", "voiceActorName"])):
            raise ValueError("The backend returned an invalid credit profile. Update the backend before using this page.")
        return {field: value.get(field) for field in ["id", "name", "characterName", "voiceActorName", "aliases"]}

    @staticmethod
    def _identity(artist_id):
        if type(artist_id) is not int or artist_id < 1:
            raise ValueError("Choose an existing credit profile.")
        return artist_id

    def search(self, query):
        if not isinstance(query, str) or len(query) > 255:
            raise ValueError("Search names using up to 255 characters.")
        rows = self._request("GET", "/admin/artist", params={"query": query.strip()})
        if not isinstance(rows, list) or len(rows) > 50:
            raise ValueError("The backend returned an invalid credit search response.")
        return [self._profile(row) for row in rows]

    def get(self, artist_id):
        identity = self._identity(artist_id)
        profile = self._profile(self._request("GET", f"/admin/artist/{identity}"))
        if profile["id"] != identity:
            raise ValueError("The backend returned a different credit profile. Nothing was changed locally.")
        return profile

    def save_aliases(self, artist_id, aliases):
        identity = self._identity(artist_id)
        if (not isinstance(aliases, list) or len(aliases) > 20
                or any(not isinstance(alias, str) or not alias.strip() or len(alias) > 255
                       or "\n" in alias or "\r" in alias for alias in aliases)):
            raise ValueError("Use at most 20 aliases, one non-empty name per line, up to 255 characters each.")
        profile = self._profile(self._request("PUT", f"/admin/artist/{identity}/aliases",
                                             json={"aliases": [alias.strip() for alias in aliases]}))
        if profile["id"] != identity:
            raise ValueError("The backend returned a different credit profile. Check the intended profile before retrying.")
        return profile
