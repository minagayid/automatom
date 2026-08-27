import os
import unittest
from unittest.mock import patch

from app.google_runtime import _client_config, runtime_metadata, vertex_ai_configured


class GoogleRuntimeMetadataTests(unittest.TestCase):
    def test_vertex_configuration_is_reported_without_credentials(self):
        environment = {
            "GOOGLE_GENAI_USE_VERTEXAI": "true",
            "GOOGLE_CLOUD_PROJECT": "demo-project",
            "GOOGLE_CLOUD_LOCATION": "us-central1",
            "GEMINI_MODEL": "gemini-3.5-flash",
        }
        with patch.dict(os.environ, environment, clear=True):
            self.assertTrue(vertex_ai_configured())
            metadata = runtime_metadata()

        self.assertEqual(metadata["agentFramework"], "Google Gen AI SDK")
        self.assertEqual(metadata["model"], "gemini-3.5-flash")
        self.assertTrue(metadata["vertexAiConfigured"])
        self.assertEqual(metadata["cloudTarget"], "Cloud Run")
        self.assertEqual(metadata["authentication"], "vertex-adc")

    def test_unconfigured_runtime_does_not_claim_vertex_execution(self):
        with patch.dict(os.environ, {}, clear=True):
            metadata = runtime_metadata()

        self.assertFalse(metadata["vertexAiConfigured"])
        self.assertEqual(metadata["authentication"], "unconfigured")

    def test_vertex_client_uses_supported_google_genai_configuration(self):
        environment = {
            "GOOGLE_GENAI_USE_VERTEXAI": "true",
            "GOOGLE_CLOUD_PROJECT": "demo-project",
            "GOOGLE_CLOUD_LOCATION": "us-central1",
        }
        with patch.dict(os.environ, environment, clear=True):
            client, authentication = _client_config()

        self.assertEqual(authentication, "vertex-adc")
        self.assertIsNotNone(client)


if __name__ == "__main__":
    unittest.main()
