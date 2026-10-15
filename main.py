
import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def normalize_key(key):
    key = key.strip()

    if key == "NUM_WORKERS":
        return "workers"

    if key.startswith("APP_"):
        key = key[4:]

    return key.lower()


def coerce(key, value):
    if key in ("port", "workers"):
        return int(value)

    if key == "debug":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {
            "true", "1", "yes", "on"
        }

    return str(value)


def apply_layer(config, values):
    for raw_key, value in values.items():
        if value is None:
            continue

        key = normalize_key(raw_key)
        config[key] = coerce(key, value)


@app.get("/effective-config")
def effective_config(
    set: list[str] | None = Query(default=None)
):
    config = DEFAULTS.copy()

    # Layer 2: environment-specific YAML
    environment = os.environ.get("APP_ENV", "development")
    yaml_path = BASE_DIR / f"config.{environment}.yaml"

    if yaml_path.exists():
        with yaml_path.open(encoding="utf-8") as f:
            values = yaml.safe_load(f) or {}
        apply_layer(config, values)

    # Layer 3: .env file
    apply_layer(config, dotenv_values(BASE_DIR / ".env"))

    # Layer 4: operating system environment variables
    os_values = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("APP_") and key != "APP_ENV"
    }
    apply_layer(config, os_values)

    # Layer 5: query-string overrides
    for item in set or []:
        if "=" not in item:
            continue

        raw_key, value = item.split("=", 1)
        key = normalize_key(raw_key)
        config[key] = coerce(key, value)

    # Never expose the actual secret
    config["api_key"] = "****"

    return config
