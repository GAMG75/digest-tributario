import os
import yaml
from dotenv import load_dotenv

load_dotenv()


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    config["anthropic_api_key"] = os.environ["ANTHROPIC_API_KEY"]
    config["gmail_user"] = os.environ["GMAIL_USER"]
    config["gmail_password"] = os.environ["GMAIL_APP_PASSWORD"]

    recipients_env = os.environ.get("RECIPIENTS", "")
    if recipients_env:
        config["recipients"] = [r.strip() for r in recipients_env.split(",") if r.strip()]
    elif not config.get("recipients"):
        config["recipients"] = []

    return config
