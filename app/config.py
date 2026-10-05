"""Small, validated configuration for the Phase 2 HTTP dependency."""

import os

from pydantic import AnyHttpUrl, BaseModel, Field


class Settings(BaseModel):
    payment_base_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8001")
    payment_timeout_seconds: float = Field(default=2.0, gt=0, le=30)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls.model_validate(
            {
                "payment_base_url": os.getenv(
                    "PAYMENT_BASE_URL", "http://127.0.0.1:8001"
                ),
                "payment_timeout_seconds": os.getenv("PAYMENT_TIMEOUT_SECONDS", "2"),
            }
        )
