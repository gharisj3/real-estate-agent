"""Tests for the kill-switch guard in core/guards.py.

This guard reads PROPDESK_BOT_ENABLED from the real environment (set
from .env), so these tests use mock.patch.dict to set it to a known
value for each test, rather than relying on whatever is in the real
.env file.
"""
import os
from unittest import mock

from django.test import SimpleTestCase

from core.guards import BOT_OFFLINE_REPLY, check_kill_switch


class CheckKillSwitchTests(SimpleTestCase):
    @mock.patch.dict(os.environ, {"PROPDESK_BOT_ENABLED": "false"})
    def test_bot_off_blocks_every_message(self):
        blocked, reply = check_kill_switch(session_id="kill-session")

        self.assertTrue(blocked)
        self.assertEqual(reply, BOT_OFFLINE_REPLY)

    @mock.patch.dict(os.environ, {"PROPDESK_BOT_ENABLED": "FALSE"})
    def test_bot_off_is_not_case_sensitive(self):
        blocked, reply = check_kill_switch(session_id="kill-session")

        self.assertTrue(blocked)
        self.assertEqual(reply, BOT_OFFLINE_REPLY)

    @mock.patch.dict(os.environ, {"PROPDESK_BOT_ENABLED": "true"})
    def test_bot_on_passes_through(self):
        blocked, reply = check_kill_switch(session_id="kill-session")

        self.assertFalse(blocked)
        self.assertIsNone(reply)

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_missing_setting_defaults_to_on(self):
        blocked, reply = check_kill_switch(session_id="kill-session")

        self.assertFalse(blocked)
        self.assertIsNone(reply)

    @mock.patch.dict(os.environ, {"PROPDESK_BOT_ENABLED": "please turn off"})
    def test_an_unrecognised_value_defaults_to_on(self):
        # A typo in .env should never accidentally take the assistant
        # down — only the exact word "false" does that.
        blocked, reply = check_kill_switch(session_id="kill-session")

        self.assertFalse(blocked)
        self.assertIsNone(reply)

    @mock.patch.dict(os.environ, {"PROPDESK_BOT_ENABLED": "false"})
    def test_trigger_is_logged(self):
        with self.assertLogs("propdesk.guards", level="WARNING") as captured:
            check_kill_switch(session_id="kill-logging-session")

        log_line = captured.output[0]
        self.assertIn("kill_switch", log_line)
        self.assertIn("kill-logging-session", log_line)
