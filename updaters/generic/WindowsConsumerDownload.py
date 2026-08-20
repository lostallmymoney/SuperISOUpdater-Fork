import re
import time
import uuid
from datetime import datetime

import requests




class WindowsConsumerDownloader:

    def __init__(self, *args, ISOname="WindowsConsumerDownload", parent_log_callback=None, **kwargs):
        import hashlib
        import random
        self.parent_log_callback = parent_log_callback
        color_codes = [
            '\033[30m', # Black
            '\033[31m', # Red
            '\033[32m', # Green
            '\033[33m', # Yellow
            '\033[34m', # Blue
            '\033[35m', # Magenta
            '\033[36m', # Cyan
            '\033[37m', # White
            '\033[90m', # Bright Black (Gray)
            '\033[91m', # Bright Red
            '\033[92m', # Bright Green
            '\033[93m', # Bright Yellow
            '\033[94m', # Bright Blue
            '\033[95m', # Bright Magenta
            '\033[96m', # Bright Cyan
            '\033[97m', # Bright White
        ]
        reset_code = '\033[0m'
        # Global color registry for non-Windows updaters
        if not hasattr(WindowsConsumerDownloader, '_used_colors'):
            WindowsConsumerDownloader._used_colors = {}
        base_name = ISOname
        windows_names = {"Windows10", "Windows11", "WindowsConsumerDownloader", "GenericUpdater"}
        class_name = self.__class__.__name__
        if base_name and not (str(base_name).startswith('\033[') and str(base_name).endswith(reset_code)):
            if class_name in windows_names:
                idx = int(hashlib.sha256(str(base_name).encode()).hexdigest(), 16) % len(color_codes)
                color = color_codes[idx]
            else:
                used = WindowsConsumerDownloader._used_colors
                for i, color in enumerate(color_codes):
                    if color not in used.values():
                        used[class_name] = color
                        break
                else:
                    idx = int(hashlib.sha256(str(base_name).encode()).hexdigest(), 16) % len(color_codes)
                    color = color_codes[idx]
                    used[class_name] = color
                color = used[class_name]
            colored_name = f"{color}{base_name}{reset_code}"
            self.ISOname = colored_name
        else:
            self.ISOname = base_name
        self.session = requests.Session()
        self.session_id = str(uuid.uuid4())
        self.session_authorized = False

    def logging_callback(self, message: str):
        prefix = f"[{getattr(self, 'ISOname', self.__class__.__name__)}]"
        if not (isinstance(message, str) and message.strip().startswith(prefix)):
            message = f"{prefix} {message}"
        if self.parent_log_callback:
            self.parent_log_callback(message)
        else:
            print(message)

    _PROFILE_ID = "606624d44113"
    _ORG_ID = "y6jn8c31"

    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    _download_page_cache = {}
    _language_skuIDs_cache = {}
    _download_link_cache = {}

    def _download_page_url(self, windows_version: str) -> str:
        match windows_version:
            case "11":
                url_segment = f"windows{windows_version}"
            case "10" | "8":
                url_segment = f"windows{windows_version}ISO"
            case _:
                raise NotImplementedError(
                    "The valid Windows versions are '11', '10', or '8'."
                )
        return f"https://www.microsoft.com/en-us/software-download/{url_segment}"

    def _request(self, url: str, retries: int = 3, timeout: float = 10.0, **kwargs):
        headers = {
            **self._HEADERS,
            **kwargs.pop("headers", {}),
        }
        self.logging_callback(f"[robust_get] Fetching URL: {url}")
        for attempt in range(1, retries + 1):
            try:
                resp = self.session.get(url, headers=headers, timeout=timeout, **kwargs)
            except requests.exceptions.RequestException as e:
                self.logging_callback(f"Network error: {e}")
                if attempt >= retries:
                    self.logging_callback(f"Exceeded network retries for {url}")
                    return None
                self.logging_callback(f"Waiting for connection to resume for {url}... ({attempt}/{retries})")
                time.sleep(3)
                continue

            if resp.status_code == 200:
                if not resp.encoding:
                    resp.encoding = "utf-8"
                return resp

            self.logging_callback(f"HTTP {resp.status_code} (retry {attempt}/{retries})")
            if attempt >= retries:
                self.logging_callback(f"Exceeded HTTP retries for {url}")
                return None
            time.sleep(1)

        return None

    def windows_consumer_file_hash(self, windows_version: str, lang: str) -> str:
        """
        Obtain a Windows ISO download URL for a specific Windows version and language.

        Args:
            windows_version (str): The desired Windows version. Valid options are '11', '10', or '8'.
                                Default is '11'.
            lang (str): The desired language for the Windows ISO. Default is 'English International'.
                See https://www.microsoft.com/en-us/software-download/windows11 for a list of available languages

        Returns:
            str: Download link for the given Windows version and language
        """
        matches = re.search(
            rf"FileHash(.+\n+)+?^<\/tr>.+{lang}.+\n<td>(.+)<",
            self._get_download_page(windows_version),
            re.MULTILINE,
        )

        if not matches or not matches.groups():
            raise LookupError("Could not find SHA256 hash")

        file_hash = matches.group(2)
        return file_hash

    def _get_download_page(self, windows_version: str) -> str:
        page_url = self._download_page_url(windows_version)
        url_segment = page_url.rsplit("/", 1)[-1]

        if not url_segment in WindowsConsumerDownloader._download_page_cache:
            resp = self._request(
                page_url,
                headers={"Referer": "https://www.microsoft.com/en-us/software-download/"},
            )
            if resp is None or getattr(resp, 'status_code', 200) != 200:
                raise RuntimeError(
                    f"Could not load the Windows {windows_version} download page."
                )
            WindowsConsumerDownloader._download_page_cache[url_segment] = resp.text

        return WindowsConsumerDownloader._download_page_cache[url_segment]

    def windows_consumer_download(self, windows_version: str, lang: str) -> str | None:
        """
        Obtain a Windows ISO download URL for a specific Windows version and language.

        Args:
            windows_version (str): The desired Windows version. Valid options are '11', '10', or '8'.
                                Default is '11'.
            lang (str): The desired language for the Windows ISO. Default is 'English International'.
                See https://www.microsoft.com/en-us/software-download/windows11 for a list of available languages
            logging_callback (callable, optional): A function to call with log messages.

        Returns:
            str: Download link for the given Windows version and language
        """
        def log(msg):
            self.logging_callback(msg)

        matches = re.search(
            r'<option value="([0-9]+)">Windows',
            self._get_download_page(windows_version),
        )
        if not matches or not matches.groups():
            raise LookupError("Could not find product edition id")

        product_edition_id = matches.group(1)
        log(f"[windows_consumer_download] Product edition id: `{product_edition_id}`")

        page_url = self._download_page_url(windows_version)
        referer_header = {"Referer": page_url}

        if not self.session_authorized:
            resp = self._request(
                f"https://vlscppe.microsoft.com/tags?org_id={self._ORG_ID}&session_id={self.session_id}",
                headers=referer_header,
            )
            if resp is None:
                raise RuntimeError("Could not authorize Windows download session")
            self.session_authorized = True

        if product_edition_id not in self._language_skuIDs_cache:
            language_skuIDs_url = (
                "https://www.microsoft.com/software-download-connector/api/getskuinformationbyproductedition"
                + f"?profile={self._PROFILE_ID}"
                + f"&productEditionId={product_edition_id}"
                + f"&SKU=undefined"
                + f"&friendlyFileName=undefined"
                + f"&Locale=en-US"
                + f"&sessionID={self.session_id}"
            )
            # concise log only
            log(f"[windows_consumer_download] Fetching SKU info")
            resp = self._request(
                language_skuIDs_url,
                headers=referer_header,
            )
            if resp is None or getattr(resp, 'status_code', 200) != 200:
                log("[windows_consumer_download] Could not fetch SKU info (no response or bad status)")
                raise ValueError("Could not fetch SKU IDs")
            # Keep only concise status and count information to avoid large dump
            log(f"[windows_consumer_download] SKU info HTTP status: {getattr(resp, 'status_code', 'NO STATUS')}")
            language_skuIDs = resp.json()
            try:
                sku_count = len(language_skuIDs.get("Skus", []))
            except Exception:
                sku_count = "unknown"
            log(f"[windows_consumer_download] SKU info received, skus={sku_count}")
            if not "Skus" in language_skuIDs:
                log(f"[windows_consumer_download] SKU JSON: {language_skuIDs}")
                raise ValueError("Could not find SKU IDs")
            self._language_skuIDs_cache[product_edition_id] = language_skuIDs

        language_skuIDs = self._language_skuIDs_cache[product_edition_id]

        sku_id = None
        # Find matching SKU by language; avoid logging entire SKU list to reduce noise
        for sku in language_skuIDs.get("Skus", []):
            if sku.get("Language") == lang:
                sku_id = sku.get("Id")
                break
        if sku_id:
            log(f"[windows_consumer_download] Matched SKU ID: {sku_id}")

        if not sku_id:
            log(f"[windows_consumer_download] No SKU found for language: {lang}")
            raise ValueError(f"The language '{lang}' for Windows could not be found!")

        log(f"[windows_consumer_download] Found SKU ID {sku_id} for {lang}")

        if (
            sku_id not in self._download_link_cache
            or datetime.now() >= self._download_link_cache[sku_id]["expires"]
        ):
            # Get ISO download link page
            iso_download_link_page = (
                "https://www.microsoft.com/software-download-connector/api/GetProductDownloadLinksBySku"
                + f"?profile={self._PROFILE_ID}"
                + f"&productEditionId={product_edition_id}"
                + f"&SKU={sku_id}"
                + "&friendlyFileName=undefined"
                + f"&Locale=en-US"
                + f"&sessionID={self.session_id}"
            )
            log(f"[windows_consumer_download] Fetching ISO download link from: {iso_download_link_page}")
            resp = self._request(
                iso_download_link_page,
                headers=referer_header,
            )
            if resp is None or getattr(resp, 'status_code', 200) != 200:
                log(f"[windows_consumer_download] Could not fetch ISO download link page, status: {getattr(resp, 'status_code', 'NO STATUS')}")
                raise RuntimeError("Could not fetch ISO download link page")
            iso_download_link_json = resp.json()
            if "Errors" in iso_download_link_json:
                log(f"[windows_consumer_download] Errors from Microsoft: {iso_download_link_json['Errors']}")
                # Do not raise, just return None so the caller can retry or handle as needed
                return None
            # Find the x64 ISO link in ProductDownloadOptions
            x64_option = None
            for option in iso_download_link_json.get("ProductDownloadOptions", []):
                uri = option.get("Uri", "")
                # Heuristic: look for x64 in the filename or URL
                if "x64" in uri.lower():
                    x64_option = option
                    break
            if not x64_option:
                # Fallback: just use the first option, but log a warning
                log("[windows_consumer_download] WARNING: Could not find x64 ISO, using first available option!")
                x64_option = iso_download_link_json["ProductDownloadOptions"][0]
            self._download_link_cache[sku_id] = {
                "expires": datetime.strptime(
                    iso_download_link_json["DownloadExpirationDatetime"][:-2],
                    "%Y-%m-%dT%H:%M:%S.%f",
                ),
                "link": x64_option["Uri"],
            }

        download_link = self._download_link_cache[sku_id]["link"]
        log(f"[windows_consumer_download] Selected download link: {download_link}")
        return download_link
