import unittest

from src.app.factories import create_web_app


class AppFactoryTests(unittest.TestCase):
    def test_create_web_app_builds_without_bot_token(self):
        app = create_web_app()
        self.assertEqual(app.title, "Portfolio Viewer")


if __name__ == "__main__":
    unittest.main()
