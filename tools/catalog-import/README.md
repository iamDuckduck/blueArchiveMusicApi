# Local catalog import

Requires Python 3.11+. Install dependencies with `python -m pip install -r requirements.txt`.

This chapter reads Kivo details for supplied track IDs and suggests explicitly supported credits. GameKee failures remain visible. The Veritas fixtures demonstrate source interpretation. Album scanning, media preparation, browser review and publication arrive in later chapters.

Run `python -m unittest discover -s tests -v` from this directory.

## Local media preparation

FFmpeg/FFprobe must be on PATH. `media.py` downloads files from reviewed Kivo URLs, validates the full audio stream, reads embedded tags and retains original covers plus 400/800 px copies. Valid cached files are reused. The browser workflow is introduced next.
