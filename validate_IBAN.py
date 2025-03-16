
from typing import List

from model import ValidationObject


class validate_IBAN:
    
    def validate(self, objects: List[ValidationObject])->List[ValidationObject]:
        return objects