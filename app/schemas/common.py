from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TimestampedModel(BaseModel):
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
