from datetime import datetime
import logging
from typing import List
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from model import ValidationObject


class validate_URL:
    """
    A class to validate URLs in several steps: syntax check, ping, and HTTP status check.
    """

    def validate_fast(self, objects: List[ValidationObject]) -> List[ValidationObject]:
        """
        Validates a list of ValidationObject instances by checking URL syntax.
        Updates the status field of each ValidationObject.

        Args:
            objects (List[ValidationObject]): A list of ValidationObject instances to be validated.

        Returns:
            List[ValidationObject]: The list of ValidationObject instances with updated status fields.
        """
        for obj in objects:
            logging.info(f"Validating URL: {obj.value}")
            obj.last_visited = datetime.now()
            url = obj.value

            # Add scheme if missing
            if not re.match(r"^(?:http|ftp)s?://", url):
                url = "http://" + url

            if not self.is_valid_url(url):
                obj.status = "check"
                obj.status_message = "Invalid URL syntax"
                continue

            obj.status = "formal ok"
            obj.status_message = "API check outstanding"
            
        return objects

    def validate_slow(self, objects: List[ValidationObject]) -> List[ValidationObject]:
        """
        Validates a list of ValidationObject instances by pinging the URL,
        and checking the HTTP status code. Updates the status field of each ValidationObject.

        Args:
            objects (List[ValidationObject]): A list of ValidationObject instances to be validated.

        Returns:
            List[ValidationObject]: The list of ValidationObject instances with updated status fields.
        """
        def validate_object(obj):
            logging.info(f"Validating URL: {obj.value}")
            obj.last_visited = datetime.now()
            url = obj.value

            obj.status, obj.status_message = self.ping_url(url)

            return obj

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(validate_object, obj) for obj in objects]
            for future in as_completed(futures):
                future.result()

        return objects

    def is_valid_url(self, url: str) -> bool:
        """
        Checks if the given URL has a valid syntax.

        Args:
            url (str): The URL to be checked.

        Returns:
            bool: True if the URL has a valid syntax, False otherwise.
        """
        regex = re.compile(
            r"^(?:http|ftp)s?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
            r"localhost|"  # localhost...
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|"  # ...or ipv4
            r"\[?[A-F0-9]*:[A-F0-9:]+\]?)"  # ...or ipv6
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )
        return re.match(regex, url) is not None

    def ping_url(self, url: str) -> (str, str):
        """
        Checks if the given URL is reachable like a browser would:
        - Ensures HTTPS is used
        - Adds a browser-like User-Agent
        - Follows redirects
        - Falls back to GET if HEAD fails

        Args:
            url (str): The URL to be checked.

        Returns:
            tuple: ("ok", "") if reachable, ("check", <reason>) otherwise.
        """
        # Ensure HTTPS is used
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        elif url.startswith("http://"):
            url = "https://" + url[len("http://"):]

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/114.0.0.0 Safari/537.36"
            )
        }

        try:
            logging.info(f"Checking URL: {url}")
            response = requests.head(url, allow_redirects=True, timeout=5, headers=headers)
            if response.status_code < 400:
                return "ok", ""
            # Fallback to GET
            response = requests.get(url, allow_redirects=True, timeout=5, headers=headers)
            if response.status_code < 400:
                return "ok", ""
            else:
                return "check", f"HTTP error: {response.status_code}"
        except Exception as e:
            return "check", f"Exception: {str(e)}"
        
    def check_http_status(self, url: str) -> int:
        """
        Checks the HTTP status code of the given URL.

        Args:
            url (str): The URL to be checked.

        Returns:
            int: The HTTP status code of the URL, or 0 if the request failed.
        """
        try:
            response = requests.get(url, timeout=5)
            return response.status_code
        except requests.RequestException as e:
            return 0
