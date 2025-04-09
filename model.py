from dataclasses import dataclass
from datetime import datetime


@dataclass
class ValidationObject:
    classification: str
    value: str
    status: str
    status_message: str
    last_visited: datetime
    additional_information: str 
