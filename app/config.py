"""Validated configuration for HTTP and database dependencies."""

import os

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://shopsphere:shopsphere_local@127.0.0.1:5432/shopsphere"
    )
    payment_base_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8001")
    payment_timeout_seconds: float = Field(default=2.0, gt=0, le=30)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            valid = url.drivername == "postgresql+psycopg" and url.host and url.database
        except ArgumentError:
            valid = False
        if not valid:
            raise ValueError(
                "DATABASE_URL must use postgresql+psycopg and include host/database"
            )
        return value

    @classmethod
    def from_env(cls) -> "Settings":
        return cls.model_validate(
            {
                "database_url": os.getenv(
                    "DATABASE_URL",
                    cls.model_fields["database_url"].default.get_secret_value(),
                ),
                "payment_base_url": os.getenv(
                    "PAYMENT_BASE_URL", "http://127.0.0.1:8001"
                ),
                "payment_timeout_seconds": os.getenv("PAYMENT_TIMEOUT_SECONDS", "2"),
            }
        )
