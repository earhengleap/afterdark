"""
Health Monitor - System health check and monitoring
"""

import asyncio
import logging
import psutil
import os
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger("AfterDark.HealthMonitor")


class HealthMonitor:
    """Monitor bot and system health"""
    
    def __init__(self, app):
        self.app = app
        self.last_check = None
        self.health_status = "unknown"
        try:
            self.process = psutil.Process(os.getpid())
        except Exception as e:
            logger.error(f"Failed to initialize health monitor process: {e}")
            self.process = None

    def _get_safe_metric(self, func, *args, default=0, **kwargs):
        """
        Safely execute a psutil metric function
        """
        if self.process is None:
            return default
            
        try:
            return func(*args, **kwargs)
        except (RuntimeError, psutil.Error) as e:
            # Specifically handle Windows handle information buffer overflow
            if "SystemExtendedHandleInformation" in str(e):
                logger.debug(f"Handle buffer overflow: {e}")
            else:
                func_name = getattr(func, "__name__", str(func))
                logger.warning(f"Failed to get metric {func_name}: {e}")
            return default
        except Exception as e:
            func_name = getattr(func, "__name__", str(func))
            logger.error(f"Unexpected error getting metric {func_name}: {e}")
            return default
    
    async def check_health(self) -> Dict:
        """
        Perform health check
        
        Returns:
            Dictionary with health status
        """
        self.last_check = datetime.now()
        
        try:
            # Check bot connection
            bot_connected = self.app.is_connected if hasattr(self.app, 'is_connected') else False
            
            # Get system metrics
            cpu_percent = self._get_safe_metric(self.process.cpu_percent, interval=0.1) if self.process else 0
            memory_info = self.process.memory_info() if self.process else None
            memory_mb = (memory_info.rss / 1024 / 1024) if memory_info else 0
            
            # Get system-wide stats
            system_cpu = psutil.cpu_percent(interval=0.1)
            system_memory = psutil.virtual_memory()
            disk_usage = psutil.disk_usage('/')
            
            # Determine overall health
            is_healthy = (
                bot_connected and
                cpu_percent < 90 and
                memory_mb < 1024 and  # Less than 1GB
                disk_usage.percent < 95
            )
            
            self.health_status = "healthy" if is_healthy else "degraded"
            
            health_data = {
                "status": self.health_status,
                "timestamp": self.last_check.isoformat(),
                "bot": {
                    "connected": bot_connected,
                    "uptime_seconds": self._get_uptime()
                },
                "process": {
                    "cpu_percent": round(cpu_percent, 2),
                    "memory_mb": round(memory_mb, 2),
                    "memory_percent": round(((memory_info.rss / system_memory.total * 100) if (memory_info and system_memory.total > 0) else 0), 2),
                    "threads": self._get_safe_metric(self.process.num_threads) if self.process else 0,
                    "open_files": len(self._get_safe_metric(self.process.open_files, default=[])) if self.process else 0
                },
                "system": {
                    "cpu_percent": round(system_cpu, 2),
                    "memory_total_mb": round(system_memory.total / 1024 / 1024, 2),
                    "memory_available_mb": round(system_memory.available / 1024 / 1024, 2),
                    "memory_percent": system_memory.percent,
                    "disk_total_gb": round(disk_usage.total / 1024 / 1024 / 1024, 2),
                    "disk_used_gb": round(disk_usage.used / 1024 / 1024 / 1024, 2),
                    "disk_percent": disk_usage.percent
                }
            }
            
            return health_data
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self.health_status = "unhealthy"
            return {
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def _get_uptime(self) -> float:
        """Get process uptime in seconds"""
        try:
            create_time = self.process.create_time()
            return datetime.now().timestamp() - create_time
        except:
            return 0.0
    
    def get_health_summary(self) -> str:
        """Get human-readable health summary"""
        try:
            cpu_percent = self._get_safe_metric(self.process.cpu_percent, interval=0.1) if self.process else 0
            memory_info = self._get_safe_metric(lambda: self.process.memory_info()) if self.process else None
            memory_mb = (memory_info.rss / 1024 / 1024) if memory_info else 0
            
            status_emoji = {
                "healthy": "✅",
                "degraded": "⚠️",
                "unhealthy": "❌",
                "unknown": "❓"
            }
            
            emoji = status_emoji.get(self.health_status, "❓")
            
            return (
                f"{emoji} **Health Status: {self.health_status.upper()}**\n\n"
                f"🔌 Bot Connected: {'Yes' if self.app.is_connected else 'No'}\n"
                f"⚡ CPU Usage: {cpu_percent:.1f}%\n"
                f"💾 Memory Usage: {memory_mb:.1f} MB\n"
                f"🕐 Last Check: {self.last_check.strftime('%Y-%m-%d %H:%M:%S') if self.last_check else 'Never'}"
            )
        except Exception as e:
            return f"❌ Health check error: {e}"


async def start_health_monitor(app, interval: int = 300):
    """
    Start periodic health monitoring
    
    Args:
        app: Pyrogram client instance
        interval: Check interval in seconds (default: 300 = 5 minutes)
    """
    monitor = HealthMonitor(app)
    logger.info(f"Health monitor started (check interval: {interval}s)")
    
    while True:
        try:
            health_data = await monitor.check_health()
            
            # Log warnings if unhealthy
            if health_data.get("status") != "healthy":
                logger.warning(f"Health check: {health_data.get('status')}")
                
                # Log specific issues
                process_data = health_data.get("process", {})
                if process_data.get("cpu_percent", 0) > 80:
                    logger.warning(f"High CPU usage: {process_data['cpu_percent']}%")
                if process_data.get("memory_mb", 0) > 512:
                    logger.warning(f"High memory usage: {process_data['memory_mb']:.1f} MB")
            
        except Exception as e:
            logger.error(f"Health monitor error: {e}")
        
        await asyncio.sleep(interval)


def get_health_monitor(app) -> HealthMonitor:
    """Create and return a health monitor instance"""
    return HealthMonitor(app)

