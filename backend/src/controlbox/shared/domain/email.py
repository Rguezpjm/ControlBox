import re
from typing import Annotated

from pydantic import BeforeValidator, Field

# Accepts panel/local install addresses (e.g. admin@controlbox.local) that strict EmailStr rejects.
_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z0-9.-]+$")


def normalize_panel_email(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Invalid email address")
    email = value.strip().lower()
    if not _EMAIL_PATTERN.match(email):
        raise ValueError("Invalid email address")
    return email


PanelEmail = Annotated[str, BeforeValidator(normalize_panel_email), Field(max_length=255)]

TENANT_SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
