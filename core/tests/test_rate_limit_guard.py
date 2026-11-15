"""Tests for the per-session rate-limit guard in core/guards.py.

These tests pass a fake `now` (a plain number of seconds, not a real
clock) into check_rate_limit(), so they can prove the limit resets
after its window without actually waiting 10 real minutes.
"""
from django.core.cache import cache
from django.test import SimpleTestCase

from core.guards import (
    RATE_LIMIT_MAX_MESSAGES,
    RATE_LIMIT_REPLY,
    RATE_LIMIT_WINDOW_SECONDS,
    check_rate_limit,
)


class CheckRateLimitTests(SimpleTestCase):
    def tearDown(self):
        # Each test uses its own session id, but clear the cache anyway
        # so no state can leak between test runs.
        cache.clear()

    def test_the_limit_itself_is_twenty_messages_in_ten_minutes(self):
        self.assertEqual(RATE_LIMIT_MAX_MESSAGES, 20)
        self.assertEqual(RATE_LIMIT_WINDOW_SECONDS, 600)

    def test_the_twentieth_message_is_allowed(self):
        session_id = "rate-session-20-allowed"

        for i in range(RATE_LIMIT_MAX_MESSAGES):  # messages 1 to 20
            blocked, reply = check_rate_limit(session_id=session_id, now=i)
            self.assertFalse(blocked, f"message {i + 1} should not be blocked")
            self.assertIsNone(reply)

    def test_the_twenty_first_message_is_blocked(self):
        session_id = "rate-session-21-blocked"

        for i in range(RATE_LIMIT_MAX_MESSAGES):  # messages 1 to 20
            check_rate_limit(session_id=session_id, now=i)

        blocked, reply = check_rate_limit(session_id=session_id, now=RATE_LIMIT_MAX_MESSAGES)

        self.assertTrue(blocked)
        self.assertEqual(reply, RATE_LIMIT_REPLY)

    def test_the_limit_resets_once_the_window_has_passed(self):
        session_id = "rate-session-resets"

        for i in range(RATE_LIMIT_MAX_MESSAGES):  # messages 1 to 20, all allowed
            check_rate_limit(session_id=session_id, now=i)

        # Message 21, still inside the window, is blocked.
        blocked, _ = check_rate_limit(session_id=session_id, now=RATE_LIMIT_MAX_MESSAGES)
        self.assertTrue(blocked)

        # Well past the 10-minute window since message 1 (and every
        # message after it) — the session should be allowed again.
        later = RATE_LIMIT_MAX_MESSAGES + RATE_LIMIT_WINDOW_SECONDS + 1
        blocked, reply = check_rate_limit(session_id=session_id, now=later)

        self.assertFalse(blocked)
        self.assertIsNone(reply)

    def test_a_different_session_has_its_own_limit(self):
        busy_session = "rate-session-busy"
        quiet_session = "rate-session-quiet"

        for i in range(RATE_LIMIT_MAX_MESSAGES + 5):
            check_rate_limit(session_id=busy_session, now=i)

        # The busy session is over its limit, but a different session
        # sending its first message right now must not be affected.
        blocked, reply = check_rate_limit(session_id=quiet_session, now=0)

        self.assertFalse(blocked)
        self.assertIsNone(reply)

    def test_trigger_is_logged(self):
        session_id = "rate-session-logging"

        for i in range(RATE_LIMIT_MAX_MESSAGES):
            check_rate_limit(session_id=session_id, now=i)

        with self.assertLogs("propdesk.guards", level="WARNING") as captured:
            check_rate_limit(session_id=session_id, now=RATE_LIMIT_MAX_MESSAGES)

        log_line = captured.output[0]
        self.assertIn("rate_limit", log_line)
        self.assertIn(session_id, log_line)
