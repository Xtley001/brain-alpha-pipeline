"""
Robust DNS Fallback & Resilience Engine.
Protects the pipeline from host router / ISP DNS dropouts ([Errno 11001] getaddrinfo failed).
Automatically falls back to direct Cloudflare/Google DNS resolution and verified endpoint IPs.
"""
from __future__ import annotations

import logging
import socket
from typing import Any

log = logging.getLogger("brain_options.dns_fallback")

# Known verified IPs for critical pipeline endpoints
FALLBACK_HOST_MAP = {
    "ep-lively-flower-zanmayxy-pooler.c-2.eu-west-2.aws.neon.tech": [
        "35.177.158.108",
        "3.10.149.215",
        "35.177.159.226",
    ],
    "api.worldquantbrain.com": [
        "54.209.200.69",
        "184.195.234.127",
        "34.237.41.148",
    ],
}

_ORIG_GETADDRINFO = socket.getaddrinfo
_PATCH_INSTALLED = False


def _resolve_via_public_dns(hostname: str) -> list[str]:
    """Attempts direct DNS query to Cloudflare (1.1.1.1) via UDP socket."""
    import struct
    try:
        # Build standard DNS query packet for Type A (IPv4)
        query_id = 0x1234
        flags = 0x0100  # Standard query with recursion desired
        qdcount = 1
        ancount = 0
        nscount = 0
        arcount = 0
        header = struct.pack("!HHHHHH", query_id, flags, qdcount, ancount, nscount, arcount)

        # Question section
        qname = b""
        for part in hostname.split("."):
            qname += struct.pack("!B", len(part)) + part.encode("ascii")
        qname += b"\x00"
        qtype = 1  # Type A
        qclass = 1  # Class IN
        question = qname + struct.pack("!HH", qtype, qclass)
        packet = header + question

        # Send to 1.1.1.1:53 with 2.5s timeout
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.5)
        sock.sendto(packet, ("1.1.1.1", 53))
        data, _ = sock.recvfrom(1024)
        sock.close()

        # Parse answers
        if len(data) > 12:
            r_ancount = struct.unpack("!H", data[6:8])[0]
            if r_ancount > 0:
                # Skip question
                offset = 12 + len(question)
                ips = []
                for _ in range(r_ancount):
                    if offset + 12 > len(data):
                        break
                    # Name pointer or label
                    if (data[offset] & 0xC0) == 0xC0:
                        offset += 2
                    else:
                        while offset < len(data) and data[offset] != 0:
                            offset += 1 + data[offset]
                        offset += 1
                    rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", data[offset:offset+10])
                    offset += 10
                    if rtype == 1 and rdlength == 4:
                        ip = socket.inet_ntoa(data[offset:offset+4])
                        ips.append(ip)
                    offset += rdlength
                if ips:
                    return ips
    except Exception:
        pass
    return []


def install_dns_resilience_patch() -> None:
    """Installs automatic fallback resolution into socket.getaddrinfo."""
    global _PATCH_INSTALLED, _ORIG_GETADDRINFO
    if _PATCH_INSTALLED:
        return

    def resilient_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any):
        try:
            return _ORIG_GETADDRINFO(host, port, *args, **kwargs)
        except socket.gaierror as e:
            if e.errno == 11001 or "getaddrinfo failed" in str(e).lower():
                h_str = str(host)
                # 1. Try public DNS query directly to 1.1.1.1
                dynamic_ips = _resolve_via_public_dns(h_str)
                if dynamic_ips:
                    return _ORIG_GETADDRINFO(dynamic_ips[0], port, *args, **kwargs)

                # 2. Match known critical endpoints in fallback map
                for domain, ips in FALLBACK_HOST_MAP.items():
                    if domain in h_str:
                        log.warning("[DNS RESILIENCE] Router DNS failure on '%s'. Falling back to verified IP '%s'.",
                                    h_str, ips[0])
                        return _ORIG_GETADDRINFO(ips[0], port, *args, **kwargs)
            raise

    socket.getaddrinfo = resilient_getaddrinfo
    _PATCH_INSTALLED = True
    log.info("DNS resilience patch installed (1.1.1.1 public fallback + static IP recovery).")


# Auto-install on module import
install_dns_resilience_patch()
