"""
General Python3 script for IP Fabric's API to get the list of available log files and searches the specific input strings in it, prints the output.

2022-11 - version 1.0
Adaptation of the search_config script created by Milan. This time we won't look in the config backup, but in the logs
using ipfabric SDK
WARNING: you should make sure the SDK version matches your version of IP Fabric
"""

import json
import os
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from ipfabric import IPFClient
from ipfabric.tools import DeviceConfigs

from modules.logs_ipf import download_logs, search_logs

try:
    from rich import print
except ImportError:
    None

# Get Current Path
CURRENT_PATH = Path(os.path.realpath(os.path.dirname(sys.argv[0]))).resolve()
# testing only: CURRENT_PATH = Path(os.path.realpath(os.path.curdir)).resolve()
# Load environment variables
load_dotenv(os.path.join(CURRENT_PATH, ".env"), override=True)

app = typer.Typer(add_completion=False)
@app.command()

def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose mode."),
):
    """
    Script to look for a pattern, in a section, for a specific command output
    in the log file of IP Fabric
    """
    def valid_json(raw_data: str):
        """
        Confirm the env variable is a valid JSON. Return the json if OK, or exit.
        """
        try:
            json_data = json.loads(raw_data)
        except json.JSONDecodeError as exc:
            print(
                f"##ERR## The filter is not a valid JSON format: {exc}\n'{raw_data}'"
            )
            sys.exit()
        return json_data


    # Getting variables
    device_filter = valid_json(os.getenv("DEVICES_FILTER", "{}"))
    input_data = valid_json(os.getenv("INPUT_DATA"))

    # Getting data from IP Fabric and printing output
    ipf_client = IPFClient(
        base_url = os.getenv("IPF_URL"),
        token = os.getenv("IPF_TOKEN"),
        IPF_SNAPSHOT = os.getenv("IPF_SNAPSHOT", "$last"),
        verify = (os.getenv("IPF_VERIFY", "False")=="True"),
    )

    logs = DeviceConfigs(ipf_client)
    # Download log files for matching hostnames
    ipf_devices = ipf_client.inventory.devices.all(filters=device_filter)
    print(f"\nDOWNLOADING log files for {len(ipf_devices)} devices", end="")
    log_list = download_logs(logs, ipf_devices)

    # Search for specific strings in the log files
    result_ok = []
    result_nok = []
    print(f"\nSEARCHING through {len(log_list)} log files")
    for check in search_logs(input_data, log_list, verbose):
        if "YES" in check["found"]:
            result_ok.append(check)
        else:
            result_nok.append(check)
    print("\n------------- COMPLIANCE OK -------------")
    print(result_ok)
    print("\n!!!!!!!!!!!!! COMPLIANCE NOK !!!!!!!!!!!!!")
    print(result_nok)


if __name__ == "__main__":
    app()
