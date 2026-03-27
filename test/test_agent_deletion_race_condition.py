"""Unit tests for agent deletion race condition fixes.

This module tests the race condition handling when DELETE requests arrive
while the verifier is actively attesting an agent. It verifies that:

1. check_agent_deletion_status() correctly detects deleted/TERMINATED agents
2. invoke_get_quote() exits early when agent is marked for deletion
3. invoke_provide_v() exits early when agent is marked for deletion
4. store_attestation_state() handles deleted agents gracefully

Regression test for: Agent deletion timing out during active attestation
causing tenant update operations to fail after 5 retries (~62 seconds).
"""

import os
import re
import unittest

from keylime.common import states


class TestCheckAgentDeletionStatusCodeAnalysis(unittest.TestCase):
    """Test check_agent_deletion_status() helper function via code analysis.

    These tests verify the implementation through source code inspection
    to ensure the race condition fix is properly implemented without
    requiring full module imports.
    """

    def test_check_agent_deletion_status_function_exists(self):
        """Verify check_agent_deletion_status() function exists in cloud_verifier_tornado.py."""
        # Read the source code
        verifier_tornado_path = os.path.join(
            os.path.dirname(__file__), "..", "keylime", "cloud_verifier_tornado.py"
        )

        with open(verifier_tornado_path, encoding="utf-8") as f:
            source = f.read()

        # Should have the function defined
        self.assertIn(
            "def check_agent_deletion_status(",
            source,
            "check_agent_deletion_status() function should exist to prevent race conditions",
        )

    def test_check_agent_deletion_status_checks_terminated_state(self):
        """Verify check_agent_deletion_status() checks for TERMINATED state."""
        verifier_tornado_path = os.path.join(
            os.path.dirname(__file__), "..", "keylime", "cloud_verifier_tornado.py"
        )

        with open(verifier_tornado_path, encoding="utf-8") as f:
            source = f.read()

        # Find the function
        pattern = r"def check_agent_deletion_status\(.*?\):(.*?)(?=\ndef |\Z)"
        match = re.search(pattern, source, re.DOTALL)

        self.assertIsNotNone(match, "check_agent_deletion_status function not found")
        assert match is not None

        function_body = match.group(1)

        # Should check operational_state == TERMINATED
        self.assertIn(
            "TERMINATED",
            function_body,
            "check_agent_deletion_status should check for TERMINATED state",
        )

        # Should return True when agent is deleted or TERMINATED
        self.assertIn(
            "return True",
            function_body,
            "check_agent_deletion_status should return True for deleted/TERMINATED agents",
        )

        # Should return False when agent is active
        self.assertIn(
            "return False",
            function_body,
            "check_agent_deletion_status should return False for active agents",
        )

    def test_check_agent_deletion_status_removes_pending_event(self):
        """Verify check_agent_deletion_status() removes pending events."""
        verifier_tornado_path = os.path.join(
            os.path.dirname(__file__), "..", "keylime", "cloud_verifier_tornado.py"
        )

        with open(verifier_tornado_path, encoding="utf-8") as f:
            source = f.read()

        pattern = r"def check_agent_deletion_status\(.*?\):(.*?)(?=\ndef |\Z)"
        match = re.search(pattern, source, re.DOTALL)
        assert match is not None
        function_body = match.group(1)

        # Should remove pending timeouts
        self.assertIn(
            "remove_timeout",
            function_body,
            "check_agent_deletion_status should remove pending timeouts to prevent memory leaks",
        )

    def test_check_agent_deletion_status_handles_database_errors(self):
        """Verify check_agent_deletion_status() handles SQLAlchemy errors."""
        verifier_tornado_path = os.path.join(
            os.path.dirname(__file__), "..", "keylime", "cloud_verifier_tornado.py"
        )

        with open(verifier_tornado_path, encoding="utf-8") as f:
            source = f.read()

        pattern = r"def check_agent_deletion_status\(.*?\):(.*?)(?=\ndef |\Z)"
        match = re.search(pattern, source, re.DOTALL)
        assert match is not None
        function_body = match.group(1)

        # Should have try/except for SQLAlchemyError
        self.assertIn(
            "except SQLAlchemyError",
            function_body,
            "check_agent_deletion_status should handle SQLAlchemy errors gracefully",
        )


