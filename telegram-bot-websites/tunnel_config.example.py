# TWA Tunnel Configuration
# Copy this file to tunnel_config.py and customize

# Your stable subdomain for serveo.net
# This creates a URL like: https://YOUR_SUBDOMAIN.serveo.net
TWA_SERVEO_SUBDOMAIN = "afterdark"

# Serveo target server (usually don't need to change)
# TWA_SERVEO_TARGET = "serveo.net"

# SSH ports to try (comma separated)
# TWA_SERVEO_SSH_PORTS = "22,443"

# Timeout for tunnel URL discovery (seconds)
TWA_SERVEO_URL_TIMEOUT = 60

# Connection timeout (seconds)
TWA_SERVEO_CONNECT_TIMEOUT = 15

# Health check timeout (seconds)
TWA_TUNNEL_HEALTH_TIMEOUT = 20
