"""Tests for the AI-disclosure guard in core/guards.py.

These tests do not call the AI or Groq. They only check that the notice
is added on the first reply of a chat, and left out of every later reply,
as the PropDesk rulebook requires (disclosure must be guaranteed by code,
not left to the AI to remember).
"""
from django.test import SimpleTestCase

from core.guards import DISCLOSURE_NOTICE, add_disclosure


class AddDisclosureTests(SimpleTestCase):
    def test_notice_appears_on_first_reply(self):
        history = [{"role": "system", "content": "instructions"}]
        reply = "Hello, how can I help?"

        result = add_disclosure(reply, history)

        self.assertIn(DISCLOSURE_NOTICE, result)
        self.assertIn(reply, result)

    def test_notice_appears_when_there_is_no_history_yet(self):
        result = add_disclosure("Hi there", [])

        self.assertIn(DISCLOSURE_NOTICE, result)

    def test_notice_does_not_appear_on_a_later_reply(self):
        history = [
            {"role": "system", "content": "instructions"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "Hello, how can I help?"},
            {"role": "user", "content": "what about prices?"},
        ]
        reply = "Let me check that for you."

        result = add_disclosure(reply, history)

        self.assertEqual(result, reply)
        self.assertNotIn(DISCLOSURE_NOTICE, result)
