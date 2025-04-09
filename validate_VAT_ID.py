import configparser
from datetime import datetime
import json
import logging
from typing import List
import re
from viesapi import VIESAPIClient

from model import ValidationObject


class validate_VAT_ID:
    """
    A class to validate European VAT IDs by checking their syntax and checksum.
    """

    def validate_fast(self, objects: List[ValidationObject]) -> List[ValidationObject]:
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
                obj.status = "check"
                obj.status_message = "Invalid VAT ID syntax"
                continue

            if not self.is_valid_vat_checksum(vat_id):
                obj.status = "check"
                obj.status_message = "Invalid VAT ID checksum"
                continue

            # If the VAT ID is valid, set status to "formal ok"
            obj.status = "formal ok"
            obj.status_message = "API check outstanding"

        return objects


    def validate_slow(self, objects: List[ValidationObject]) -> List[ValidationObject]:
        """
        NO SLOW VALIDATION IMPLEMENTED YET

        Args:
            objects (List[ValidationObject]): A list of ValidationObject instances to be validated.

        Returns:
            List[ValidationObject]: The list of ValidationObject instances with updated status fields.
        """

        config = configparser.ConfigParser()
        config.read("config.ini")
        viesapicredentials = config["viesapi"]
        viesapi = VIESAPIClient(
            viesapicredentials["Identifier"], viesapicredentials["Key"]
        )
        account = viesapi.get_account_status()
        if account:
            logging.info(f"Account status:")
            varsaccount = vars(account)
            logging.info(json.dumps(varsaccount, indent=4,default=str))
            if varsaccount["total_count"] >= varsaccount["limit"]:
                logging.info("Account status: limit reached")
                return objects
        else:
            logging.info("No account status available.")
            logging.info(viesapi.get_last_error())
                
        for obj in objects:
            logging.info(f"Validating VAT_ID: {obj.value}")
            result = viesapi.get_vies_data(obj.value)
            resultvars = vars(result)
            logging.info(json.dumps(resultvars, indent=4, default=str))
            if resultvars["valid"] is False:
                obj.additional_information = ""
                obj.status = "check"
                obj.status_message = "Invalid VAT ID (API check)"
            else:
                trader_info = {key: value for key, value in resultvars.items() if key.startswith("trader") or key in ["country_code","source","vat_number"]}
                obj.additional_information = json.dumps(trader_info, indent=4, default=str)
                obj.status = "ok"
                obj.status_message = ""
            obj.last_visited = datetime.now()

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
