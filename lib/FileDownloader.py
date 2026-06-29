import os
import cloudscraper
import shutil

from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

from lib.ApkProviderFetcher import APK_HEADERS


class FileDownloader:
    def __init__(self, url, download_dir, filename, extra_headers=None):
        self.url = url
        self.local_filepath = os.path.join(download_dir, filename)
        os.makedirs(download_dir, exist_ok=True)
        self.scraper = cloudscraper.create_scraper()
        self.headers = {**APK_HEADERS, **(extra_headers or {})}

        cpu_threads = os.cpu_count() or 1
        if cpu_threads >= 4:
            self.thread_count = cpu_threads // 2
        else:
            self.thread_count = cpu_threads

    def download(self):
        try:
            head = self.scraper.head(self.url, headers=self.headers, allow_redirects=True, timeout=10)
            total_size = int(head.headers.get('content-length', 0))
            accept_ranges = head.headers.get('Accept-Ranges', '').lower()

            if total_size > 0 and 'bytes' in accept_ranges:
                return self._multi_threaded_download(total_size)
            else:
                return self._standard_download()
        except Exception as e:
            print(f"Setup failed, falling back: {e}")
            return self._standard_download()

    def _standard_download(self):
        r = self.scraper.get(self.url, headers=self.headers, stream=True, allow_redirects=True)
        r.raise_for_status()
        total = int(r.headers.get('content-length', 0))

        with tqdm.wrapattr(r.raw, "read", total=total, desc="Standard") as stream:
            with open(self.local_filepath, 'wb') as f:
                shutil.copyfileobj(stream, f)
        return True

    def _multi_threaded_download(self, total_size):
        with open(self.local_filepath, 'wb') as f:
            f.truncate(total_size)

        chunk_size = total_size // self.thread_count
        ranges = []
        for i in range(self.thread_count):
            start = i * chunk_size
            end = (i + 1) * chunk_size - 1 if i < self.thread_count - 1 else total_size - 1
            ranges.append((start, end))

        with tqdm(total=total_size, unit='B', unit_scale=True, desc="Multi") as pbar:
            with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
                futures = [executor.submit(self._download_chunk, s, e, pbar) for s, e in ranges]
                for future in futures:
                    future.result()
        return True

    def _download_chunk(self, start, end, pbar):
        headers = {**self.headers, 'Range': f'bytes={start}-{end}'}
        resp = self.scraper.get(self.url, headers=headers, stream=True)
        with open(self.local_filepath, 'rb+') as f:
            f.seek(start)
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))
