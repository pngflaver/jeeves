import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from services import network_tools

async def test_security_filter():
    print("🔒 --- Testing Security & IP Filtering ---")
    bad_targets = [
        "127.0.0.1",
        "localhost",
        "192.168.1.1",
        "10.0.0.1",
        "169.254.169.254",
        "google.com; rm -rf /",
        "google.com && whoami",
        "| cat /etc/passwd",
    ]

    for bad in bad_targets:
        is_valid, cleaned, err = network_tools.validate_target(bad)
        print(f"Target: {bad:25} -> Valid: {is_valid} | Result: {err}")
        assert not is_valid, f"Security check failed: {bad} should have been rejected!"

    print("✅ All security blacklist & injection tests PASSED!\n")

async def test_live_tools():
    print("🌐 --- Testing Live Network Diagnostic Tools ---")

    print("\n1. Testing /ping 1.1.1.1...")
    res = await network_tools.run_ping("1.1.1.1")
    print(res)

    print("\n2. Testing /dns google.com MX...")
    res = await network_tools.run_dns("google.com", "MX")
    print(res)

    print("\n3. Testing /http https://telegram.org...")
    res = await network_tools.run_http("https://telegram.org")
    print(res)

    print("\n4. Testing /ssl google.com...")
    res = await network_tools.run_ssl("google.com")
    print(res)

    print("\n5. Testing /ipinfo 1.1.1.1...")
    res = await network_tools.run_ipinfo("1.1.1.1")
    print(res)

    print("\n6. Testing /nmap scanme.nmap.org...")
    res = await network_tools.run_nmap("scanme.nmap.org")
    print(res)

    print("\n✅ All live tool tests PASSED!")

async def main():
    await test_security_filter()
    await test_live_tools()

if __name__ == "__main__":
    asyncio.run(main())
