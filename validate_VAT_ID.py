
from datetime import datetime
from typing import List

from model import ValidationObject


class validate_VAT_ID:
    
    def validate(self, objects: List[ValidationObject])->List[ValidationObject]:
        objects[0].last_visit = datetime.now()
        return objects