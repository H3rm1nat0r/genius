from datetime import datetime
import logging
from typing import List
import re

from model import ValidationObject


class validate_VAT_ID:
    """
    A class to validate European VAT IDs by checking their syntax and checksum.
    """

    def validate(self, objects: List[ValidationObject]) -> List[ValidationObject]:
        """
        Validates a list of ValidationObject instances by checking VAT ID syntax and checksum.
        Updates the status field of each ValidationObject.

        Args:
            objects (List[ValidationObject]): A list of ValidationObject instances to be validated.

        Returns:
            List[ValidationObject]: The list of ValidationObject instances with updated status fields.
        """
        for obj in objects:
            logging.info(f"Validating VAT_ID: {obj.value}")
            obj.last_visited = datetime.now()
            vat_id = obj.value

            if not self.is_valid_vat_syntax(vat_id):
                obj.status = "CHECK"
                obj.status_message = "Invalid VAT ID syntax"
                continue

            if not self.is_valid_vat_checksum(vat_id):
                obj.status = "CHECK"
                obj.status_message = "Invalid VAT ID checksum"
                continue

            obj.status, obj.status_message = self._validate_vat_api_call(vat_id)

        return objects

    def is_valid_vat_syntax(self, vat_id: str) -> bool:
        """
        Checks if the given VAT ID has a valid syntax.

        Args:
            vat_id (str): The VAT ID to be checked.

        Returns:
            bool: True if the VAT ID has a valid syntax, False otherwise.
        """
        regex = re.compile(r"^[A-Z]{2}[A-Z0-9]{2,12}$", re.IGNORECASE)
        return re.match(regex, vat_id) is not None

    def is_valid_vat_checksum(self, vat_id: str) -> bool:
        """
        Checks if the given VAT ID has a valid checksum.

        Args:
            vat_id (str): The VAT ID to be checked.

        Returns:
            bool: True if the VAT ID has a valid checksum, False otherwise.
        """
        country_code = vat_id[:2].upper()
        number = vat_id[2:]

        if country_code == "DE":
            return self._is_valid_german_vat_checksum(number)
        elif country_code == "AT":
            return self._is_valid_austrian_vat_checksum(number)
        elif country_code == "CH":
            return self._is_valid_swiss_vat_checksum(number)
        else:
            # For simplicity, assume other VAT IDs are valid
            return True

    def _is_valid_german_vat_checksum(self, number: str) -> bool:
        """
        Validates the checksum for a German VAT ID.

        Args:
            number (str): The VAT ID number part (without country code).

        Returns:
            bool: True if the checksum is valid, False otherwise.
        """
        if len(number) != 9:
            return False

        product = 10
        for i in range(8):
            sum = (int(number[i]) + product) % 10
            if sum == 0:
                sum = 10
            product = (2 * sum) % 11

        check_digit = (11 - product) % 10
        return check_digit == int(number[8])

    def _is_valid_austrian_vat_checksum(self, number: str) -> bool:
        """
        Validates the checksum for an Austrian VAT ID.

        Args:
            number (str): The VAT ID number part (without country code).

        Returns:
            bool: True if the checksum is valid, False otherwise.
        """
        if len(number) != 9 or not number.startswith("U"):
            return False

        weights = [1, 2, 1, 2, 1, 2, 1]
        total = 0
        for i in range(7):
            product = int(number[i + 1]) * weights[i]
            total += product // 10 + product % 10

        check_digit = (10 - (total + 4) % 10) % 10
        return check_digit == int(number[8])

    def _is_valid_swiss_vat_checksum(self, number: str) -> bool:
        """
        Validates the checksum for a Swiss VAT ID.

        Args:
            number (str): The VAT ID number part (without country code).

        Returns:
            bool: True if the checksum is valid, False otherwise.
        """
        if len(number) != 9 or not number.startswith("CHE"):
            return False

        weights = [5, 4, 3, 2, 7, 6, 5, 4]
        total = sum(int(number[i]) * weights[i] for i in range(8))
        check_digit = 11 - (total % 11)
        if check_digit == 10:
            check_digit = 0
        return check_digit == int(number[8])

    def _validate_vat_api_call(self, number: str) -> (str,str): # type: ignore
        """
        Calls an external API to validate the VAT ID.

        Args:
            number (str): The VAT ID number part (without country code).

        Returns:
            bool: True if the VAT ID is valid, False otherwise.
        """
        # Placeholder for API call
        return ("OK", "")