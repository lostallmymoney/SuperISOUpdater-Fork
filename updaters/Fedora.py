from functools import cache
import re
from pathlib import Path
from bs4 import BeautifulSoup
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.check_remote_integrity import check_remote_integrity
from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.robust_get import robust_get

BASE_URL = "https://download.fedoraproject.org/pub/fedora/linux/releases"
FILE_NAME = "Fedora-[[EDITION]]-Live-x86_64-[[VER]].iso"
ISOname = "Fedora"


class Fedora(GenericUpdater):
    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = [
            "Budgie", "Cinnamon", "KDE", "LXDE", "MATE_Compiz", "SoaS", "Sway", "Xfce", "i3"
        ]
        self.edition = edition
        file_name = FILE_NAME.replace("[[EDITION]]", self.edition)
        file_path = folder_path / file_name
        super().__init__(file_path, *args, **kwargs)
        self.edition = next(
            valid_ed for valid_ed in self.valid_editions if valid_ed.lower() == self.edition.lower()
        )
        self.download_page = None
        self.soup_download_page = BeautifulSoup("", features="html.parser")

    @cache
    def _get_download_link(self) -> str | None:
        latest_version = self._get_latest_version()
        if not latest_version or not isinstance(latest_version, list) or not latest_version[0]:
            return None
        major = latest_version[0]
        iso_dir = robust_get(f"{BASE_URL}/{major}/Spins/x86_64/iso/", logging_callback=self.logging_callback, timeout=20)
        if not iso_dir or getattr(iso_dir, 'status_code', 0) != 200:
            self.logging_callback(f"Could not fetch ISO listing for Fedora {major}.")
            return None

        for href in re.findall(r'href=["\']([^"\']+)["\']', iso_dir.text):
            if href.endswith('.iso') and 'Live' in href and self.edition.lower() in href.lower():
                return f"{BASE_URL}/{major}/Spins/x86_64/iso/{href}"
        return None

    def check_integrity(self) -> bool | int | None:
        latest_version = self._get_latest_version()
        if not isinstance(latest_version, list):
            self.logging_callback(f"Could not determine latest version for edition: {self.edition}")
            return None
        local_file = self._get_complete_normalized_file_path(absolute=True)
        if not local_file.exists():
            self.logging_callback(f"File does not exist: {local_file}")
            return False

        major = latest_version[0]
        minor = latest_version[1] if len(latest_version) > 1 else None
        if minor is None:
            self.logging_callback(f"Could not determine Fedora release minor version for {self.edition}")
            return None

        sha256_url = f"{BASE_URL}/{major}/Spins/x86_64/iso/Fedora-Spins-{major}-{minor}-x86_64-CHECKSUM"
        iso_url = self._get_download_link()
        if not iso_url:
            self.logging_callback("Could not determine ISO download URL for file size check.")
            return None

        size_ok = verify_file_size(local_file, iso_url, logging_callback=self.logging_callback)
        if not size_ok:
            self.logging_callback("File size check failed.")
            return False

        hash_ok = check_remote_integrity(
            hash_url=sha256_url,
            local_file=local_file,
            hash_type="sha256",
            parse_hash_args=(["SHA256 (Fedora-", self.edition, "Live"], 3),
            logging_callback=self.logging_callback
        )
        if not hash_ok:
            self.logging_callback("Hash check failed.")
            return False
        return True

    @cache
    def _get_latest_version(self) -> list[str] | None:
        release_index = robust_get(f"{BASE_URL}/", logging_callback=self.logging_callback, timeout=20)
        if not release_index or getattr(release_index, 'status_code', 0) != 200:
            self.logging_callback(f"Could not fetch Fedora release index from {BASE_URL}.")
            return None

        releases = sorted(
            {match for match in re.findall(r'href=["\']?(\d+)[/"\']?', release_index.text) if match.isdigit()},
            key=lambda x: int(x),
            reverse=True,
        )
        if not releases:
            self.logging_callback("Could not determine latest Fedora release from the release index.")
            return None

        latest_major = releases[0]
        iso_dir = robust_get(f"{BASE_URL}/{latest_major}/Spins/x86_64/iso/", logging_callback=self.logging_callback, timeout=20)
        if not iso_dir or getattr(iso_dir, 'status_code', 0) != 200:
            self.logging_callback(f"Could not fetch ISO listing for Fedora {latest_major}.")
            return None

        iso_link = None
        for href in re.findall(r'href=["\']([^"\']+)["\']', iso_dir.text):
            if href.endswith('.iso') and 'Live' in href and self.edition.lower() in href.lower():
                iso_link = href
                break
        if not iso_link:
            self.logging_callback(f"Could not find Fedora ISO link. Edition: {self.edition}, major: {latest_major}")
            return None

        m = re.search(
            rf"Fedora-{re.escape(self.edition)}(?:-Mobile)?-Live(?:-x86_64)?-(\d+)-([\d.]+)(?:\.x86_64)?\.iso$",
            iso_link,
            flags=re.IGNORECASE,
        )
        if not m:
            self.logging_callback(f"Could not extract version from ISO link: {iso_link}")
            return None
        return [m.group(1), m.group(2)]