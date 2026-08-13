import unittest

from app.strands_runtime import AgentResult, ProfessionalBriefAgent


class ProfessionalBriefAgentTests(unittest.TestCase):
    def test_offline_agent_returns_structured_brief_and_pending_notification(self):
        result = ProfessionalBriefAgent(mode="offline").run(
            "Prepare a weekly competitor brief for a small SaaS team"
        )

        self.assertIsInstance(result, AgentResult)
        self.assertEqual(result.mode, "offline")
        self.assertEqual(result.status, "awaiting_approval")
        self.assertIn("competitor", result.brief.lower())
        self.assertEqual(result.notification_status, "pending_approval")

    def test_approval_does_not_send_a_message(self):
        agent = ProfessionalBriefAgent(mode="offline")
        result = agent.run("Summarize this week's support themes")

        approved = agent.approve(result.run_id)

        self.assertEqual(approved.notification_status, "approved_for_send")
        self.assertFalse(approved.sent)


if __name__ == "__main__":
    unittest.main()
