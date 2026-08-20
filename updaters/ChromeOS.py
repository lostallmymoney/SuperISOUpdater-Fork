from functools import cache
from pathlib import Path
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.robust_download import robust_download
from updaters.shared.list_zip_files import list_zip_files
from updaters.shared.extract_file_from_zip import extract_file_from_zip
from updaters.shared.sha1_hash_check import sha1_hash_check
import os

DOMAIN = "https://dl.google.com"
FILE_NAME = "chromeos_[[VER]]_[[EDITION]].img"
ISOname = "ChromeOS"


class ChromeOS(GenericUpdater):
    @cache
    def _get_download_link(self) -> str | None:
        if not self.cur_edition_info:
            self.logging_callback("No edition info available for download link.")
            return None
        return self.cur_edition_info.get("url")
    
    def __init__(self, folder_path: Path, edition: str = "stable", *args, **kwargs) -> None:
        self.valid_editions = ["ltc", "ltr", "stable"]
        self.edition = edition.lower() if edition else "stable"

        file_path = Path(folder_path) / FILE_NAME if 'FILE_NAME' in globals() else folder_path
        super().__init__(file_path, *args, **kwargs)

        import requests
        self.chromium_releases_info: list[dict] = requests.get(
            f"{DOMAIN}/dl/edgedl/chromeos/recovery/cloudready_recovery2.json"
        ).json()

        self.cur_edition_info: dict | None = next(
            d
            for d in self.chromium_releases_info
            if d["channel"].lower() == self.edition
        )

        self.extractOnly = False

        if not self.cur_edition_info:
            self.logging_callback(f"No release info found for edition '{self.edition}'")
            self.cur_edition_info = None
            return

    def check_integrity(self) -> bool | int | None:
        archive_path = self._get_archive_path()
        if archive_path is None or not Path(archive_path).is_file():
            return None

        if not self.cur_edition_info:
            self.logging_callback("No edition info available for integrity check.")
            return -1

        sha1_sum = self.cur_edition_info.get("sha1")
        if not sha1_sum:
            self.logging_callback(f"No release info found for edition '{self.edition}'")
            return -1

        zip_ok = sha1_hash_check(
            archive_path,
            sha1_sum,
            logging_callback=self.logging_callback
        )
        if not zip_ok:
            return False

        return True

    def _get_archive_path(self) -> Path | None:
        if not self.cur_edition_info:
            self.logging_callback("No edition info available to determine archive path.")
            return None
        
        img_path = self._get_complete_normalized_file_path(
            absolute=True,
            latest=True
        )
        if not isinstance(img_path, Path):
            self.logging_callback("Could not determine image path for archive.")
            return None
        
        # Create parent directory if it doesn't exist
        try:
            img_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logging_callback(f"Failed to create parent directory: {e}")
            return None
        
        return img_path.with_suffix('.zip')

    def install_latest_version(self, retries: int = 3) -> bool | None:
        archive_path = self._get_archive_path()
        if not self.cur_edition_info or not isinstance(archive_path, Path):
            self.logging_callback("Cannot proceed with installation: missing edition info or archive path.")
            return None

        # Ensure parent directory exists before download
        try:
            archive_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logging_callback(f"Failed to create directory for archive: {e}")
            return None

        img_path = archive_path.with_suffix("").with_suffix(".img")
        download_link = self._get_download_link()
        if not isinstance(download_link, str):
            self.logging_callback("No valid download link for ChromeOS installation.")
            return None

        zip_size = self.cur_edition_info.get("zipfilesize")
        is_extract_only = self.extractOnly

        if is_extract_only:
            self.logging_callback("Extract-only mode enabled: skipping download and archive verification.")

        if not is_extract_only:
            result = robust_download(
                download_link,
                local_file=archive_path,
                retries=retries,
                logging_callback=self.logging_callback,
                expected_size=zip_size
            )

            if not result:
                self.logging_callback("Download failed for ChromeOS archive.")
                return None

            sha1_sum = self.cur_edition_info.get("sha1")
            if not sha1_sum:
                archive_path.unlink(missing_ok=True)
                self.logging_callback("No SHA1 hash found for integrity check.")
                return None

            if not sha1_hash_check(
                archive_path,
                sha1_sum,
                logging_callback=self.logging_callback
            ):
                archive_path.unlink(missing_ok=True)
                return False

        file_list = list_zip_files(archive_path)
        bin_candidates = [f for f in file_list if f.lower().endswith('.bin')]
        if not bin_candidates:
            archive_path.unlink(missing_ok=True)
            self.logging_callback("No .bin file found in archive.")
            return None

        to_extract = bin_candidates[0]

        extract_file_from_zip(archive_path, to_extract, img_path.parent)
        extracted_file = img_path.parent / to_extract
        os.replace(extracted_file, img_path)

        # FINAL FILE SIZE CHECK (CORRECT FIELD: filesize, NOT zipfilesize)
        expected_bin_size = self.cur_edition_info.get("filesize")
        if expected_bin_size is not None:
            actual_size = img_path.stat().st_size
            self.logging_callback(
                f"Expected BIN size: {expected_bin_size}, File size: {actual_size} (file: {img_path})"
            )

            if actual_size != expected_bin_size:
                self.logging_callback("File size mismatch, will redownload.")
                return False

        return True

    @cache
    def _get_latest_version(self) -> list[str] | None:
        if not self.cur_edition_info:
            return None
        return self._str_to_version(self.cur_edition_info.get("version", "0.0.0"))