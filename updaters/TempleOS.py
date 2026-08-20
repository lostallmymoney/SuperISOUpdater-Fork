from pathlib import Path
from bs4 import BeautifulSoup
from bs4.element import Tag
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.md5_hash_check import md5_hash_check
from updaters.shared.parse_hash import parse_hash
from updaters.shared.robust_get import robust_get
from updaters.shared.verify_file_size import verify_file_size
from datetime import datetime
from functools import cache

DOMAIN = "https://templeos.org"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/Downloads/"
FILE_NAME = "TempleOS_[[EDITION]]_[[VER]].ISO"
ISOname = "TempleOS"

class TempleOS(GenericUpdater):
    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = ["Distro", "Lite"]
        self.edition = edition
        # Make the parameter case insensitive, and find back the correct case using valid_editions
        self.edition = next(
            valid_ed
            for valid_ed in self.valid_editions
            if valid_ed.lower() == self.edition.lower()
        )
        file_path = Path(folder_path) / FILE_NAME.replace("[[EDITION]]", self.edition)
        super().__init__(file_path, *args, **kwargs)
        self.server_file_name = (f"TempleOS{'Lite' if self.edition == 'Lite' else ''}.ISO")
        resp = robust_get(DOWNLOAD_PAGE_URL, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp is None or resp.status_code != 200:
            self.download_page = None
            self.soup_download_page = None
            return
        self.download_page = resp
        self.soup_download_page = BeautifulSoup(self.download_page.content.decode("utf-8"), features="html.parser")


    @cache
    def _get_download_link(self) -> str | None:
        return f"{DOWNLOAD_PAGE_URL}{self.server_file_name}"

    def check_integrity(self) -> bool | int | None:
        local_file = self._get_complete_normalized_file_path(absolute=True)
        download_link = self._get_download_link()
        if not isinstance(local_file, Path) or download_link is None:
            return -1
        if verify_file_size(local_file, download_link, logging_callback=self.logging_callback) is False:
            return False
        md5_url = f"{DOWNLOAD_PAGE_URL}md5sums.txt"
        resp = robust_get(md5_url, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp is None or resp.status_code != 200:
            self.logging_callback("Could not fetch md5sums.txt; skipping integrity check.")
            return False
        md5_sums = resp.text
        md5_sum = parse_hash(md5_sums, [self.server_file_name], 0, logging_callback=self.logging_callback)
        if md5_sum is None:
            return False
        return md5_hash_check(local_file, md5_sum, logging_callback=self.logging_callback)

    @cache
    def _get_latest_version(self) -> list[str] | None:
        if self.soup_download_page is None:
            self.logging_callback("Could not load TempleOS download page.")
            return None
        file_list_soup: Tag | None = self.soup_download_page.find("pre")  # type: ignore
        if not file_list_soup:
            self.logging_callback("Could not find download links list.")
            return None

        page_text = file_list_soup.getText()

        next_line_has_date = False
        date: str | None = None
        for line in page_text.splitlines():
            if self.server_file_name in line:
                next_line_has_date = True
                continue
            if next_line_has_date:
                # Remove last element (size)
                date = " ".join(line.strip().split()[1:-1])
                break
        if not date:
            self.logging_callback("Could not find date on download page.")
            return None

        datetime_date = datetime.strptime(date, r"%d-%b-%Y %H:%M")

        return self._str_to_version(str(datetime.timestamp(datetime_date)))
