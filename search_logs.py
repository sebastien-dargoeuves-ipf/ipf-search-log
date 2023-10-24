"""
General Python3 script for IP Fabric's API to get the list of available
log files and searches the specific input strings in it, prints the output.

2022-11 - version 1.0
Adaptation of the search_config script created by Milan. This time
we won't look in the config backup, but in the logs

WARNING: you should make sure the SDK version matches your version of IP Fabric
"""


import contextlib
import json
import os
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from ipfabric import IPFClient
from ipfabric.tools import DeviceConfigs
from modules.logs_dhcp import search_dhcp_interfaces, display_dhcp_interfaces
from modules.logs_ipf import download_logs, search_logs, display_log_compliance
from modules.logs_switchport import (
    search_switchport_logs,
    display_switchport_log_compliance,
)

with contextlib.suppress(ImportError):
    from rich import print
# Get Current Path
CURRENT_PATH = Path(os.path.realpath(os.path.dirname(sys.argv[0]))).resolve()
# CURRENT_PATH = Path(os.path.realpath(os.path.curdir)).resolve() # for testing only

app = typer.Typer(add_completion=False)


@app.command()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose mode."),
    dhcp_intf: bool = typer.Option(
        False,
        "--dhcp-interfaces",
        "-d",
        help="Check for interfaces configured as DHCP client",
    ),
    switchport_intf: bool = typer.Option(
        False,
        "--switchport-interfaces",
        "-sw",
        help="Check switchport interfaces, access or not",
    ),
    file_output: str = typer.Option(
        None,
        "--file-output",
        "-fo",
        help="Write the output to a file",
    ),
):
    """
    Script to look for a pattern, in a section, for a specific command output
    in the log file of IP Fabric
    """

    def valid_json(raw_data: str):
        """
        Confirm the env variable is a valid JSON. Return the json if OK, or exit.
        """
        if not raw_data:
            print("##ERR## The `INPUT_DATA` is not in the .env file.")
            sys.exit()
        try:
            json_data = json.loads(raw_data)
        except json.JSONDecodeError as exc:
            print(f"##ERR## The `INPUT_DATA` is not a valid JSON.\n{exc}\n'{raw_data}'")
            sys.exit()
        return json_data

    # Load environment variables
    load_dotenv(os.path.join(CURRENT_PATH, ".env"), override=True)
    prompt_delimiter = os.getenv("PROMPT_DELIMITER")
    device_filter = valid_json(os.getenv("DEVICES_FILTER", "{}"))

    # Getting data from IP Fabric and printing output
    ipf_client = IPFClient(
        base_url=os.getenv("IPF_URL"),
        token=os.getenv("IPF_TOKEN"),
        snapshot_id=os.getenv("IPF_SNAPSHOT", "$last"),
        verify=(os.getenv("IPF_VERIFY", "False") == "True"),
    )

    logs = DeviceConfigs(ipf_client)
    # Download log files for matching hostnames
    ipf_devices = ipf_client.inventory.devices.all(filters=device_filter)
    print(f"\nDOWNLOADING log files for {len(ipf_devices)} devices", end="")
    log_list = download_logs(logs, ipf_devices)

    # Search for specific strings in the log files
    print(f"\nSEARCHING through {len(log_list)} log files")
    # Call the DHCP function, if the option is selected
    if dhcp_intf:
        result = search_dhcp_interfaces(ipf_client, log_list, prompt_delimiter, verbose)
        if not file_output:
            display_dhcp_interfaces(result)
    # Call the switchport function, if the option is selected
    elif switchport_intf:
        # Get the list of switchport interfaces filtered by the device_filter if it's based on hostname
        if "hostname" in device_filter.keys():
            print(
                f" and matching with all {ipf_client.technology.interfaces.switchport.count(filters=device_filter)} interfaces"
            )
            switchport_interfaces = ipf_client.technology.interfaces.switchport.all(
                columns=["hostname", "intName"], filters=device_filter
            )
        # Otherwise, we get the list of all switchport interfaces, as we can't filter.
        else:
            print(
                f" and matching with all {ipf_client.technology.interfaces.switchport.count()} interfaces"
            )
            switchport_interfaces = ipf_client.technology.interfaces.switchport.all(
                columns=["hostname", "intName"]
            )  # ,filters=device_filter)
        result = search_switchport_logs(
            log_list, prompt_delimiter, switchport_interfaces, verbose
        )
        if not file_output:
            display_switchport_log_compliance(result)
    # Otherwise, we perform the search as per the INPUT_DATA in the .env file
    else:
        input_data = valid_json(os.getenv("INPUT_DATA", ""))
        result = search_logs(input_data, log_list, prompt_delimiter, verbose)
        if not file_output:
            display_log_compliance(result)

    # Write the output to a file, if requested, in CSV or JSON format
    if file_output and file_output.endswith("csv"):
        # Write the output to a CSV file
        import csv

        print("CSV OUTPUT")
        with open(file_output, "w") as file:
            writer = csv.DictWriter(file, fieldnames=result[0].keys())
            writer.writeheader()
            writer.writerows(result)
    elif file_output:
        print("JSON OUTPUT")
        with open(file_output, "w") as file:
            json.dump(result, file, indent=4)
        print(f"\nOUTPUT written to {file_output}")

    if file_output and file_output.endswith("csv"):
        # Write the output to a CSV file
        import csv
        print("CSV OUTPUT")
        with open(file_output, "w") as file:
            writer = csv.DictWriter(file, fieldnames=result[0].keys())
            writer.writeheader()
            writer.writerows(result)
    elif file_output:
        print("JSON OUTPUT")
        with open(file_output, "w") as file:
            json.dump(result, file, indent=4)
        print(f"\nOUTPUT written to {file_output}")

if __name__ == "__main__":
    app()
