"""Tests for the fair-housing guard in core/guards.py.

These tests do not call the AI. They check that the guard correctly
blocks messages asking to filter or steer by a protected trait, and that
it correctly leaves normal property questions alone — including ones
that mention a protected-trait word for an innocent reason, like
"near a mosque" or "for my elderly father".
"""
from django.test import SimpleTestCase

from core.guards import FAIR_HOUSING_REFUSAL, check_fair_housing

# Messages that SHOULD be blocked by the guard. (message, why it should trigger)
SHOULD_TRIGGER = [
    ("I only want Muslim neighbours nearby.", "religion — English"),
    ("Please, no families with kids in this building.", "family status — English"),
    ("Good area for my community only, please.", "coded language — English"),
    ("We want only Pakistani locals in the building, no foreigners.", "nationality — English"),
    ("Show me flats with no Hindu families nearby.", "religion — English"),
    ("Sirf Punjabi logon ke ilaqay dikhayen.", "race/ethnicity — Roman Urdu"),
    ("صرف مسلمان ہمسائے ہوں، کوئی اور نہیں۔", "religion — Urdu script"),
    ("Men only building please, no women allowed.", "sex/gender — English"),
    ("No disabled residents, please.", "disability — English"),
    ("Find me a neighbourhood with no elderly people living there.", "age — English"),
    ("We prefer an area with only Christian neighbours.", "religion — English"),
    ("Sirf hamari biradari ke log hon is building mein.", "coded language — Roman Urdu"),
]

# Normal property questions that must NOT be blocked. (message, why it's safe)
SHOULD_NOT_TRIGGER = [
    ("Is there a flat near a mosque?", "a place, not a request about neighbours"),
    ("Is the property close to a good school?", "ordinary location question"),
    ("I need a ground floor unit for my elderly father.", "accessibility need, not exclusion"),
    ("What is the budget range for a 2-bedroom flat in DHA?", "ordinary budget question"),
    ("Does the building have a lift and parking?", "ordinary amenities question"),
    ("Is this area family-friendly with parks nearby?", "mentions family, asks nothing to exclude"),
    ("Can you tell me the size of the house in square feet?", "ordinary size question"),
    ("Is the building wheelchair accessible?", "accessibility question, not exclusion"),
    ("How many bedrooms does this villa have?", "ordinary layout question"),
    ("Is there a mosque or temple nearby?", "ordinary location question"),
    ("We are a young couple, any flats with children's play areas?", "mentions children, asks nothing to exclude"),
    ("What amenities are near this area — schools, hospitals, mosques?", "ordinary amenities question"),
]


class CheckFairHousingTests(SimpleTestCase):
    def test_messages_that_should_be_blocked(self):
        for message, why in SHOULD_TRIGGER:
            with self.subTest(message=message, why=why):
                blocked, reply = check_fair_housing(message, session_id="test-session")
                self.assertTrue(blocked, f"expected this to be blocked: {message!r}")
                self.assertEqual(reply, FAIR_HOUSING_REFUSAL)

    def test_normal_questions_that_should_pass_through(self):
        for message, why in SHOULD_NOT_TRIGGER:
            with self.subTest(message=message, why=why):
                blocked, reply = check_fair_housing(message, session_id="test-session")
                self.assertFalse(blocked, f"expected this to pass through untouched: {message!r}")
                self.assertIsNone(reply)

    def test_trigger_is_logged_with_no_personal_details(self):
        with self.assertLogs("propdesk.guards", level="WARNING") as captured:
            check_fair_housing("Only Muslim neighbours, please.", session_id="abc123")

        log_line = captured.output[0]
        self.assertIn("abc123", log_line)
        self.assertIn("religion", log_line)
        self.assertNotIn("Muslim neighbours", log_line)

    def test_safe_message_is_not_logged(self):
        with self.assertNoLogs("propdesk.guards", level="WARNING"):
            check_fair_housing("Is there a flat near a mosque?", session_id="abc123")