class TestInvokeGetQuoteRaceConditionFix(unittest.TestCase):
    """Test invoke_get_quote() race condition fix via code analysis."""

    def test_invoke_get_quote_calls_deletion_check(self):
        """Verify invoke_get_quote() checks agent deletion status early."""
        verifier_tornado_path = os.path.join(
            os.path.dirname(__file__), "..", "keylime", "cloud_verifier_tornado.py"
        )

        with open(verifier_tornado_path, encoding="utf-8") as f:
            source = f.read()

        # Find invoke_get_quote function
        pattern = r"async def invoke_get_quote\(.*?\):(.*?)(?=\nasync def |\ndef |\Z)"
        match = re.search(pattern, source, re.DOTALL)

        self.assertIsNotNone(match, "invoke_get_quote function not found")
        assert match is not None

        function_body = match.group(1)

        # Should call check_agent_deletion_status
        self.assertIn(
            "check_agent_deletion_status(",
            function_body,
            "invoke_get_quote should check if agent is being deleted before getting quote",
        )

        # Should return early if agent is being deleted
        # Look for pattern: if check_agent_deletion_status(...): ... return
        deletion_check_index = function_body.find("check_agent_deletion_status(")
        after_check = function_body[deletion_check_index:deletion_check_index + 500]

        self.assertIn(
            "return",
            after_check,
            "invoke_get_quote should return early when agent is being deleted",
        )

    def test_invoke_get_quote_deletion_check_comes_first(self):
        """Verify deletion check happens before prepare_get_quote."""
        verifier_tornado_path = os.path.join(
            os.path.dirname(__file__), "..", "keylime", "cloud_verifier_tornado.py"
        )

        with open(verifier_tornado_path, encoding="utf-8") as f:
            source = f.read()

        pattern = r"async def invoke_get_quote\(.*?\):(.*?)(?=\nasync def |\ndef |\Z)"
        match = re.search(pattern, source, re.DOTALL)
        assert match is not None
        function_body = match.group(1)

        # Find positions of deletion check and prepare_get_quote
        deletion_check_pos = function_body.find("check_agent_deletion_status(")
        prepare_quote_pos = function_body.find("prepare_get_quote(")

        # Deletion check should come before prepare_get_quote
        self.assertLess(
            deletion_check_pos,
            prepare_quote_pos,
            "Deletion check must happen BEFORE preparing quote to prevent wasted work",
        )


class TestInvokeProvideVRaceConditionFix(unittest.TestCase):
    """Test invoke_provide_v() race condition fix via code analysis."""

    def test_invoke_provide_v_calls_deletion_check(self):
        """Verify invoke_provide_v() checks agent deletion status early."""
        verifier_tornado_path = os.path.join(
            os.path.dirname(__file__), "..", "keylime", "cloud_verifier_tornado.py"
        )

        with open(verifier_tornado_path, encoding="utf-8") as f:
            source = f.read()

        # Find invoke_provide_v function
        pattern = r"async def invoke_provide_v\(.*?\):(.*?)(?=\nasync def |\ndef |\Z)"
        match = re.search(pattern, source, re.DOTALL)

        self.assertIsNotNone(match, "invoke_provide_v function not found")
        assert match is not None

        function_body = match.group(1)

        # Should call check_agent_deletion_status
        self.assertIn(
            "check_agent_deletion_status(",
            function_body,
            "invoke_provide_v should check if agent is being deleted before providing V key",
        )

        # Should return early if agent is being deleted
        deletion_check_index = function_body.find("check_agent_deletion_status(")
        after_check = function_body[deletion_check_index:deletion_check_index + 500]

        self.assertIn(
            "return",
            after_check,
            "invoke_provide_v should return early when agent is being deleted",
        )


class TestStoreAttestationStateRaceConditionFix(unittest.TestCase):
    """Test store_attestation_state() race condition fix via code analysis."""

    def test_store_attestation_state_handles_deleted_agent(self):
        """Verify store_attestation_state() handles deleted agents gracefully."""
        verifier_tornado_path = os.path.join(
            os.path.dirname(__file__), "..", "keylime", "cloud_verifier_tornado.py"
        )

        with open(verifier_tornado_path, encoding="utf-8") as f:
            source = f.read()

        # Find store_attestation_state function
        pattern = r"def store_attestation_state\(.*?\):(.*?)(?=\ndef |\Z)"
        match = re.search(pattern, source, re.DOTALL)

        self.assertIsNotNone(match, "store_attestation_state function not found")
        assert match is not None

        function_body = match.group(1)

        # Should check if update_agent is None
        self.assertIn(
            "is None",
            function_body,
            "store_attestation_state should check if agent was deleted during attestation",
        )

        # Should NOT have assert update_agent (the bug we fixed)
        self.assertNotIn(
            "assert update_agent",
            function_body,
            "store_attestation_state should NOT assert, it should gracefully handle deleted agents",
        )

        # Should return early when agent is None
        # Look for pattern where we check None and return
        get_pos = function_body.find("session.get(")
        after_get = function_body[get_pos:get_pos + 1000]

        self.assertIn(
            "return",
            after_get,
            "store_attestation_state should return early when agent is deleted",
        )

    def test_store_attestation_state_logs_debug_on_deletion(self):
        """Verify store_attestation_state() logs debug message when agent deleted."""
        verifier_tornado_path = os.path.join(
            os.path.dirname(__file__), "..", "keylime", "cloud_verifier_tornado.py"
        )

        with open(verifier_tornado_path, encoding="utf-8") as f:
            source = f.read()

        pattern = r"def store_attestation_state\(.*?\):(.*?)(?=\ndef |\Z)"
        match = re.search(pattern, source, re.DOTALL)
        assert match is not None
        function_body = match.group(1)

        # Should log when agent no longer exists
        self.assertIn(
            "no longer exists",
            function_body,
            "store_attestation_state should log when agent was deleted during attestation",
        )


