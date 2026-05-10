import unittest
from pathlib import Path


STATIC_INDEX = Path(__file__).resolve().parents[1] / "backend" / "trading_monitor" / "static" / "index.html"


class StaticDashboardTests(unittest.TestCase):
    def test_api_text_fields_are_escaped_before_inner_html_rendering(self):
        html = STATIC_INDEX.read_text()

        self.assertIn("function escapeHtml(value)", html)
        self.assertIn("${escapeHtml(status.data_provider)}", html)
        self.assertIn("${escapeHtml(signal.band)}", html)
        self.assertIn("${escapeHtml(reason)}", html)
        self.assertIn("${escapeHtml(result.warning)}", html)
        self.assertIn("${escapeHtml(notification.status)}", html)


if __name__ == "__main__":
    unittest.main()
