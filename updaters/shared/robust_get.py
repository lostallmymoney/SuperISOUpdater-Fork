import requests
import time

def robust_get(
    url: str,
    logging_callback,
    method: str = "GET",
    retries: int = 5,
    delay: float = 1.0,
    redirects=True,
    timeout: float = 10.0,
    **kwargs
):
    def report(msg):
        logging_callback(msg)

    report(f"[robust_get] Fetching URL: {url}")

    attempt = 0
    network_attempt = 0

    PERMANENT_FAILURE_STATUSES = {400, 401, 410, 422, 451}
    MAX_HTTP_RETRIES = retries if retries != -1 else 10
    MAX_NETWORK_RETRIES = retries if retries != -1 else 10

    while True:
        try:
            headers = kwargs.pop("headers", {}).copy()

            resp = requests.request(
                method,
                url,
                headers=headers,
                timeout=timeout,
                allow_redirects=redirects,
                **kwargs
            )

            if resp.status_code in {301, 302, 303, 307, 308}:
                location = resp.headers.get("Location", "(no Location header)")
                report(f"Redirect ({resp.status_code}) for {url} to {location}")
                return None

            if resp.status_code in (200, 206):
                if not resp.encoding:
                    resp.encoding = "utf-8"
                return resp

            if resp.status_code in PERMANENT_FAILURE_STATUSES:
                attempt += 1
                report(f"HTTP {resp.status_code} (permanent retry {attempt}/{MAX_HTTP_RETRIES})")

                if attempt >= MAX_HTTP_RETRIES:
                    report(f"Exceeded HTTP retries for {url}")
                    return None

                time.sleep(delay)
                continue

            attempt += 1
            report(f"HTTP {resp.status_code} (retry {attempt}/{MAX_HTTP_RETRIES})")

            if attempt >= MAX_HTTP_RETRIES:
                report(f"Exceeded HTTP retries for {url}")
                return None

            time.sleep(delay)

        except requests.exceptions.RequestException as e:
            network_attempt += 1
            report(f"Network error: {e}")

            if network_attempt >= MAX_NETWORK_RETRIES:
                report(f"Exceeded network retries for {url}")
                return None

            report(f"Waiting for connection to resume for {url}... ({network_attempt}/{MAX_NETWORK_RETRIES})")
            time.sleep(3)
            continue

        except Exception as e:
            report(f"robust_get: Unexpected error: {e}")
            return None
