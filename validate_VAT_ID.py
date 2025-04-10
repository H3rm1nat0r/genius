import configparser
from datetime import datetime
import time
import json
import logging
from typing import List
import re
from viesapi import VIESAPIClient, Error

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

        # initialize VIES API client
        config = configparser.ConfigParser()
        config.read("config.ini")
        viesapicredentials = config["viesapi"]
        viesapi = VIESAPIClient(
            viesapicredentials["Identifier"], viesapicredentials["Key"]
        )

        # check if we have reached the limit of API calls
        # if yes, return the objects with status "check"
        # if no, continue with the validation
        account = viesapi.get_account_status()
        if account:
            logging.info(f"Account status:")
            varsaccount = vars(account)
            logging.info(json.dumps(varsaccount, indent=4, default=str))
            if varsaccount["total_count"] >= varsaccount["limit"]:
                logging.info("Account status: limit reached")
                return objects
        else:
            logging.info("No account status available.")
            logging.info(viesapi.get_last_error())

        # setup the list of VATIDs to be checked
        vat_ids = [obj.value for obj in objects]

        # call bulk check
        token = viesapi.get_vies_data_async(vat_ids)

        # wait for the batch to be processed
        while True:
            result = viesapi.get_vies_data_async_result(token)
            if result:
                # Batch result is ready
                logging.info("Batch result is ready.")
                break

            # Check for errors
            if viesapi.get_last_error_code() != Error.BATCH_PROCESSING:
                logging.error(
                    f"Error: {viesapi.get_last_error()} (code: {viesapi.get_last_error_code()})"
                )
                return objects

            # Batch is still processing, wait for 30 seconds
            logging.info("Batch is still processing, waiting...")
            time.sleep(1)

        # Process the batch result
        resultvars = vars(result)
        logging.info(json.dumps(resultvars, indent=4, default=str))
        numbers = resultvars["numbers"]
        if not numbers:
            logging.info("No numbers found in the batch result.")
            return objects
        if resultvars["errors"]:
            logging.error(f"Batch result error: {resultvars['errors']}")
            return objects

        # Update the objects with the batch result
        for number in numbers:
            viesdata = vars(number)
            country_code = viesdata["country_code"]
            vat_id = viesdata["vat_number"]

            for obj in objects:
                if obj.value == f"{country_code}{vat_id}":
                    obj.last_visited = datetime.now()
                    if viesdata["valid"] is False:
                        obj.additional_information = ""
                        obj.status = "check"
                        obj.status_message = "Invalid VAT ID (API check)"
                    else:
                        trader_info = {
                            key: value
                            for key, value in viesdata.items()
                            if key.startswith("trader")
                            or key in ["country_code", "source", "vat_number"]
                        }
                        obj.additional_information = json.dumps(
                            trader_info, indent=4, default=str
                        )
                        obj.status = "ok"
                        obj.status_message = ""
                    break

        return objects

    def is_valid_vat_syntax(self, vat_id: str) -> bool:
        """
        Checks if the given VAT ID has a valid syntax.

        Args:
            vat_id (str): The VAT ID to be checked.

        Returns:
            bool: True if the VAT ID has a valid syntax, False otherwise.
        """
        vat_id = vat_id.strip().upper()

        regex = re.compile(
            r"^("
            r"ATU\d{8}|"
            r"BE0\d{9}|"
            r"BG\d{9,10}|"
            r"CY\d{8}[A-Z]|"
            r"CZ\d{8,10}|"
            r"DE\d{9}|"
            r"DK\d{8}|"
            r"EE\d{9}|"
            r"EL\d{9}|"
            r"ES[A-Z0-9]\d{7}[A-Z0-9]|"
            r"FI\d{8}|"
            r"FR[A-Z0-9]{2}\d{9}|"
            r"HR\d{11}|"
            r"HU\d{8}|"
            r"IE\d{7}[A-W]|"
            r"IE\d{7}[A-W][A-I]|"
            r"IT\d{11}|"
            r"LT(\d{9}|\d{12})|"
            r"LU\d{8}|"
            r"LV\d{11}|"
            r"MT\d{8}|"
            r"NL\d{9}B\d{2}|"
            r"PL\d{10}|"
            r"PT\d{9}|"
            r"RO\d{2,10}|"
            r"SE\d{12}|"
            r"SI\d{8}|"
            r"SK\d{10}"
            r")$"
        )

        return regex.match(vat_id) is not None

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

        country_code = country_code.upper()
        if country_code == "DE":
            return self._is_valid_german_vat_checksum(number)
        elif country_code == "AT":
            return self._is_valid_austrian_vat_checksum(number)
        elif country_code == "CH":
            return self._is_valid_swiss_vat_checksum(number)
        elif country_code == "IT":
            return self._is_valid_italian_vat_checksum(number)
        elif country_code == "NL":
            return self._is_valid_dutch_vat_checksum(number)
        elif country_code == "BE":
            return self._is_valid_belgian_vat_checksum(number)
        elif country_code == "SE":
            return self._is_valid_swedish_vat_checksum(number)
        else:
            # Default to true for countries without official checksum validation
            return True

    def _is_valid_german_vat_checksum(self, number: str) -> bool:
        """
        Validates the checksum for a German VAT ID.

        Args:
            number (str): The VAT ID number part (without country code).

        Returns:
            bool: True if the checksum is valid, False otherwise.
        """
        if len(number) != 9 or not number.isdigit():
            return False

        product = 10
        for i in range(8):
            sum_ = (int(number[i]) + product) % 10
            if sum_ == 0:
                sum_ = 10
            product = (2 * sum_) % 11

        check = 11 - product
        if check == 10:
            check = 0
        return check == int(number[8])

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

        digits = [int(d) for d in number[1:8]]
        checksum = int(number[8])
        weights = [1, 2, 1, 2, 1, 2, 1]
        total = 0

        for i in range(7):
            product = digits[i] * weights[i]
            total += product if product < 10 else (product // 10 + product % 10)

        checkdigit = (10 - (total + 4) % 10) % 10
        return checkdigit == checksum

    def _is_valid_swiss_vat_checksum(self, number: str) -> bool:
        """
        Validates the checksum for a Swiss VAT ID.

        Args:
            number (str): The VAT ID number part (without country code).

        Returns:
            bool: True if the checksum is valid, False otherwise.
        """
        if len(number) != 9 or not number.isdigit():
            return False

        weights = [5, 4, 3, 2, 7, 6, 5, 4]
        total = sum(int(number[i]) * weights[i] for i in range(8))
        remainder = total % 11
        check = 11 - remainder
        if check == 10:
            return False
        elif check == 11:
            check = 0
        return check == int(number[8])

    def _is_valid_belgian_vat_checksum(self,number: str) -> bool:
        if len(number) != 10 or not number.startswith("0") or not number.isdigit():
            return False

        base = int(number[1:9])
        checksum = int(number[8:10])
        calculated = 97 - (base % 97)
        return calculated == checksum
    
    
    def _is_valid_italian_vat_checksum(self,number: str) -> bool:
        if len(number) != 11 or not number.isdigit():
            return False

        s = 0
        for i in range(10):
            n = int(number[i])
            if i % 2 == 0:
                s += n
            else:
                n = 2 * n
                s += n if n < 10 else n - 9
        checkdigit = (10 - (s % 10)) % 10
        return checkdigit == int(number[10])    
    
    def _is_valid_dutch_vat_checksum(self,number: str) -> bool:
        if not number.endswith("B01") and not number.endswith("B02"):
            return True  # Only check for standard formats

        digits = number[:9]
        if not digits.isdigit():
            return False

        weights = list(range(9, 0, -1))
        total = sum(int(d) * w for d, w in zip(digits, weights))
        return total % 11 == 0    
    
    def _is_valid_swedish_vat_checksum(self,number: str) -> bool:
        if len(number) != 12 or not number.isdigit():
            return False

        digits = number[:10]
        total = 0
        for i, digit in enumerate(digits):
            n = int(digit)
            if i % 2 == 0:
                n *= 2
            total += n if n < 10 else (n // 10 + n % 10)

        checkdigit = (10 - (total % 10)) % 10
        return checkdigit == int(number[10])    