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

            # Add scheme if missing
            if not re.match(r"^(?:http|ftp)s?://", url):
                url = "http://" + url

            if not self.ping_url(url):
                obj.status = "check"
                obj.status_message = "URL not reachable"
                return obj

            http_status = self.check_http_status(url)
            if http_status != 200:
                obj.status = "check"
                obj.status_message = f"HTTP status code: {http_status}"
            else:
                obj.status = "ok"
                obj.status_message = ""

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

    def ping_url(self, url: str) -> bool:
        """
        Pings the given URL to check if it is reachable.

        Args:
            url (str): The URL to be pinged.

        Returns:
            bool: True if the URL is reachable, False otherwise.
        """
        try:
            response = requests.head(url, timeout=5)
            return response.status_code < 400
        except requests.RequestException:
            return False

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
