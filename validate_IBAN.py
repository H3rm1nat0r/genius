from typing import List
import logging
import re
from model import ValidationObject
from datetime import datetime

class validate_IBAN:
    """
    A class to validate IBAN numbers by checking their syntax and checksum.
    """

    def validate(self, objects: List[ValidationObject]) -> List[ValidationObject]:
        """
        Validates a list of ValidationObject instances by checking IBAN syntax and checksum.
        Updates the status field of each ValidationObject.

        Args:
            objects (List[ValidationObject]): A list of ValidationObject instances to be validated.

        Returns:
            List[ValidationObject]: The list of ValidationObject instances with updated status fields.
        """
        for obj in objects:
            logging.info(f"Validating IBAN: {obj.value}")
            obj.last_visited = datetime.now()
            iban = obj.value

            if not self.is_valid_iban_syntax(iban):
                obj.status = "check"
                obj.status_message = "Invalid IBAN syntax"
                continue

            if not self.is_valid_iban_checksum(iban):
                obj.status = "check"
                obj.status_message = "Invalid IBAN checksum"
                continue

            obj.status = "ok"
            obj.status_message = ""

        return objects

    def is_valid_iban_syntax(self, iban: str) -> bool:
        """
        Checks if the given IBAN has a valid syntax.

        Args:
            iban (str): The IBAN to be checked.

        Returns:
            bool: True if the IBAN has a valid syntax, False otherwise.
        """
        regex = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{1,30}$", re.IGNORECASE)
        return re.match(regex, iban) is not None

    def is_valid_iban_checksum(self, iban: str) -> bool:
        """
        Checks if the given IBAN has a valid checksum.

        Args:
            iban (str): The IBAN to be checked.

        Returns:
            bool: True if the IBAN has a valid checksum, False otherwise.
        """
        # Move the four initial characters to the end of the string
        rearranged_iban = iban[4:] + iban[:4]
        # Replace each letter in the string with two digits
        numeric_iban = ''.join(str(int(ch, 36)) for ch in rearranged_iban)
        # Interpret the string as a decimal integer and compute the remainder of that number on division by 97
        return int(numeric_iban) % 97 == 1
