import os
import argparse

from lib.FileExtractor import FileExtractor
from lib.FileDownloader import FileDownloader
from lib.ApkProviderFetcher import (
    get_apk_url,
    extract_apk_download_url,
    check_apk,
    needs_catalog_update,
    update_api_data
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download & extract Blue Archive Android Data"
    )
    parser.add_argument(
        "--client",
        choices=["global", "jp"],
        default="jp",
        help="Which game client to download (default: jp)",
    )
    parser.add_argument(
        "--url",
        required=False,
        default=None,
        help="Download URL (default: None)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force download even if version is up to date",
    )
    args = parser.parse_args()

    client = args.client

    download_dir = os.path.join(os.getcwd(), 'apk_downloads')
    extract_dir = os.path.join(os.getcwd(), f'{client}_extracted')

    if client == "global":
        pkg = "com.nexon.bluearchive"
    else:
        pkg = "com.YostarJP.BlueArchive"

    if args.url is not None:
        xapk_url = args.url
    else:
        xapk_url = extract_apk_download_url(pkg)
        if xapk_url is None:
            print("Falling back to APKPure/APKCombo scraper...")
            xapk_url = get_apk_url(pkg)

    print(f"Checking {client} version...")
    if not args.force and not needs_catalog_update(pkg, client):
        print(f"{client} is up to date. Use --force to force download.")
        exit(0)

    print(f"Downloading {client} Data...")
    apk_filename = f"{pkg}.xapk"
    downloader = FileDownloader(xapk_url, download_dir, apk_filename)
    downloader.download()

    local_path = os.path.join(download_dir, apk_filename)
    if check_apk(xapk_url, local_path):
        print("APK downloaded but size mismatch, retrying...")
        downloader = FileDownloader(xapk_url, download_dir, apk_filename)
        downloader.download()

    FileExtractor(downloader.local_filepath, extract_dir, client).extract_xapk()
    update_api_data(pkg, client)

    print("Successfully downloaded and extracted files")
