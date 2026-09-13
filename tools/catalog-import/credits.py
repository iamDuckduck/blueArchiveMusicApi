"""Structured draft credits, including conversion of the first version's text fields."""

import re


CREDIT_FIELDS = {"group", "composer", "performers"}


def credit_entries(field, value):
    if isinstance(value, str):
        if len(value) > 20000:
            raise ValueError("Credit text must be up to 20,000 characters.")
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        if field != "performers":
            return lines
        entries = []
        for line in lines:
            match = re.fullmatch(r"(.*?)\s*[（(]\s*CV\s*[.:：]?\s*([^()（）]*)[）)]", line, re.I)
            entries.append({"character": match[1].strip() if match else line,
                            "voice_actor": match[2].strip() if match else ""})
        return entries
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError("Credits must be a list of up to 100 entries.")
    result = []
    for entry in value:
        if field == "performers":
            if not isinstance(entry, dict) or set(entry) != {"character", "voice_actor"}:
                raise ValueError("Each participant needs character and voice actor fields.")
            if any(not isinstance(v, str) or len(v) > 20000 for v in entry.values()):
                raise ValueError("Credit names must be text, up to 20,000 characters.")
            entry = {key: text.strip() for key, text in entry.items()}
            if any(entry.values()):
                result.append(entry)
        else:
            if not isinstance(entry, str) or len(entry) > 20000:
                raise ValueError("Credit names must be text, up to 20,000 characters.")
            if entry.strip():
                result.append(entry.strip())
    return result
