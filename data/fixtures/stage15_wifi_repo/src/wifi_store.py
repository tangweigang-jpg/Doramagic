from pathlib import Path
import json

STORE_PATH = Path.home() / ".wifi-tool" / "profiles.json"


def save_profile(ssid: str, password: str) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ssid": ssid, "password": password}
    STORE_PATH.write_text(json.dumps(payload), encoding="utf-8")


def list_profiles() -> dict:
    if not STORE_PATH.exists():
        return {}
    return json.loads(STORE_PATH.read_text(encoding="utf-8"))
