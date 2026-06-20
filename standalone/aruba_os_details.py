"""Standalone script: extract OS firmware details from HPE Aruba devices.

Reads the `show version` output from IP Fabric device logs and extracts:
  - family `arubacx` (AOS-CX)      -> BIOS Version       (e.g. FL.01.0007)
  - family `arubasw` (AOS-Switch)  -> Boot ROM Version   (e.g. WC.17.02.0007)

This is a self-contained version of the `--os-details` feature from
`search_logs.py`. It only does the Aruba OS/BIOS check, nothing else.

Usage:
    python aruba_os_details.py

Configuration is read from the `.env` file (same variables as the main project):
    IPF_URL, IPF_TOKEN, IPF_VERIFY, IPF_SNAPSHOT, IPF_TIMEOUT,
    PROMPT_DELIMITER, DEVICES_FILTER (optional)

Output: prints the results and writes `os_details.csv`.

WARNING: make sure the `ipfabric` SDK version matches your IP Fabric version.
"""

import contextlib
import csv
import json
import os
import re

from dotenv import find_dotenv, load_dotenv
from ipfabric import IPFClient
from ipfabric.tools import DeviceConfigs

with contextlib.suppress(ImportError):
    from rich import print

# Families handled by this script (IP Fabric family strings)
SUPPORTED_FAMILIES = ["arubacx", "arubasw"]

# Matches ANSI/CSI terminal control sequences (cursor moves, screen clears...),
# e.g. "\x1b[150;1H", "\x1b[2K", "\x1b[?25h". The arubasw logs are full of these
# and they fragment the command echo (show versi...on), so we strip them first.
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

# What to extract per family: the regex group "value" holds the version string.
FAMILY_RULES = {
    "arubacx": {"detail": "BIOS Version", "pattern": r"BIOS Version\s*:\s*(?P<value>\S+)"},
    "arubasw": {"detail": "Boot ROM Version", "pattern": r"Boot ROM Version\s*:\s*(?P<value>\S+)"},
}


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)


def extract_first_command_block(full_logs, hostname, prompt_delimiter, command):
    """Return the first complete output block for `command`, or None.

    Using .search() (first match only) means a log with the command repeated
    more than once still yields a single, complete block (from the first command
    echo up to the next prompt).
    """
    # Wrap the prompt delimiter in a non-capturing group so a multi-option
    # delimiter (e.g. "#|>") doesn't break the surrounding pattern's precedence.
    delim = rf"(?:{prompt_delimiter})"
    command_pattern = rf"({hostname}\S*{delim}\s*{command}.*?(?={hostname}\S*{delim}))"
    command_regex = re.compile(command_pattern, re.DOTALL)
    if command_section := command_regex.search(full_logs):
        return command_section[0].replace("\r\n", "\n")
    return None


def extract_os_detail(log, family, prompt_delimiter):
    """Extract the BIOS / Boot ROM version for a single device log."""
    rule = FAMILY_RULES[family]
    device_hostname = log["hostname"].split(".")[0]
    # Clean ANSI control sequences and the bell char before matching
    full_logs = strip_ansi(log["text"]).replace("\x07", "")

    command_section = extract_first_command_block(
        full_logs, device_hostname, prompt_delimiter, "show version"
    )
    # Fall back to the cleaned full log if the command echo can't be matched
    search_text = command_section if command_section is not None else full_logs

    value = "not found"
    if match := re.search(rule["pattern"], search_text):
        value = match.group("value").strip()

    return {
        "device": device_hostname,
        "family": family,
        "detail": rule["detail"],
        "value": value,
    }


def download_aruba_logs(logs, ipf_devices):
    """Download the IP Fabric text log for each supported Aruba device."""
    log_list = []
    total = len(ipf_devices)
    for index, host in enumerate(ipf_devices, start=1):
        if host["family"] not in SUPPORTED_FAMILIES:
            continue
        print(f"Downloading logs ({index}/{total}): {host['hostname']}")
        if dev_log := logs.get_text_log(host):
            log_list.append(
                {
                    "hostname": host["hostname"],
                    "sn": host["sn"],
                    "family": host["family"],
                }
                | {"text": dev_log}
            )
    return log_list


def save_to_csv(result, filename="os_details.csv"):
    if not result:
        print("No results to save.")
        return
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["device", "family", "detail", "value"])
        writer.writeheader()
        writer.writerows(result)
    print(f"\nCSV written to {filename}")


def main():
    # Load environment variables
    load_dotenv(find_dotenv(), override=True)
    prompt_delimiter = os.getenv("PROMPT_DELIMITER", "#|>")

    # DEVICES_FILTER is optional; default to all devices (families are filtered below)
    raw_filter = os.getenv("DEVICES_FILTER", "{}")
    try:
        device_filter = json.loads(raw_filter) if raw_filter else {}
    except json.JSONDecodeError as exc:
        print(f"##ERR## DEVICES_FILTER is not valid JSON: {exc}")
        return

    ipf_client = IPFClient(
        base_url=os.getenv("IPF_URL"),
        token=os.getenv("IPF_TOKEN"),
        snapshot_id=os.getenv("IPF_SNAPSHOT", "$last"),
        verify=(os.getenv("IPF_VERIFY", "False") == "True"),
        timeout=os.getenv("IPF_TIMEOUT", 60),
    )
    logs = DeviceConfigs(client=ipf_client)

    ipf_devices = ipf_client.inventory.devices.all(filters=device_filter)
    print(f"\nChecking {len(ipf_devices)} devices for families {SUPPORTED_FAMILIES}\n")

    log_list = download_aruba_logs(logs, ipf_devices)
    print(f"\nParsing {len(log_list)} Aruba log file(s)")

    result = [
        extract_os_detail(log, log["family"], prompt_delimiter) for log in log_list
    ]

    print(result)
    save_to_csv(result)


if __name__ == "__main__":
    main()
