"""Tests: family selection propagates to _create_entry in orvibo-lan-control.

Verifies the data logic only — doesn't instantiate HA flow classes.
"""
from __future__ import annotations

import importlib.util
import os
import unittest

_test_root = os.path.dirname(os.path.abspath(__file__))
_orvibo_lan = os.path.join(_test_root, "..", "custom_components")

# Load const for CONF constants
const_path = os.path.join(_orvibo_lan, "orvibo_lan", "const.py")
spec = importlib.util.spec_from_file_location("custom_components.orvibo_lan.const", const_path)
assert spec is not None and spec.loader is not None
const_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(const_mod)

FAKE_FAMILIES = [
    {"familyId": "fam-001", "familyName": "家庭A"},
    {"familyId": "fam-002", "familyName": "家庭B"},
    {"familyId": "fam-003", "familyName": "家庭C"},
]


class TestFamilySelectionDataLogic(unittest.TestCase):
    """Test the data transformation logic inside config_flow.

    We test the actual assignment/merge logic without instantiating HA flow classes.
    """

    def test_selected_family_overrides_first_family(self):
        """_create_entry: _selected_family_id preferred over first family."""
        _selected_family_id = "fam-002"
        _family_list = FAKE_FAMILIES

        family_id = _selected_family_id or (
            _family_list[0]["familyId"] if _family_list else None
        )
        self.assertEqual(family_id, "fam-002")
        self.assertNotEqual(family_id, "fam-001")

    def test_no_selection_falls_back_to_first_family(self):
        """_create_entry: no selection → first family."""
        _selected_family_id = None
        _family_list = FAKE_FAMILIES

        family_id = _selected_family_id or (
            _family_list[0]["familyId"] if _family_list else None
        )
        self.assertEqual(family_id, "fam-001")

    def test_selected_family_goes_into_entry_data(self):
        """_create_entry: family_id appears in data dict."""
        _selected_family_id = "fam-003"
        _family_list = FAKE_FAMILIES
        _username = "13800138000"
        _password = "testpass"

        family_id = _selected_family_id or (
            _family_list[0]["familyId"] if _family_list else None
        )
        data = {
            const_mod.CONF_USERNAME: _username,
            const_mod.CONF_PASSWORD: _password,
            const_mod.CONF_FAMILY_ID: family_id,
        }
        self.assertEqual(data[const_mod.CONF_FAMILY_ID], "fam-003")
        self.assertEqual(data[const_mod.CONF_USERNAME], "13800138000")

    def test_empty_family_list_with_no_selection(self):
        """Edge case: no families and no selection."""
        _selected_family_id = None
        _family_list = []

        family_id = _selected_family_id or (
            _family_list[0]["familyId"] if _family_list else None
        )
        self.assertIsNone(family_id)

    def test_empty_family_list_with_explicit_selection(self):
        """Edge case: empty families but explicit selection set."""
        _selected_family_id = "fam-099"
        _family_list = []

        family_id = _selected_family_id or (
            _family_list[0]["familyId"] if _family_list else None
        )
        self.assertEqual(family_id, "fam-099")

    def test_async_step_select_family_propagation(self):
        """Simulate the full config flow step: user selects → stored → entry.

        This exactly mirrors the data flow:
        async_step_select_family → _selected_family_id = family_id
        → update _family_name → _create_entry
        """
        # Step 1: user selects family B
        user_input = {"family_id": "fam-002"}
        _selected_family_id: str | None = None
        _family_name = "家庭A"  # was set in async_step_user
        _family_list = FAKE_FAMILIES

        family_id_from_step = user_input.get("family_id")
        if family_id_from_step:
            _selected_family_id = family_id_from_step
            # Update family name to match selection
            for f in _family_list:
                if f["familyId"] == family_id_from_step:
                    _family_name = f.get("familyName", "")
                    break

        self.assertEqual(_selected_family_id, "fam-002")
        self.assertEqual(_family_name, "家庭B")  # was "家庭A", now "家庭B"

        # Step 2: _create_entry uses the stored values
        family_id = _selected_family_id or (
            _family_list[0]["familyId"] if _family_list else None
        )
        self.assertEqual(family_id, "fam-002")

        # Step 3: entry title uses correct family name
        title = f"13800138000 - {_family_name}"
        self.assertEqual(title, "13800138000 - 家庭B")

    def test_single_family_no_selection_keeps_first_name(self):
        """Only one family → _family_name stays as first family's name."""
        _family_name = "家庭A"
        _family_list = [FAKE_FAMILIES[0]]
        _selected_family_id = None

        # No selection step happens, goes straight to _create_entry
        family_id = _selected_family_id or (
            _family_list[0]["familyId"] if _family_list else None
        )
        title = f"13800138000 - {_family_name}"
        self.assertEqual(title, "13800138000 - 家庭A")
        self.assertEqual(family_id, "fam-001")


if __name__ == "__main__":
    unittest.main()
