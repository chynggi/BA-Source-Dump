import requests

from requests_cache import CachedSession
from typing import Dict, Any
from lib.ApkProviderFetcher import get_version

API_URL = "https://api-pub.nexon.com/patch/v1.1/version-check"

def get_game_version() -> str:
    version = get_version("com.nexon.bluearchive", "global")
    if not version:
        raise ValueError("Could not find game version")
    return version

def catalog_url() -> Dict[str, Any]:
    version = get_game_version()
    build_number = version.split('.')[-1]

    with CachedSession('nexonapi', use_temp=True) as session:
        response = session.post(
            API_URL,
            json={
                "market_game_id": "com.nexon.bluearchive",
                "market_code": "playstore",
                "curr_build_version": version,
                "curr_build_number": build_number
            }
        )
        data = response.json()
        return data