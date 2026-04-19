from datetime import datetime
from pydantic import BaseModel


# Hinweis:
# Diese Modelle sind nur ein möglicher Startpunkt für die Übung.
# Ihr dürft Felder ergänzen, umbenennen oder weitere Modelle anlegen.


class DeviceCreate(BaseModel):
    serial_number: str
    inventory_number: str
    device_type_id: int
    location_id: int
    status: str = "available"
    is_loanable: bool = True


class AssignmentCreate(BaseModel):
    device_id: int
    person_id: int
    issued_at: datetime | None = None
    due_at: datetime | None = None
    note: str | None = None


class AssignmentReturn(BaseModel):
    returned_at: datetime | None = None

