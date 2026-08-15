"""
Unit tests for the security gate — the most important part of this system.
Run: python -m pytest tests/test_security.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from core.security import SecurityGate
from core.errors import ConfirmationRequiredError, ToolValidationError


def test_safe_app_name_passes():
    gate = SecurityGate()
    gate.validate("open_application", {"app_name": "chrome"})  # should not raise


def test_unsafe_app_name_rejected():
    gate = SecurityGate()
    with pytest.raises(ToolValidationError):
        gate.validate("open_application", {"app_name": "chrome; rm -rf /"})


def test_bad_url_rejected():
    gate = SecurityGate()
    with pytest.raises(ToolValidationError):
        gate.validate("open_url", {"url": "javascript:alert(1)"})


def test_good_url_passes():
    gate = SecurityGate()
    gate.validate("open_url", {"url": "https://example.com"})


def test_volume_out_of_range_rejected():
    gate = SecurityGate()
    with pytest.raises(ToolValidationError):
        gate.validate("control_volume", {"action": "set", "level": 150})


def test_delete_requires_confirmation():
    gate = SecurityGate()
    with pytest.raises(ConfirmationRequiredError):
        gate.check("delete_path", {"path": "C:/Users/test/Desktop/junk"})
    assert gate.has_pending_confirmation


def test_delete_protected_path_rejected_even_with_confirmation():
    gate = SecurityGate()
    with pytest.raises(ToolValidationError):
        gate.check("delete_path", {"path": "C:/Windows"})


def test_confirm_and_check_approves_pending():
    gate = SecurityGate()
    try:
        gate.check("system_power", {"action": "shutdown"})
    except ConfirmationRequiredError:
        pass
    approved = gate.confirm_and_check(user_said_yes=True)
    assert approved is not None
    assert approved["tool_name"] == "system_power"


def test_confirm_and_check_declines_pending():
    gate = SecurityGate()
    try:
        gate.check("system_power", {"action": "restart"})
    except ConfirmationRequiredError:
        pass
    approved = gate.confirm_and_check(user_said_yes=False)
    assert approved is None


def test_start_project_protected_path_rejected():
    gate = SecurityGate()
    with pytest.raises(ToolValidationError):
        gate.validate("start_project", {"path": "C:/Windows"})


def test_start_project_normal_path_passes():
    gate = SecurityGate()
    gate.validate("start_project", {"path": "C:/Projects/JARVIS"})  # should not raise