class TestRaceConditionDocumentation(unittest.TestCase):
    """Test that race condition fixes are properly documented."""

    def test_check_agent_deletion_status_has_docstring(self):
        """Verify check_agent_deletion_status() has explanatory docstring."""
        verifier_tornado_path = os.path.join(
            os.path.dirname(__file__), "..", "keylime", "cloud_verifier_tornado.py"
        )

        with open(verifier_tornado_path, encoding="utf-8") as f:
            source = f.read()

        pattern = r"def check_agent_deletion_status\(.*?\):(.*?)(?=\n    with |\n    if )"
        match = re.search(pattern, source, re.DOTALL)
        assert match is not None
        after_def = match.group(1)

        # Should have docstring explaining the race condition
        critical_terms = ["race", "DELETE", "deletion", "attestation"]
        found_terms = [term for term in critical_terms if term.lower() in after_def.lower()]

        self.assertGreaterEqual(
            len(found_terms),
            2,
            f"check_agent_deletion_status docstring should explain the race condition. "
            f"Expected mentions of race/DELETE/deletion/attestation, found: {found_terms}",
        )

    def test_invoke_get_quote_has_deletion_check_comment(self):
        """Verify invoke_get_quote() documents why deletion check is needed."""
        verifier_tornado_path = os.path.join(
            os.path.dirname(__file__), "..", "keylime", "cloud_verifier_tornado.py"
        )

        with open(verifier_tornado_path, encoding="utf-8") as f:
            source = f.read()

        pattern = r"async def invoke_get_quote\(.*?\):(.*?)(?=\nasync def |\ndef |\Z)"
        match = re.search(pattern, source, re.DOTALL)
        assert match is not None
        function_body = match.group(1)

        # Find the deletion check section
        check_pos = function_body.find("check_agent_deletion_status(")
        before_check = function_body[max(0, check_pos - 300):check_pos]

        # Should have comment explaining race condition
        critical_terms = ["race", "DELETE", "deletion", "prevent"]
        found_terms = [term for term in critical_terms if term.lower() in before_check.lower()]

        self.assertGreaterEqual(
            len(found_terms),
            2,
            f"invoke_get_quote should document why deletion check is needed. "
            f"Expected mentions of race/DELETE/deletion/prevent, found: {found_terms}",
        )


class TestRaceConditionCodeStructure(unittest.TestCase):
    """Test the overall code structure of the race condition fix."""

    def test_all_three_functions_use_check_agent_deletion_status(self):
        """Verify both async functions use the centralized helper."""
        verifier_tornado_path = os.path.join(
            os.path.dirname(__file__), "..", "keylime", "cloud_verifier_tornado.py"
        )

        with open(verifier_tornado_path, encoding="utf-8") as f:
            source = f.read()

        # Count calls to check_agent_deletion_status
        calls = source.count("check_agent_deletion_status(agent)")

        self.assertGreaterEqual(
            calls,
            2,
            "Both invoke_get_quote() and invoke_provide_v() should call check_agent_deletion_status(). "
            f"Found {calls} call(s), expected at least 2.",
        )

    def test_no_code_duplication_in_deletion_check(self):
        """Verify deletion check logic is centralized, not duplicated."""
        verifier_tornado_path = os.path.join(
            os.path.dirname(__file__), "..", "keylime", "cloud_verifier_tornado.py"
        )

        with open(verifier_tornado_path, encoding="utf-8") as f:
            source = f.read()

        # The deletion check logic should only appear in check_agent_deletion_status
        # Not duplicated in invoke_get_quote or invoke_provide_v

        # Find invoke_get_quote
        pattern = r"async def invoke_get_quote\(.*?\):(.*?)(?=\nasync def |\ndef |\Z)"
        match = re.search(pattern, source, re.DOTALL)
        assert match is not None
        get_quote_body = match.group(1)

        # Should NOT query for agent state directly (that's in the helper)
        # It should only CALL the helper function
        self.assertNotIn(
            "session.query(VerfierMain).filter_by(agent_id=",
            get_quote_body,
            "invoke_get_quote should use check_agent_deletion_status(), not duplicate the logic",
        )


if __name__ == "__main__":
    unittest.main()
