from functools import cache
from pathlib import Path
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.parse_hash import parse_hash
from updaters.shared.sha256_hash_check import sha256_hash_check
from updaters.shared.robust_get import robust_get
from updaters.shared.check_remote_integrity import check_remote_integrity
from updaters.shared.verify_file_size import verify_file_size
import re

DOMAIN = "https://enterprise.proxmox.com"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/iso"
FILE_NAME = "proxmox-[[EDITION]]_[[VER]].iso"
ISOname = "Proxmox"


class Proxmox(GenericUpdater):
    """
    A class representing an updater for Proxmox.

    Attributes:
        valid_editions (list[str]): List of valid editions to use
        edition (str): Edition to download
        download_page (requests.Response): The HTTP response containing the download page HTML.
        soup_download_page (BeautifulSoup): The parsed HTML content of the download page.

    Note:
        This class inherits from the abstract base class GenericUpdater.
    """

    def __init__(self, folder_path: Path, edition: str, **kwargs) -> None:
        self.valid_editions = [
            "ve",
            "mail-gateway",
        ]
        self.edition = edition
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, **kwargs)

        self.edition = next(
            valid_ed
            for valid_ed in self.valid_editions
            if valid_ed.lower() == self.edition.lower()
        )

        self.download_page = None
        self.soup_download_page = None

    @cache
    def _get_download_link(self) -> str | None:
        latest_version = self._get_latest_version()
        if latest_version is None:
            return None

        latest_version_str = self._version_to_str(latest_version)

        return f"{DOWNLOAD_PAGE_URL}/{FILE_NAME.replace('[[VER]]', latest_version_str).replace('[[EDITION]]', self.edition)}"

    @cache
    def _get_latest_version(self) -> list[str] | None:
        sha256_url = f"{DOWNLOAD_PAGE_URL}/SHA256SUMS"
        resp = robust_get(sha256_url, retries=3, delay=1, logging_callback=self.logging_callback)

        if resp is None or resp.status_code != 200:
            self.logging_callback("Could not fetch SHA256SUMS")
            return None

        lines = resp.text.splitlines()
        filename_regex = re.compile(rf"^proxmox-{re.escape(self.edition)}_(\d+(?:\.\d+)*)-(\d+)\.iso$")
        versions: list[tuple[tuple[int, ...], int, list[str]]] = []

        for line in lines:
            parts = line.strip().split()
            if len(parts) != 2:
                continue

            filename = parts[1]
            match = filename_regex.match(filename)
            if not match:
                continue
            base, build = match.groups()
            version_parts = tuple(int(part) for part in base.split("."))
            versions.append((version_parts, int(build), base.split(".") + [build]))

        if not versions:
            self.logging_callback("No valid versions found in SHA256SUMS")
            return None

        return max(versions, key=lambda version: (version[0], version[1]))[2]

    def check_integrity(self) -> bool | int | None:
        sha256_url = f"{DOWNLOAD_PAGE_URL}/SHA256SUMS"
        local_file = self._get_complete_normalized_file_path(absolute=True)
        download_link = self._get_download_link()

        if not isinstance(local_file, Path) or download_link is None:
            self.logging_callback("Could not resolve file path or download link for integrity check.")
            return None

        if verify_file_size(local_file, download_link, logging_callback=self.logging_callback) is False:
            return False

        return check_remote_integrity(
            hash_url=sha256_url,
            local_file=local_file,
            hash_type="sha256",
            parse_hash_args=([str(self._get_complete_normalized_file_path(absolute=False))], 0),
            logging_callback=self.logging_callback,
        )

    def _version_to_str(self, version: list[str], version_splitter: str = ".") -> str:
        version = version.copy()
        dash_something: str = version.pop()
        return f"{version_splitter.join(str(i) for i in version)}-{dash_something}"

    def _str_to_version(self, version_str: str) -> list[str]:
        base, dash = version_str.split("-", 1)
        return base.split(".") + [dash]
