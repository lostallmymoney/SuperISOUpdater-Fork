from functools import cache
from pathlib import Path
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.robust_get import robust_get
from updaters.shared.fetch_expected_file_size import fetch_expected_file_size as fetch_expected_file_size
from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.check_remote_integrity import check_remote_integrity

import re
import requests
from urllib.parse import urljoin


DOMAIN = "https://download.opensuse.org"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/distribution/[[EDITION]]"
FILE_NAME = "Leap-[[VER]]-offline-installer-x86_64.install.iso"

ISOname = "OpenSUSE"


class OpenSUSE(GenericUpdater):
    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = ["leap", "leap-micro", "jump"]
        self.edition = edition.lower()
        self.download_page_url = DOWNLOAD_PAGE_URL.replace("[[EDITION]]", self.edition)
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)

    def _capitalize_edition(self) -> str:
        return "-".join([s.capitalize() for s in self.edition.split("-")])

    @cache
    def _resolve_latest_version_from_redirect(self) -> list[str] | None:
        """
        Extract latest version from get.opensuse.org HTML.
        Example:
        https://get.opensuse.org/leap/
        contains:
        /leap/16.0/
        """
        url = f"https://get.opensuse.org/{self.edition}/"

        try:
            resp = requests.get(url, timeout=10)
            html = resp.text
        except Exception as e:
            self.logging_callback(f"[{ISOname}] Failed to fetch get.opensuse page: {e}")
            return None

        match = re.search(rf"/{self.edition}/([0-9]+\.[0-9]+)/", html)

        if not match:
            self.logging_callback(f"[{ISOname}] Could not parse version from get.opensuse page")
            return None

        version_str = match.group(1)

        try:
            return self._str_to_version(version_str)
        except Exception:
            self.logging_callback(f"[{ISOname}] Invalid version format: {version_str}")
            return None

    @cache
    def _get_download_link(self) -> str | None:
        latest_version = self._get_latest_version()

        if latest_version is None:
            return None

        latest_version_str = self._version_to_str(latest_version)

        # New Leap ISO layout
        if self.edition == "leap":
            directory_url = f"{self.download_page_url}/{latest_version_str}/offline/"
            resp = robust_get(directory_url, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
            if resp is None or resp.status_code != 200:
                self.logging_callback(f"[{ISOname}] Could not list Leap offline directory: {directory_url}")
                return f"{directory_url}Leap-{latest_version_str}-offline-installer-x86_64.install.iso"

            html = resp.text
            candidates = re.findall(
                r'href=["\'](\./Leap-' + re.escape(latest_version_str) + r'-offline-installer-x86_64(?:-Build[0-9.]+)?\.install\.iso)["\']',
                html,
            )
            if candidates:
                build_candidates = [c for c in candidates if "-Build" in c]
                if build_candidates:
                    def build_key(name: str):
                        match = re.search(r"Build([0-9]+(?:\.[0-9]+)?)", name)
                        if not match:
                            return (0,)
                        return tuple(int(part) for part in match.group(1).split("."))
                    best = max(build_candidates, key=build_key)
                    return urljoin(directory_url, best)
                return urljoin(directory_url, sorted(candidates)[-1])
            return f"{directory_url}Leap-{latest_version_str}-offline-installer-x86_64.install.iso"

        # Existing behavior for other editions
        url = f"{self.download_page_url}/{latest_version_str}"

        resp = robust_get(
            f"{url}?jsontable",
            retries=self.retries_count,
            delay=1,
            logging_callback=self.logging_callback
        )

        if resp is None:
            return ""

        edition_page = resp.json()["data"]

        if any("product" in item["name"] for item in edition_page):
            url += "/product"

        if self.edition != "leap-micro":
            latest_version_str += "-NET"

        return (
            f"{url}/iso/openSUSE-{self._capitalize_edition()}"
            f"-{latest_version_str}-x86_64"
            f"{'-Current' if self.edition != 'leap-micro' else ''}.iso"
        )

    def check_integrity(self) -> bool | int | None:
        file = self._get_complete_normalized_file_path(absolute=True)

        if not isinstance(file, Path):
            self.logging_callback("File path is not a valid Path object for integrity check.")
            return -1

        link = self._get_download_link()

        if not link:
            self.logging_callback("Could not determine download link for integrity check.")
            return -1

        self.logging_callback(f"[{ISOname}] Resolved download link: {link}")

        if not verify_file_size(file, link, logging_callback=self.logging_callback):
            return False

        # OpenSUSE Leap publishes checksums only for the concrete build-specific file.
        # The generic alias is a redirect/compatibility link and does not have a checksum file.
        hash_urls = []
        if self.edition == "leap":
            hash_urls.append((f"{link}.sha512", "sha512"))
            hash_urls.append((f"{link}.sha256", "sha256"))
            hash_urls.append((f"{link.rsplit('/', 1)[0]}/CHECKSUMS", "sha256"))
        else:
            hash_urls.append((f"{link}.sha256", "sha256"))

        for hash_url, hash_type in hash_urls:
            result = check_remote_integrity(
                hash_url,
                file,
                hash_type,
                ([Path(link).name], 0),
                logging_callback=self.logging_callback,
            )
            if result != -1:
                return result

        # If no hash file found, return -1 (unavailable) rather than failing.
        self.logging_callback(f"[{ISOname}] Could not find hash file for integrity check, accepting file as valid")
        return -1

    @cache
    def _get_latest_version(self) -> list[str] | None:
        return self._resolve_latest_version_from_redirect()