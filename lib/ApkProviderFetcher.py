import os
import re
import json
import cloudscraper
import urllib.parse

APKPURE_URL = "https://apkpure.com/blue-archive/{pkg}/download"
APKPURE_VER_PATTERN = r'property="og:title" content="Download [^"]+ ([\d\.]+)'
APKPURE_PKG_PATTERN = r'<link rel="canonical" href="https://apkpure\.com/[^/]+/([^/]+)/download"'

APKCOMBO_URL = "https://apkcombo.com/{app_name}/{pkg}/download/apk"
APKCOMBO_VER_PATTERN = r'Version:\s*([\d\.]+)'
APKCOMBO_CDN_PATTERN = r'https%3A%2F%2Fapks\.[^.]+\.r2\.cloudflarestorage\.com%2F[^&"]+'

JAPAN_VERSION_URL = "https://api.pureapk.com/m/v3/cms/app_version?hl=en-US&package_name=com.YostarJP.BlueArchive"
GLOBAL_VERSION_URL = "https://api.pureapk.com/m/v3/cms/app_version?hl=en-US&package_name=com.nexon.bluearchive"
PLAYSTORE_VERSION_URL = "https://apptopia.com/google-play/app/com.nexon.bluearchive/about"

REGEX_VERSION = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)')
PLAYSTORE_REGEX_VERSION = re.compile(r'\d+\.\d+\.\d+')

JAPAN_REGEX_URL = re.compile(
    r'(X?APKJ)..(https?://(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*))'
)

APK_HEADERS = {
    'x-cv': '3172501',
    'x-sv': '29',
    'x-abis': 'arm64-v8a,armeabi-v7a,armeabi',
    'x-gp': '1'
}

API_DATA_FILE = 'api_data.json'


def get_version(pkg: str, region: str = "jp") -> str | None:
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )

    if region == "global":
        url = PLAYSTORE_VERSION_URL
        regex = PLAYSTORE_REGEX_VERSION
    else:
        url = JAPAN_VERSION_URL
        regex = REGEX_VERSION

    try:
        response = scraper.get(url, headers=APK_HEADERS, timeout=10)
        response.raise_for_status()
        body = response.text

        match = regex.search(body)
        if match:
            return match.group(0)
        return None
    except Exception:
        return None


def extract_apk_download_url(pkg: str) -> str | None:
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )

    version_url = JAPAN_VERSION_URL if pkg == "com.YostarJP.BlueArchive" else GLOBAL_VERSION_URL

    try:
        response = scraper.get(version_url, headers=APK_HEADERS, timeout=10)
        response.raise_for_status()
        body = response.text

        match = JAPAN_REGEX_URL.search(body)
        if match and match.lastindex and match.lastindex >= 2:
            return match.group(2)
        return None
    except Exception:
        return None


def check_apk(url: str, apk_path: str) -> bool:
    if not os.path.exists(apk_path):
        return True

    local_size = os.path.getsize(apk_path)

    scraper = cloudscraper.create_scraper()
    try:
        response = scraper.get(
            url,
            headers={**APK_HEADERS, 'Range': 'bytes=0-0'},
            timeout=10
        )

        content_length = response.headers.get('content-length')
        content_range = response.headers.get('Content-Range', '')

        if content_range:
            parts = content_range.split('/')
            if len(parts) >= 2:
                try:
                    remote_size = int(parts[-1])
                    return remote_size == 0 or local_size != remote_size
                except ValueError:
                    pass

        if content_length:
            try:
                remote_size = int(content_length)
                return local_size != remote_size
            except ValueError:
                pass

        return True
    except Exception:
        return True


def load_api_data() -> dict:
    if os.path.exists(API_DATA_FILE):
        with open(API_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "japan": {"version": "", "platform": "Android"},
        "global": {"version": "", "platform": "Android", "build_type": "Standard"}
    }


def save_api_data(data: dict):
    with open(API_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def needs_catalog_update(pkg: str, region: str, platform: str = "Android", build_type: str = "Standard") -> bool:
    api_data = load_api_data()

    if region not in api_data:
        return True

    cached = api_data[region]
    cached_version = cached.get("version", "")
    cached_platform = cached.get("platform", "Android")
    cached_build_type = cached.get("build_type", "Standard")

    current_version = get_version(pkg, region)

    if current_version is None:
        return False

    if current_version != cached_version:
        print(f"Version changed: {cached_version} -> {current_version}")
        return True

    if platform != cached_platform:
        print(f"Platform changed: {cached_platform} -> {platform}")
        return True

    if region == "global" and build_type != cached_build_type:
        print(f"Build type changed: {cached_build_type} -> {build_type}")
        return True

    print(f"Version {current_version} is up to date")
    return False


def update_api_data(pkg: str, region: str, platform: str = "Android", build_type: str = "Standard") -> str | None:
    version = get_version(pkg, region)
    if version is None:
        return None

    api_data = load_api_data()
    entry = {"version": version, "platform": platform}
    if region == "global":
        entry["build_type"] = build_type

    api_data[region] = entry
    save_api_data(api_data)
    return version


def get_apk_url(pkg: str):
    (apk_pure_version, apk_pure_cdn_url) = get_apkpure_url(pkg)
    (apk_combo_version, apk_combo_cdn_url) = get_apkcombo_url(pkg)

    pure_build = parse_ver(apk_pure_version)
    combo_build = parse_ver(apk_combo_version)

    if pure_build == 0 and combo_build == 0:
        raise ValueError("Critical Error: Could not detect version builds from either source.")

    if pure_build > combo_build and apk_pure_cdn_url:
        return apk_pure_cdn_url

    if apk_combo_cdn_url:
        return apk_combo_cdn_url

    if apk_pure_cdn_url:
        return apk_pure_cdn_url

    raise ValueError(f"Could not retrieve a valid CDN URL for package: {pkg}")


def get_apkpure_url(pkg: str) -> tuple[str | None, str | None]:
    url = APKPURE_URL.format(pkg=pkg)
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    headers = {
        'Referer': f'https://apkpure.com/blue-archive/com.YostarJP.BlueArchive/download',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    try:
        response = scraper.get(url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()
        file_content = response.text

        version_match = re.search(APKPURE_VER_PATTERN, file_content)
        package_match = re.search(APKPURE_PKG_PATTERN, file_content)

        version: str | None = version_match.group(1) if version_match else None
        package = package_match.group(1) if package_match else None

        cdn_url = f"https://d.apkpure.com/b/XAPK/{package}?version=latest" if package else None

        return version, cdn_url
    except Exception:
        return None, None


def get_apkcombo_url(pkg: str) -> tuple[str | None, str | None]:
    app_name = "blue-archive-jp" if pkg == "com.YostarJP.BlueArchive" else "blue-archive"
    url = APKCOMBO_URL.format(app_name=app_name, pkg=pkg)

    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    headers = {
        'Referer': f'https://apkcombo.com/{app_name}/{pkg}/',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    try:
        response = scraper.get(url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()
        file_content = response.text

        version_match = re.search(APKCOMBO_VER_PATTERN, file_content)
        cdn_match = re.search(APKCOMBO_CDN_PATTERN, file_content)

        version: str | None = version_match.group(1) if version_match else None
        raw_cdn = cdn_match.group(0) if cdn_match else None
        cdn_url = urllib.parse.unquote(raw_cdn) if raw_cdn else None

        return version, cdn_url
    except Exception:
        return None, None


def parse_ver(v):
    try:
        return int(v.split(".")[-1]) if v else 0
    except Exception:
        return 0
