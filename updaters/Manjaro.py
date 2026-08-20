import re
from functools import cache
from pathlib import Path
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.robust_get import robust_get
from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.parse_hash import parse_hash
from updaters.shared.sha256_hash_check import sha256_hash_check
from updaters.shared.sha512_hash_check import sha512_hash_check
from updaters.shared.md5_hash_check import md5_hash_check

DOMAIN = "https://gitlab.manjaro.org"
PRIMARY_DOWNLOAD_PAGE_URL = f"{DOMAIN}/web/iso-info/-/raw/master/file-info.json"
FALLBACK_DOWNLOAD_PAGE_URL = f"{DOMAIN}/fhdk/iso-info/-/raw/master/file-info.json"
DOWNLOAD_PAGE_URLS = [PRIMARY_DOWNLOAD_PAGE_URL, FALLBACK_DOWNLOAD_PAGE_URL]
FILE_NAME = "manjaro-[[EDITION]]-[[VER]]-linux.iso"

ISOname = "Manjaro"


class Manjaro(GenericUpdater):
    """
    A class representing an updater for Manjaro.

    Attributes:
        valid_editions (list[str]): List of valid editions to use
        edition (str): Edition to download
        file_info_json (dict[Any, Any]): JSON file containing file information for each edition

    Note:
        This class inherits from the abstract base class GenericUpdater.
    """

    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = ["plasma", "xfce", "gnome", "cinnamon", "i3"]
        self.edition = edition.lower()
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)
        self.file_info_json = None
        payloads = []
        for url in DOWNLOAD_PAGE_URLS:
            self.logging_callback(f"Fetching metadata from {url}")
            resp = robust_get(url, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
            if resp is None:
                continue
            try:
                payload = resp.json()
            except Exception as exc:
                self.logging_callback(f"Metadata payload invalid for {url}: {exc}")
                continue
            payloads.append(payload)

        if not payloads:
            self.logging_callback("Unable to load release metadata from all known GitLab endpoints.")
            return

        merged = {"official": {}, "community": {}}
        for payload in payloads:
            for bucket in ("official", "community"):
                for ed, release in (payload.get(bucket, {}) or {}).items():
                    existing = merged[bucket].get(ed)
                    release_version = self._release_version_from_image(release.get("image")) if isinstance(release, dict) else None
                    existing_version = self._release_version_from_image(existing.get("image")) if isinstance(existing, dict) else None
                    if existing is None or (release_version is not None and (existing_version is None or release_version > existing_version)):
                        merged[bucket][ed] = release

        self.file_info_json = merged
        self.file_info_json["releases"] = self.file_info_json.get("official", {}) | self.file_info_json.get("community", {})

    @cache
    def _get_download_link(self) -> str | None:
        if not self.file_info_json:
            return None
        release = self.file_info_json.get("releases", {}).get(self.edition)
        if not release:
            self.logging_callback(f"No release metadata found for edition '{self.edition}'.")
            return None
        return release.get("image")

    @staticmethod
    def _release_version_from_image(image_url: str | None) -> tuple[int, ...] | None:
        if not image_url:
            return None
        match = re.search(r"/(\d+(?:\.\d+)*)/[^/]+$", image_url)
        if not match:
            return None
        try:
            return tuple(int(part) for part in match.group(1).split("."))
        except ValueError:
            return None

    def check_integrity(self) -> bool | int | None:
        if not self.file_info_json:
            self.logging_callback(f"No file info JSON loaded.")
            return False
        checksum_url = self.file_info_json["releases"][self.edition]["checksum"]
        if checksum_url.endswith(".sha512"):
            hash_type = "sha512"
        elif checksum_url.endswith(".sha256"):
            hash_type = "sha256"
        elif checksum_url.endswith(".md5"):
            hash_type = "md5"
        else:
            hash_type = "sha256"  # fallback
        local_file = self._get_complete_normalized_file_path(absolute=True)
        if not isinstance(local_file, Path):
            return -1
        local_file = Path(local_file)
        download_link = self._get_download_link()
        if download_link is None:
            return -1
        if not verify_file_size(local_file, download_link, logging_callback=self.logging_callback):
            return False
        # Hash check
        resp = robust_get(checksum_url, retries=3, delay=1, logging_callback=self.logging_callback)
        if resp is None:
            self.logging_callback(f"Could not fetch checksum file: robust_get failed")
            return -1
        hash_file = resp.text
        hash_val = parse_hash(hash_file, [], 0, logging_callback=self.logging_callback)
        if not hash_val:
            return -1
        if hash_type == "sha512":
            return sha512_hash_check(local_file, hash_val, logging_callback=self.logging_callback)
        elif hash_type == "sha256":
            return sha256_hash_check(local_file, hash_val, logging_callback=self.logging_callback)
        elif hash_type == "md5":
            return md5_hash_check(local_file, hash_val, logging_callback=self.logging_callback)
        return -1

    @cache
    def _get_latest_version(self) -> list[str] | None:
        download_link = self._get_download_link()
        if download_link:
            latest_version_regex = re.search(r"manjaro-[A-Za-z0-9-]+-(.+?)-(?:linux|\d+)", download_link)
            if latest_version_regex:
                return self._str_to_version(latest_version_regex.group(1))

        # Fallback: try to get version from local filename if available
        local_file = self._get_local_file()
        if local_file:
            filename = local_file.name
            version_match = re.search(r"manjaro-[A-Za-z0-9-]+-(.+?)-linux", filename)
            if version_match:
                return self._str_to_version(version_match.group(1))

        self.logging_callback("Could not find the latest available version")
        return None
