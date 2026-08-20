from functools import cache
import bz2
from pathlib import Path
from bs4 import BeautifulSoup
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.robust_get import robust_get
from updaters.shared.check_remote_integrity import check_remote_integrity
from updaters.shared.verify_signature import verify_opnsense_signature
from updaters.shared.robust_download import robust_download

import mmap

DOMAIN = "https://pkg.opnsense.org"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/releases/mirror"
FILE_NAME = "OPNsense-[[VER]]-[[EDITION]]-amd64.[[EXT]]"
ISOname = "OPNsense"
ISOname = "OPNsense"


class OPNsense(GenericUpdater):
    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = ["dvd", "nano", "serial", "vga"]
        self.edition = edition.lower()
        file_extension = "iso" if self.edition == "dvd" else "img"
        file_path = folder_path / FILE_NAME.replace("[[EXT]]", file_extension)
        super().__init__(file_path, *args, **kwargs)

        resp = robust_get(DOWNLOAD_PAGE_URL, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp is None or resp.status_code != 200:
            self.download_page = None
            self.soup_download_page = None
            return
        self.download_page = resp
        self.soup_download_page = BeautifulSoup(
            self.download_page.content.decode("utf-8"), features="html.parser"
        )

    @cache
    def _get_download_link(self) -> str | None:
        return f"{DOWNLOAD_PAGE_URL}/{self._get_complete_normalized_file_path(absolute=False)}.bz2"

    def check_integrity(self) -> bool | int | None:
        latest_version = self._get_latest_version()
        if latest_version is None:
            self.logging_callback("Could not determine the latest version for integrity check.")
            return -1

        latest_version_str = self._version_to_str(latest_version)
        pub_url = f"{DOWNLOAD_PAGE_URL}/OPNsense-{latest_version_str}.pub"
        sig_url = f"{DOWNLOAD_PAGE_URL}/OPNsense-{latest_version_str}-{self.edition}-amd64.img.sig"
        image_path = self._get_complete_normalized_file_path(absolute=True)

        pub_resp = robust_get(pub_url, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        sig_resp = robust_get(sig_url, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if not pub_resp or not sig_resp or pub_resp.status_code != 200 or sig_resp.status_code != 200:
            self.logging_callback("Failed to download pub or sig file for integrity check.")
            return -1

        return verify_opnsense_signature(
            pub_resp.content,
            sig_resp.content,
            image_path,
            logging_callback=self.logging_callback
        )

    def install_latest_version(self, retries: int = 0) -> bool | None:
        complete_path = self._get_complete_normalized_file_path(absolute=True)
        if not isinstance(complete_path, Path):
            return None
        archive_path = complete_path.with_name(complete_path.name + ".bz2")

        # Download the .bz2 archive
        download_url = self._get_download_link()
        if not isinstance(download_url, str) or not download_url:
            self.logging_callback(f"Download URL is invalid: {download_url}")
            return False
        self.logging_callback(f"Downloading archive: {download_url} -> {archive_path}")
        resp = robust_download(download_url, local_file=archive_path, retries=1, delay=1, logging_callback=self.logging_callback)
        if resp is not True:
            self.logging_callback(f"Download failed for archive: {download_url}")
            return False

        # Integrity check
        latest_version = self._get_latest_version()
        if latest_version is None:
            self.logging_callback("Could not determine the latest version for integrity check.")
            return False
        latest_version_str = self._version_to_str(latest_version)
        sha256_url = f"{DOWNLOAD_PAGE_URL}/OPNsense-{latest_version_str}-checksums-amd64.sha256"
        valid = check_remote_integrity(
            hash_url=sha256_url,
            local_file=archive_path,
            hash_type="sha256",
            parse_hash_args=([self.edition], -1),
            logging_callback=self.logging_callback,
        )
        if not valid:
            return False

        # Extract the .img from the .bz2
        try:
            with bz2.open(archive_path, "rb") as src, open(complete_path, "wb") as dst:
                for chunk in iter(lambda: src.read(8192), b""):
                    dst.write(chunk)
        except Exception as e:
            self.logging_callback(f"Failed to extract archive: {e}")
            return False

        # Remove the archive after extraction
        try:
            archive_path.unlink()
        except Exception:
            pass

        return True

    @cache
    def _get_latest_version(self) -> list[str] | None:
        download_a_tags = self.soup_download_page.find_all("a", href=True) if self.soup_download_page else []
        if not download_a_tags:
            self.logging_callback("Could not parse the download page for version info.")
            return None

        local_version = self._get_local_version()
        latest = local_version or []

        for a_tag in download_a_tags:
            href = a_tag.get("href")
            if not href or not isinstance(href, str) or self.edition not in href:
                continue
            version_number = self._str_to_version(href.split("-")[1])
            if self._compare_version_numbers(latest, version_number):
                latest = version_number

        return latest

