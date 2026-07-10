import unittest

from fastapi.testclient import TestClient

from dashboard.server import app


class DashboardSpaRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_view_route_serves_spa_entrypoint(self):
        response = self.client.get("/view/12345")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn('<div id="root"></div>', response.text)


if __name__ == "__main__":
    unittest.main()
