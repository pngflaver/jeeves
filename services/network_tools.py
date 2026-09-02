import asyncio
import ipaddress
import re
import socket
from typing import Optional, Tuple
import httpx

# Whitelist allowed hostname / IP characters
HOST_REGEX = re.compile(r"^[a-zA-Z0-9.-]+$")
URL_REGEX = re.compile(r"^https?://[a-zA-Z0-9.-]+(?::\d+)?(?:/.*)?$", re.IGNORECASE)

def validate_target(target: str) -> Tuple[bool, str, Optional[str]]:
    """
    Validate target hostname or IP.
    Returns: (is_valid, sanitized_target, error_message)
    """
    cleaned = target.strip()
    # Strip protocol if user included http:// or https://
    cleaned = re.sub(r"^https?://", "", cleaned).split("/")[0].split(":")[0]

    if not cleaned or len(cleaned) > 253 or not HOST_REGEX.match(cleaned):
        return False, cleaned, "Invalid hostname or IP address format."

    # Check for private / loopback IP address
    try:
        # Check if direct IP
        ip = ipaddress.ip_address(cleaned)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local or ip.is_multicast:
            return False, cleaned, "⚠️ Access Denied: Scanning internal, private, or loopback IPs is prohibited."
    except ValueError:
        # Hostname - attempt DNS resolution to check if it points to private IP
        try:
            resolved_ip = socket.gethostbyname(cleaned)
            ip = ipaddress.ip_address(resolved_ip)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local or ip.is_multicast:
                return False, cleaned, f"⚠️ Access Denied: '{cleaned}' resolves to a private IP ({resolved_ip})."
        except socket.error:
            # If resolution fails, let command handle unresolved host error
            pass

    return True, cleaned, None

async def _exec_cmd(cmd_args: list, timeout: int = 10) -> str:
    """Safely execute a command with argument list and strict timeout."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", errors="replace").strip()
        
        # Limit output length for Telegram messages (max 3500 chars)
        if len(output) > 3500:
            output = output[:3500] + "\n... [Output truncated]"
        return output if output else "Command completed with no output."
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return f"⏱️ Timeout: Command exceeded {timeout}s time limit."
    except Exception as e:
        return f"⚠️ Execution Error: {e}"

async def run_ping(target: str) -> str:
    """Execute ping with 4 packets."""
    is_valid, host, err = validate_target(target)
    if not is_valid:
        return err

    cmd = ["ping", "-c", "4", "-W", "2", host]
    raw = await _exec_cmd(cmd, timeout=12)
    return f"```\n$ ping -c 4 {host}\n\n{raw}\n```"

async def run_traceroute(target: str) -> str:
    """Execute fast traceroute (max 15 hops)."""
    is_valid, host, err = validate_target(target)
    if not is_valid:
        return err

    cmd = ["traceroute", "-m", "15", "-q", "1", "-w", "1", host]
    raw = await _exec_cmd(cmd, timeout=18)
    return f"```\n$ traceroute -m 15 {host}\n\n{raw}\n```"

async def run_dns(target: str, record_type: str = "A") -> str:
    """Execute dig DNS query."""
    is_valid, host, err = validate_target(target)
    if not is_valid:
        return err

    valid_types = {"A", "AAAA", "MX", "TXT", "NS", "CNAME", "SOA", "ANY"}
    rec_type = record_type.upper().strip()
    if rec_type not in valid_types:
        rec_type = "A"

    cmd = ["dig", host, rec_type, "+noall", "+answer", "+stats"]
    raw = await _exec_cmd(cmd, timeout=8)
    if not raw or "ANSWER: 0" in raw and not any(r in raw for r in ["IN\t", "IN "]):
        # Fallback to standard query if answer is empty
        cmd = ["dig", host, rec_type]
        raw = await _exec_cmd(cmd, timeout=8)

    return f"```\n$ dig {host} {rec_type}\n\n{raw}\n```"

async def run_nmap(target: str) -> str:
    """Scan top common ports with Nmap."""
    is_valid, host, err = validate_target(target)
    if not is_valid:
        return err

    # Top common ports only (fast, non-intrusive)
    common_ports = "21,22,25,53,80,110,143,443,465,587,993,995,3306,5432,8080,8443"
    cmd = ["nmap", "-T4", "-Pn", "-p", common_ports, "--open", host]
    raw = await _exec_cmd(cmd, timeout=20)
    return f"```\n$ nmap -p common {host}\n\n{raw}\n```"

async def run_whois(target: str) -> str:
    """Execute whois lookup."""
    is_valid, host, err = validate_target(target)
    if not is_valid:
        return err

    cmd = ["whois", host]
    raw = await _exec_cmd(cmd, timeout=10)
    
    # Filter out excessive legal disclaimers if present
    lines = raw.splitlines()
    filtered = [l for l in lines if not l.startswith("%") and not l.startswith("#")]
    output_text = "\n".join(filtered).strip()
    if not output_text:
        output_text = raw

    return f"```\n$ whois {host}\n\n{output_text[:3000]}\n```"

async def run_http(target: str) -> str:
    """Check HTTP/HTTPS response status, latency, and headers."""
    cleaned = target.strip()
    if not cleaned.startswith("http://") and not cleaned.startswith("https://"):
        url = f"https://{cleaned}"
    else:
        url = cleaned

    is_valid, host, err = validate_target(url)
    if not is_valid:
        return err

    cmd = ["curl", "-ILs", "--max-time", "6", url]
    raw = await _exec_cmd(cmd, timeout=8)
    return f"```\n$ curl -IL {url}\n\n{raw}\n```"

async def run_ssl(target: str) -> str:
    """Check SSL certificate validity and expiry dates."""
    is_valid, host, err = validate_target(target)
    if not is_valid:
        return err

    cmd = [
        "bash", "-c",
        f"echo | openssl s_client -servername {host} -connect {host}:443 -brief 2>/dev/null; "
        f"echo | openssl s_client -servername {host} -connect {host}:443 2>/dev/null | openssl x509 -noout -dates -subject -issuer 2>/dev/null"
    ]
    raw = await _exec_cmd(cmd, timeout=8)
    return f"```\n$ ssl-check {host}:443\n\n{raw}\n```"

async def run_ipinfo(target: str) -> str:
    """Fetch IP / Host geolocation and ASN information."""
    is_valid, host, err = validate_target(target)
    if not is_valid:
        return err

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(f"https://ipapi.co/{host}/json/")
            if res.status_code == 200:
                d = res.json()
                if not d.get("error"):
                    formatted = (
                        f"IP:          {d.get('ip')}\n"
                        f"City/Region: {d.get('city')}, {d.get('region')} ({d.get('region_code')})\n"
                        f"Country:     {d.get('country_name')} ({d.get('country_code')})\n"
                        f"Postal:      {d.get('postal')}\n"
                        f"Coordinates: {d.get('latitude')}, {d.get('longitude')}\n"
                        f"Timezone:    {d.get('timezone')}\n"
                        f"Org / ASN:   {d.get('org')} ({d.get('asn')})\n"
                    )
                    return f"```\n$ ipinfo {host}\n\n{formatted}\n```"
    except Exception as e:
        pass

    # Fallback to curl ipinfo.io
    cmd = ["curl", "-s", f"https://ipinfo.io/{host}/json"]
    raw = await _exec_cmd(cmd, timeout=6)
    return f"```\n$ ipinfo {host}\n\n{raw}\n```"
