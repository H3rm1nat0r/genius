from dataclasses import dataclass
from datetime import datetime


@dataclass
class ValidationObject:
    classification: str
    value: str
    status: str
    last_visited: datetime