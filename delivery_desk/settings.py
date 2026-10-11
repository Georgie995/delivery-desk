"""Settings from delivery-desk.toml, checked before anything runs.

No secrets here: the webhook secret and the AI key stay in environment variables, exactly as
delivery-ops-hub and ai-triage already expect.
"""

import tomllib
from pathlib import Path

REQUIRED = ("ops_hub_path", "ops_hub_config")
OPTIONAL = ("ai_triage_path", "ai_triage_python")


class SettingsError(Exception):
    """delivery-desk can't run with these settings (exit code 3, as in delivery-ops-hub)."""


def load_settings(path):
    path = Path(path)
    if not path.exists():
        raise SettingsError(f"settings file {path} not found (copy delivery-desk.example.toml to start)")
    data = _toml(path)

    unknown = set(data) - set(REQUIRED) - set(OPTIONAL)
    if unknown:
        raise SettingsError(f"{path}: unknown setting(s): {', '.join(sorted(unknown))}")
    missing = [key for key in REQUIRED if not data.get(key)]
    if missing:
        raise SettingsError(f"{path}: missing setting(s): {', '.join(missing)}")
    if not (Path(data["ops_hub_path"]) / "delivery_ops_hub").is_dir():
        raise SettingsError(f"{path}: delivery-ops-hub not found at ops_hub_path = {data['ops_hub_path']}")
    if not Path(data["ops_hub_config"]).is_file():
        raise SettingsError(f"{path}: ops_hub_config = {data['ops_hub_config']} doesn't exist")
    # Reports go wherever delivery-ops-hub sends them, so read that rather than repeat it here.
    reports_dir = _toml(Path(data["ops_hub_config"])).get("reports_dir")
    if not reports_dir:
        raise SettingsError(f"{data['ops_hub_config']} has no reports_dir, so delivery-desk can't find reports")
    if bool(data.get("ai_triage_path")) != bool(data.get("ai_triage_python")):
        raise SettingsError(f"{path}: set both ai_triage_path and ai_triage_python, or neither")

    return {**{key: None for key in OPTIONAL}, **data, "reports_dir": str(Path(reports_dir))}


def _toml(path):
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise SettingsError(f"settings file {path} is not valid TOML: {error}") from error
