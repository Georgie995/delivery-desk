"""Module 3: delivery-desk.toml is checked before anything runs. Needs none of the other repos."""

import re

import pytest

from delivery_desk import cli
from delivery_desk.settings import SettingsError, load_settings


@pytest.fixture
def hub(tmp_path):
    """Just enough of a delivery-ops-hub folder and settings file for the checks to pass."""
    (tmp_path / "hub" / "delivery_ops_hub").mkdir(parents=True)
    config = tmp_path / "hub" / "ops-hub.toml"
    config.write_text(f'reports_dir = "{(tmp_path / "reports").as_posix()}"\n', encoding="utf-8")
    return tmp_path / "hub", config


def write(tmp_path, text):
    path = tmp_path / "delivery-desk.toml"
    path.write_text(text, encoding="utf-8")
    return path


def basic(hub):
    return f'ops_hub_path = "{hub[0].as_posix()}"\nops_hub_config = "{hub[1].as_posix()}"\n'


def test_good_settings_give_the_reports_folder_from_delivery_ops_hub(tmp_path, hub):
    settings = load_settings(write(tmp_path, basic(hub)))
    assert settings["reports_dir"] == str(tmp_path / "reports")
    assert settings["ai_triage_python"] is None


@pytest.mark.parametrize("text, message", [
    ("", "missing setting(s): ops_hub_path, ops_hub_config"),
    ("ops_hub_pth = 'x'\n", "unknown setting(s): ops_hub_pth"),
    ("ops_hub_path = \n", "not valid TOML"),
])
def test_wrong_settings_are_named(tmp_path, text, message):
    with pytest.raises(SettingsError, match=re.escape(message)):
        load_settings(write(tmp_path, text))


def test_a_missing_settings_file_points_to_the_example(tmp_path):
    with pytest.raises(SettingsError, match="copy delivery-desk.example.toml"):
        load_settings(tmp_path / "delivery-desk.toml")


def test_ops_hub_path_must_be_the_delivery_ops_hub_folder(tmp_path, hub):
    text = basic(hub).replace(hub[0].as_posix(), (tmp_path / "elsewhere").as_posix())
    with pytest.raises(SettingsError, match="delivery-ops-hub not found"):
        load_settings(write(tmp_path, text))


def test_the_ops_hub_settings_must_exist_and_say_where_reports_go(tmp_path, hub):
    hub[1].write_text('webhook_url = "http://localhost:5678"\n', encoding="utf-8")
    with pytest.raises(SettingsError, match="reports_dir"):
        load_settings(write(tmp_path, basic(hub)))
    hub[1].unlink()
    with pytest.raises(SettingsError, match="ops_hub_config"):
        load_settings(write(tmp_path, basic(hub)))


def test_ai_triage_needs_both_settings_or_neither(tmp_path, hub):
    with pytest.raises(SettingsError, match="both ai_triage_path and ai_triage_python, or neither"):
        load_settings(write(tmp_path, basic(hub) + 'ai_triage_python = "C:/x/python.exe"\n'))


def test_check_with_bad_settings_stops_with_exit_3_before_running_anything(tmp_path, capsys):
    assert cli.main(["--config", str(tmp_path / "missing.toml"), "check", str(tmp_path), "--manifest", "m"]) == 3
    assert "delivery-desk.example.toml" in capsys.readouterr().err
