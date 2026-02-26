#!/usr/bin/env python3
"""
Start the TWA Gallery with a stable serveo tunnel.

Usage:
    python start_with_tunnel.py [subdomain]

Examples:
    python start_with_tunnel.py mygallery    # Creates https://mygallery.serveo.net
    python start_with_tunnel.py              # Uses config or 'afterdark' as default

The subdomain will remain the same across restarts, giving you a stable URL.

Configuration:
    Create 'tunnel_config.py' with:
        TWA_SERVEO_SUBDOMAIN = "your-subdomain"
"""

import os
import sys
import subprocess
from pathlib import Path

def load_config():
    """Load configuration from tunnel_config.py if it exists."""
    config_path = Path(__file__).parent.parent / "tunnel_config.py"
    config = {"subdomain": "afterdark"}
    
    if config_path.exists():
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("tunnel_config", config_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "TWA_SERVEO_SUBDOMAIN"):
                    config["subdomain"] = module.TWA_SERVEO_SUBDOMAIN
        except Exception as e:
            print(f"Warning: Could not load tunnel_config.py: {e}")
    
    return config

def main():
    # Load config
    config = load_config()
    
    # Get subdomain from argument, config, or default
    if len(sys.argv) > 1:
        subdomain = sys.argv[1]
    else:
        subdomain = config["subdomain"]
    
    print("=" * 50)
    print("TWA Gallery with Stable Tunnel")
    print("=" * 50)
    print(f"Subdomain: {subdomain}")
    print(f"Public URL: https://{subdomain}.serveo.net")
    print()
    print("NOTE: The URL will be stable across restarts!")
    print("      Update your Telegram Mini App URL once.")
    print("=" * 50)
    print()
    
    # Set environment variables
    env = os.environ.copy()
    env["TWA_SERVEO_SUBDOMAIN"] = subdomain
    env["TWA_SERVEO_AUTOSTART"] = "1"
    env["TWA_SERVEO_URL_TIMEOUT"] = "60"
    env["TWA_SERVEO_CONNECT_TIMEOUT"] = "15"
    env["TWA_LOCALHOSTRUN_AUTOSTART"] = "0"
    env["TWA_TUNNEL_PROVIDER"] = "serveo"
    
    # Change to twa directory
    script_dir = Path(__file__).parent.parent
    os.chdir(script_dir)
    
    # Start the server
    try:
        subprocess.run([sys.executable, "server.py"], env=env)
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
