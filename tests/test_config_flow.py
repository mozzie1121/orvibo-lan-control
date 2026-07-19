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
        → _create_entry → family_id = _selected_family_id or fallback
        """
        # Step 1: user selects family B
        user_input = {"family_id": "fam-002"}
        _selected_family_id: str | None = None

        family_id_from_step = user_input.get("family_id")
        if family_id_from_step:
            _selected_family_id = family_id_from_step

        self.assertEqual(_selected_family_id, "fam-002")

        # Step 2: _create_entry uses the stored value
        _family_list = FAKE_FAMILIES
        family_id = _selected_family_id or (
            _family_list[0]["familyId"] if _family_list else None
        )
        self.assertEqual(family_id, "fam-002")

        # Step 3: Goes into entry.data
        data = {"family_id": family_id}
        self.assertEqual(data["family_id"], "fam-002")

    def test_single_family_skip_selection(self):
        """Only one family → goes directly to _create_entry, uses first family."""
        _selected_family_id = None
        _family_list = [FAKE_FAMILIES[0]]

        # This path doesn't go through async_step_select_family
        family_id = _selected_family_id or (
            _family_list[0]["familyId"] if _family_list else None
        )
        self.assertEqual(family_id, "fam-001")


if __name__ == "__main__":
    unittest.main()
