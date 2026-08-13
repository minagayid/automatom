import unittest

from app.strands_runtime import ProfessionalBriefAgent, result_payload


class DemoContractTests(unittest.TestCase):
    def test_demo_result_exposes_agent_mode_and_approval_boundary(self):
        result = ProfessionalBriefAgent(mode="offline").run("Prepare a weekly client update")
        payload = result_payload(result)

        self.assertEqual(payload["agentMode"], "offline")
        self.assertTrue(payload["approvalRequired"])
        self.assertEqual(payload["notificationStatus"], "pending_approval")
        self.assertFalse(payload["sent"])


if __name__ == "__main__":
    unittest.main()
