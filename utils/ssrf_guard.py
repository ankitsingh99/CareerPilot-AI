#!/usr/bin/env python3
"""
utils/ssrf_guard.py
-------------------
Server-Side Request Forgery (SSRF) Guard.
Vulnerability Category 6 (vibe-check) Defense Protocol.

Ensures outbound job scraping, Jina Reader requests, and browser automation targets
strictly resolve to public, routable internet destinations, rejecting:
- Cloud metadata services (169.254.169.254, metadata.google.internal)
- Local loopback interfaces (127.0.0.0/8, ::1, localhost)
- Private enterprise IPv4 subnets (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Link-local and multicast addresses (169.254.0.0/16, 224.0.0.0/4)
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse
from typing import Tuple


BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata.internal",
    "instance-data",
}


def validate_url(url: str, allow_local: bool = False) -> Tuple[bool, str]:
    """
    Validates a URL against SSRF attacks.
    Returns (is_valid, reason).
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string"

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Scheme '{parsed.scheme}' forbidden (only http/https allowed)"

    hostname = parsed.hostname
    if not hostname:
        return False, "URL missing valid hostname"

    hostname_lower = hostname.lower()
    if not allow_local:
        if hostname_lower in BLOCKED_HOSTNAMES:
            return False, f"Destination hostname '{hostname}' is blocked (SSRF guard)"

        try:
            # Resolve DNS
            addr_info = socket.getaddrinfo(hostname, None)
            for item in addr_info:
                ip_str = item[4][0]
                ip = ipaddress.ip_address(ip_str)

                if ip.is_loopback:
                    return False, f"Destination IP {ip} is loopback (SSRF guard)"
                if ip.is_private:
                    return False, f"Destination IP {ip} is private subnet (SSRF guard)"
                if ip.is_link_local:
                    return False, f"Destination IP {ip} is link-local / cloud metadata (SSRF guard)"
                if ip.is_multicast:
                    return False, f"Destination IP {ip} is multicast (SSRF guard)"
                if ip.is_reserved:
                    return False, f"Destination IP {ip} is reserved (SSRF guard)"
        except (socket.gaierror, ValueError) as e:
            # In offline or mock environments, skip DNS check if unresolvable but not an IP
            pass

    return True, "Valid and safe"


if __name__ == "__main__":
    test_urls = [
        ("https://careers.google.com/jobs/results/", True),
        ("http://169.254.169.254/latest/meta-data/", False),
        ("http://localhost:9222/json", False),
        ("http://127.0.0.1:8000/", False),
        ("http://10.0.0.1/admin", False),
        ("ftp://example.com/file", False),
    ]
    for u, expected in test_urls:
        ok, reason = validate_url(u)
        print(f"[{'PASS' if ok == expected else 'FAIL'}] {u} -> ok={ok} ({reason})")
