"""General Python3 script for IP Fabric's API to get the list of available
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

import typer
from dotenv import find_dotenv, load_dotenv
from ipfabric import IPFClient
from ipfabric.tools import DeviceConfigs

from modules.logs_cve_2024_3400 import display_cve_2024_3400, search_cve_2024_3400
from modules.logs_dhcp import display_dhcp_interfaces, search_dhcp_interfaces
from modules.logs_ipf import display_log_compliance, download_logs, search_logs
from modules.logs_macro_intf import display_interfaces_macro, search_interfaces_macro
from modules.logs_password_encryption import (
    display_password_encryption,
    find_password_encryption,
)
from modules.logs_switchport import (
    display_switchport_log_compliance,
    search_switchport_logs,
)
from modules.logs_temperature import find_temperature
from modules.logs_intf_last_counters import find_interfaces_last_counters
from modules.logs_intf_pause_txrx import get_devices_with_fex, find_pause_txrx

with contextlib.suppress(ImportError):
    from rich import print

app = typer.Typer(add_completion=False)


@app.command()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose mode."),
    dhcp_intf: bool = typer.Option(
        False,
        "--dhcp-interfaces",
        "-dhcp",
        help="Check for interfaces configured as DHCP client",
    ),
    switchport_intf: bool = typer.Option(
        False,
        "--switchport-interfaces",
        "-sw",
        help="Check switchport interfaces, access or not",
    ),
    password_level: bool = typer.Option(
        False,
        "--password-encryption",
        "-pwd",
        help="Check the password level of the devices",
    ),
    macro_intf: bool = typer.Option(
        False,
        "--macro-interfaces",
        "-macro",
        help="Check if a Macro is assigned to the interface",
    ),
    temperature: bool = typer.Option(
        False,
        "--temperature",
        "-temp",
        help="Check the temperatures of the different modules",
    ),
    pause_counter_interf: bool = typer.Option(
        False,
        "--pause-counter-interfaces",
        "-pause",
        help="Check Rx/Tx pause counters on interfaces",
    ),
    # used_counter_interf: bool = typer.Option(
    #     False,
    #     "--used-counter-interfaces",
    #     "-used",
    #     help="Check last input/output counters on interfaces",
    # ),
    cve_2024_3400: bool = typer.Option(
        False,
        "--cve-2024-3400",
        "-cve3400",
        help="Check for Palo Alto CVE-2024-3400 vulnerabilities (https://security.paloaltonetworks.com/CVE-2024-3400)",
    ),
    file_output: str = typer.Option(
        None,
        "--file-output",
        "-fo",
        help="Write the output to a file",
    ),
):
    """Script to look for a pattern, in a section, for a specific command output
    in the log file of IP Fabric
    """

    def valid_json(raw_data: str):
        """Confirm the env variable is a valid JSON. Return the json if OK, or exit."""
        if not raw_data:
            print("##ERR## The `INPUT_DATA` is not in the .env file.")
            sys.exit()
        try:
            json_data = json.loads(raw_data)
        except json.JSONDecodeError as exc:
            print(f"##ERR## The `INPUT_DATA` is not a valid JSON.\n{exc}\n'{raw_data}'")
            sys.exit()
        return json_data

    def get_logs_supported_devices(ipf_devices, supported_families):
        # Download log files for matching hostnames
        print(
            f"\nDOWNLOADING relevant log files, checking {len(ipf_devices)} devices\n",
            end="",
        )
        log_list = download_logs(logs, ipf_devices, supported_families)
        # Search for specific strings in the log files
        print(f"\nSEARCHING through {len(log_list)} log files")
        return log_list

    # Load environment variables
    load_dotenv(find_dotenv(), override=True)
    prompt_delimiter = os.getenv("PROMPT_DELIMITER")
    device_filter = valid_json(os.getenv("DEVICES_FILTER", "{}"))

    # Getting data from IP Fabric and printing output
    ipf_client = IPFClient(
        base_url=os.getenv("IPF_URL"),
        token=os.getenv("IPF_TOKEN"),
        snapshot_id=os.getenv("IPF_SNAPSHOT", "$last"),
        verify=(os.getenv("IPF_VERIFY", "False") == "True"),
        timeout=os.getenv("IPF_TIMEOUT", 60)
    )

    logs = DeviceConfigs(client=ipf_client)
    ipf_devices = ipf_client.inventory.devices.all(filters=device_filter)
    # Call the DHCP function, if the option is selected
    if dhcp_intf:
        supported_families = ["ios-xe", "ios", "ios-xr", "nx-os"]
        log_list = get_logs_supported_devices(ipf_devices, supported_families)
        result = search_dhcp_interfaces(ipf_client, log_list, prompt_delimiter, verbose)
        if not file_output:
            display_dhcp_interfaces(result)
    # Call the switchport function, if the option is selected
    elif switchport_intf:
        supported_families = ["ios-xe", "ios", "ios-xr", "nx-os"]
        log_list = get_logs_supported_devices(ipf_devices, supported_families)
        # Get the list of switchport interfaces filtered by the device_filter if it's based on hostname
        if "hostname" in device_filter.keys():
            print(
                f" and matching with all {ipf_client.technology.interfaces.switchport.count(filters=device_filter)} interfaces",
            )
            switchport_interfaces = ipf_client.technology.interfaces.switchport.all(
                columns=["hostname", "intName"],
                filters=device_filter,
            )
        # Otherwise, we get the list of all switchport interfaces, as we can't filter.
        else:
            print(f" and matching with all {ipf_client.technology.interfaces.switchport.count()} interfaces")
            switchport_interfaces = ipf_client.technology.interfaces.switchport.all(
                columns=["hostname", "intName"],
            )  # ,filters=device_filter)
        result = search_switchport_logs(log_list, prompt_delimiter, switchport_interfaces, verbose)
        if not file_output:
            display_switchport_log_compliance(result)
    elif password_level:
        supported_families = ["ios-xe", "ios", "ios-xr", "nx-os", "eos"]
        log_list = get_logs_supported_devices(ipf_devices, supported_families)
        result = find_password_encryption(ipf_client, ipf_devices, log_list, prompt_delimiter, verbose)
        if not file_output:
            display_password_encryption(result)
    elif macro_intf:
        supported_families = ["ios-xe", "ios"]
        log_list = get_logs_supported_devices(ipf_devices, supported_families)
        result = search_interfaces_macro(ipf_client, ipf_devices, log_list, prompt_delimiter, verbose)
        if not file_output:
            display_interfaces_macro(result)
    elif cve_2024_3400:
        supported_families = ["pan-os"]
        log_list = get_logs_supported_devices(ipf_devices, supported_families)
        result = search_cve_2024_3400(
            ipf_client=ipf_client,
            ipf_devices=ipf_devices,
            log_list=log_list,
            prompt_delimiter=prompt_delimiter,
            verbose=verbose,
        )
        if not file_output:
            display_cve_2024_3400(result)
    elif temperature:
        # supported_families = ["ios-xe", "ios", "ios-xr", "nx-os", "aci", "juniper", "arubasw"]
        supported_families = ["nx-os", "aci", "ios-xe", "junos"]
        log_list = get_logs_supported_devices(ipf_devices, supported_families)
        result = find_temperature(
            ipf_devices=ipf_devices,
            log_list=log_list,
            prompt_delimiter=prompt_delimiter,
            verbose=verbose,
        )
    elif pause_counter_interf:
        # We only want to check devices with FEX modules
        devices_with_fex = get_devices_with_fex(ipf_client, ipf_devices)
        supported_families = ["nx-os"]
        log_list = get_logs_supported_devices(devices_with_fex, supported_families)
        result = find_pause_txrx(
            ipf_devices=devices_with_fex,
            log_list=log_list,
            prompt_delimiter=prompt_delimiter,
            verbose=verbose,
        )
    # elif used_counter_interf:
    #     # supported_families = ["ios-xe", "ios", "ios-xr", "nx-os", "aci", "juniper", "arubasw"]
    #     supported_families = ["nx-os", "aci", "ios-xe"]
    #     log_list = get_logs_supported_devices(ipf_devices, supported_families)
    #     result = find_interfaces_last_counters(
    #         ipf_devices=ipf_devices,
    #         log_list=log_list,
    #         prompt_delimiter=prompt_delimiter,
    #         verbose=verbose,
    #     )
    
    # Otherwise, we perform the search as per the INPUT_DATA in the .env file
    else:
        input_data = valid_json(os.getenv("INPUT_DATA", ""))
        result = search_logs(input_data, log_list, prompt_delimiter, verbose)
        if not file_output:
            display_log_compliance(result)

    # Write the output to a file, if requested, in CSV or JSON format
    # if file_output and file_output.endswith("csv"):
    #     # Write the output to a CSV file
    #     import csv
    #     with open(file_output, "w") as file:
    #         writer = csv.DictWriter(file, fieldnames=result[0].keys())
    #         writer.writeheader()
    #         writer.writerows(result)
    #     print(f"\nCSV OUTPUT written to {file_output}")
    # el
    if file_output:
        # Write the output to a JSON file
        with open(file_output, "w") as file:
            json.dump(result, file, indent=4)
        print(f"\nJSON OUTPUT written to {file_output}")


if __name__ == "__main__":
    app()
