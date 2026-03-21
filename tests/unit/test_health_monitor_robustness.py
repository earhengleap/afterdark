import asyncio
import unittest
from unittest.mock import MagicMock, patch
import psutil
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.health_monitor import HealthMonitor

class TestHealthMonitorRobustness(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_app.is_connected = True
        self.monitor = HealthMonitor(self.mock_app)

    @patch('psutil.Process')
    async def test_check_health_buffer_error(self, mock_process_class):
        # Setup mock process
        mock_process = MagicMock()
        mock_process_class.return_value = mock_process
        
        # Re-initialize monitor with mock process
        self.monitor = HealthMonitor(self.mock_app)
        
        # Mock open_files to raise the specific buffer error
        mock_process.open_files.side_effect = RuntimeError("SystemExtendedHandleInformation buffer too big")
        
        # Mock other metrics to return valid values
        mock_process.cpu_percent.return_value = 10.0
        mock_process.memory_info.return_value.rss = 100 * 1024 * 1024
        mock_process.num_threads.return_value = 5
        
        # Run health check
        health_data = await self.monitor.check_health()
        
        # Verify it didn't crash and status is healthy (since other metrics are fine)
        self.assertEqual(health_data["status"], "healthy")
        self.assertEqual(health_data["process"]["open_files"], 0)
        self.assertEqual(health_data["process"]["cpu_percent"], 10.0)

    @patch('psutil.Process')
    async def test_get_summary_robustness(self, mock_process_class):
        mock_process = MagicMock()
        mock_process_class.return_value = mock_process
        self.monitor = HealthMonitor(self.mock_app)
        
        # Mock valid returns for other metrics to avoid MagicMock formatting errors
        mock_process.cpu_percent.return_value = 0.0
        mock_process.memory_info.return_value.rss = 0
        
        # Mock error in cpu_percent specifically for this test
        mock_process.cpu_percent.side_effect = Exception("General error")
        
        summary = self.monitor.get_health_summary()
        
        # Verify summary contains status even if some metrics failed
        self.assertIn("Health Status", summary)
        self.assertIn("0.0%", summary) # Default for failed CPU metric

if __name__ == "__main__":
    unittest.main()
