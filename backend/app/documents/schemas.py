"""What the API returns when listing a booking's documents."""
from datetime import datetime

from pydantic import BaseModel


class DocumentLinkOut(BaseModel):
    type: str
    title: str
    number: str
    issued_at: datetime
    url: str       # opens the document; anyone with the link can view it, so share it only with the client