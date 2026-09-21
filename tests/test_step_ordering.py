"""Cross-service ordering for the steps Partner B owns (3, 4 and 5).

This is the local half of conformance check H-ORD: the harness merges the
transcripts of all four services by `ts` and expects the five Figure 3 steps in
order. Steps 1 and 2 are the CSP's to write, so this test drives the Verifier's
binding endpoint directly in place of Partner A's CSP and then checks that
everything from step 2 onwards lands in the right order.
"""

import os
import unittest

from shared.pwhash import hash_secret
from tests.helpers import Harness, apply_test_env

RUN_ID = "test-ordering-000003"
CANARY = "CANARY-a1b2c3d4e5f6"


class StepOrderingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        apply_test_env()
        from services.rp.app import RelyingParty
        from services.verifier.app import Verifier

        self.verifier = Harness(Verifier())
        self.addCleanup(self.verifier.close)
        os.environ["LAB1_VERIFIER_URL"] = self.verifier.url
        self.rp = Harness(RelyingParty())
        self.addCleanup(self.rp.close)

    def merged_events(self):
        events = self.verifier.transcript(RUN_ID) + self.rp.transcript(RUN_ID)
        return sorted(events, key=lambda e: e["ts"])

    def test_steps_two_to_five_appear_once_each_in_timestamp_order(self):
        # Step 2: the CSP hands the binding record to the Verifier.
        self.verifier.request(
            "POST", "/binding",
            {"run_id": RUN_ID, "identifier": "alice",
             "verifier_record": hash_secret(CANARY)},
            headers={"X-Lab1-Binding-Token": "test-binding-token-0123456789"},
        )
        # Step 3: the subscriber asks for the protected resource and is told to
        # authenticate. This is the Subscriber -> Claimant transition.
        status, _ = self.rp.request("GET", "/protected",
                                    headers={"X-Run-Id": RUN_ID})
        self.assertEqual(status, 401)
        # Step 4: the claimant proves control of the authenticator.
        _, body = self.verifier.request(
            "POST", "/authenticate",
            {"run_id": RUN_ID, "identifier": "alice", "authenticator_output": CANARY},
        )
        # Step 5: the RP validates the assertion and establishes a session.
        _, session = self.rp.request(
            "POST", "/session", {"run_id": RUN_ID, "assertion": body["assertion"]}
        )
        status, _ = self.rp.request(
            "GET", "/protected",
            headers={"Authorization": "Lab1-Session " + session["session"]},
        )
        self.assertEqual(status, 200)

        events = self.merged_events()
        steps = [e["step"] for e in events]
        self.assertEqual(steps, sorted(steps), "steps are out of timestamp order")
        self.assertEqual(sorted(set(steps)), [2, 3, 4, 5])
        self.assertTrue(all(e["outcome"] == "success" for e in events))
        self.assertTrue(all(e["run_id"] == RUN_ID for e in events))
        # Both services agree on the step names, because they share one table.
        names = {e["step"]: e["step_name"] for e in events}
        self.assertEqual(names[3], "authentication_request")
        self.assertEqual(names[5], "authenticated_session")

    def test_a_denied_run_records_no_successful_step_five(self):
        # The shape every negative scenario must have: the RP may log the denial,
        # but no step 5 succeeds.
        self.rp.request("GET", "/protected", headers={"X-Run-Id": RUN_ID})
        self.rp.request("POST", "/session",
                        {"run_id": RUN_ID, "assertion": "A" * 43})
        successes = [e for e in self.merged_events()
                     if e["step"] == 5 and e["outcome"] == "success"]
        self.assertEqual(successes, [])


if __name__ == "__main__":
    unittest.main()
