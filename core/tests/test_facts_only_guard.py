"""Tests for the facts-only guard and the plain database search it relies
on.

These tests do not call the real AI. The "AI reply" in each guard test is
written by the test itself, to prove the guard catches an invented price
or bedroom count without needing Groq, an internet connection, or a real
API key.
"""
from decimal import Decimal

from django.test import TestCase

from core.guards import FACTS_ONLY_SAFE_REPLY, check_facts_only
from core.models import Property
from core.property_search import find_matching_properties, properties_as_facts


class FindMatchingPropertiesTests(TestCase):
    def setUp(self):
        self.flat = Property.objects.create(
            title="[SAMPLE DATA] 2-Bedroom Flat in Test Gardens",
            city="Testville",
            area="Test Gardens",
            type=Property.FLAT,
            bedrooms=2,
            price=Decimal("5000000"),
            currency="PKR",
            status=Property.AVAILABLE,
            description="Invented sample data for testing.",
        )
        self.house = Property.objects.create(
            title="[SAMPLE DATA] 4-Bedroom House in Test Hills",
            city="Testville",
            area="Test Hills",
            type=Property.HOUSE,
            bedrooms=4,
            price=Decimal("15000000"),
            currency="PKR",
            status=Property.AVAILABLE,
            description="Invented sample data for testing.",
        )
        self.other_city = Property.objects.create(
            title="[SAMPLE DATA] 2-Bedroom Flat in Other City",
            city="Othertown",
            area="Somewhere",
            type=Property.FLAT,
            bedrooms=2,
            price=Decimal("4000000"),
            currency="AED",
            status=Property.AVAILABLE,
            description="Invented sample data for testing.",
        )

    def test_filters_by_city(self):
        results = find_matching_properties(city="testville")
        self.assertCountEqual(results, [self.flat, self.house])

    def test_filters_by_bedrooms(self):
        results = find_matching_properties(bedrooms=2)
        self.assertCountEqual(results, [self.flat, self.other_city])

    def test_filters_by_max_price(self):
        results = find_matching_properties(max_price=Decimal("5000000"))
        self.assertCountEqual(results, [self.flat, self.other_city])

    def test_combining_filters(self):
        results = find_matching_properties(city="Testville", bedrooms=2, max_price=Decimal("6000000"))
        self.assertEqual(results, [self.flat])

    def test_properties_as_facts_lists_every_match(self):
        text = properties_as_facts([self.flat])
        self.assertIn("2 bedroom flat", text)
        self.assertIn("5000000", text)

    def test_properties_as_facts_handles_no_matches(self):
        self.assertIn("No matching properties", properties_as_facts([]))


class CheckFactsOnlyTests(TestCase):
    def setUp(self):
        self.flat = Property.objects.create(
            title="[SAMPLE DATA] 2-Bedroom Flat in Test Gardens",
            city="Testville",
            area="Test Gardens",
            type=Property.FLAT,
            bedrooms=2,
            price=Decimal("5000000"),
            currency="PKR",
            status=Property.AVAILABLE,
            description="Invented sample data for testing.",
        )
        self.matches = [self.flat]

    def test_good_reply_passes_through(self):
        reply = (
            "We have a 2-bedroom flat in Test Gardens, Testville, priced "
            "at 5,000,000 PKR."
        )

        blocked, safe_reply = check_facts_only(reply, self.matches)

        self.assertFalse(blocked)
        self.assertIsNone(safe_reply)

    def test_reply_with_an_invented_price_is_blocked(self):
        # The real price is 5,000,000 — this reply invents a different one.
        reply = (
            "We have a 2-bedroom flat in Test Gardens, Testville, priced "
            "at 6,500,000 PKR."
        )

        blocked, safe_reply = check_facts_only(reply, self.matches, session_id="facts-session")

        self.assertTrue(blocked)
        self.assertEqual(safe_reply, FACTS_ONLY_SAFE_REPLY)

    def test_reply_with_an_invented_bedroom_count_is_blocked(self):
        # The real listing has 2 bedrooms — this reply says 3.
        reply = "We have a 3-bedroom flat in Test Gardens for 5,000,000 PKR."

        blocked, safe_reply = check_facts_only(reply, self.matches, session_id="facts-session")

        self.assertTrue(blocked)
        self.assertEqual(safe_reply, FACTS_ONLY_SAFE_REPLY)

    def test_mismatch_is_logged(self):
        reply = "We have a 2-bedroom flat for 9,999,999 PKR."

        with self.assertLogs("propdesk.guards", level="WARNING") as captured:
            check_facts_only(reply, self.matches, session_id="abc777")

        log_line = captured.output[0]
        self.assertIn("abc777", log_line)
        self.assertIn("facts_only", log_line)

    def test_good_reply_is_not_logged(self):
        reply = "We have a 2-bedroom flat in Test Gardens for 5,000,000 PKR."

        with self.assertNoLogs("propdesk.guards", level="WARNING"):
            check_facts_only(reply, self.matches, session_id="abc777")
