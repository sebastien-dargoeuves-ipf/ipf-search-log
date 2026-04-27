import contextlib
import re

import pandas as pd
from ipfabric import IPFClient

with contextlib.suppress(ImportError):
    from rich import print


def display_interfaces_interfaces_pause_txrx(result: list):
    """Takes the result and display it"""
    new_result = [r for r in result if len(list(r.values())[0]) != 0]
    # result_ok = []
    # result_nok = []
    # for check in result:
    #     if check["found"] == "DHCP":
    #         result_ok.append(check)
    #     else:
    #         result_nok.append(check)
    # print("\n------------- INTERFACES with DHCP -------------")
    # print(result_ok)
    # print("\n!!!!!!!!!!!!! INTERFACES NOT with DHCP !!!!!!!!!!!!!")
    # print(result_nok)
    print(new_result)


def get_device_family(ipf_devices, sn):
    return [device["family"] for device in ipf_devices if device["sn"] == sn][0]

def get_devices_with_fex(ipf_client: IPFClient, ipf_devices: list):
    # Get all unique SN of devices with FEX modules
    sn_devices_with_fex = {
        parent_device['sn']
        for entry in ipf_client.technology.platforms.cisco_fex_modules.all()
        for parent_device in entry['parents']
    }

    return [
        device
        for device in ipf_devices
        if device['sn'] in sn_devices_with_fex
    ]

def save_to_csv(result, title: str):
    # use pandas to save the result to a csv file
    df = pd.DataFrame(result)
    df.to_csv(f"{title}.csv", index=False)

def find_pause_txrx(
    ipf_devices: list,
    log_list,
    prompt_delimiter: str,
    verbose: bool = False,
):
    result = []
    for log in log_list:
        family = get_device_family(ipf_devices, log["sn"])
        if family in ["nx-os"]:
            result.extend(nx_os_interfaces_pause_txrx(log, prompt_delimiter))
    try:
        save_to_csv(result, "FEX-TxRxPause")
    except Exception as e:
        print(f"Error saving to CSV: {e}")
        # save as a json file
        with open("FEX-TxRxPause.json", "w") as f:
            json_result = str(result).replace("'", '"')
            f.write(json_result)
        print("Saved as JSON file: FEX-TxRxPause.json")
    
    return result


def nx_os_interfaces_pause_txrx(log, prompt_delimiter):
    """Searches for specific patterns in a log text and extracts relevant information.

    Args:
    ----
        log (dict): The log information containing the hostname and text.
        prompt_delimiter (str): The delimiter used in the command prompt.

    Returns:
    -------
        dict: A dictionary containing the hostname as the key and a list of extracted information as the value.

    Examples:
    --------
        log = {
            "hostname": "Router1",
            "text": "enable password 1234\nusername admin password 5678\ntacacs.server 192.168.1.1\nkey 9876"
        }
        prompt = "# "
        result = iosxe_password_encryption(log, prompt)
        # Output: {"Router1": ["enable: 1234", "username admin: 5678", "tacacs.server: 192.168.1.1", "key: 9876"]}

    """
    input_string = {
        "command": "show interface",
        "match": r"(?P<interface>\w+(\d{3}/\d/\d+))\sis\s(?P<status>\w+)\s*.*?(?P<rx_pause>\d+)\sRx\spause.*?(?P<tx_pause>\d+)\sTx\spause",
        # the regex will only match FEX interfaces Ethernet123/1/1, it won't capture Ethernet1/1/1 or other interfaces
    }
    full_logs = log["text"].replace("\x07", "")
    # we search and extract the output for the show ip interface command
    command_pattern = rf'({log["hostname"]}{prompt_delimiter}\s*{input_string["command"]}.*?[\s\S]*?(?={log["hostname"]}{prompt_delimiter}))'
    command_regex = re.compile(command_pattern, re.MULTILINE)
    if not (command_section := command_regex.search(full_logs)):
        return {log["hostname"]: "No matches found"}
    command_section = command_section[0].replace("\r\n", "\n")

    pattern = re.compile(input_string["match"], re.DOTALL)
    # result = []
    # for match in pattern.finditer(command_section):
    #     print(match)
    #     result.append(
    #         {
    #             "device": log["hostname"],
    #             "interface": match.group("interface").strip(),
    #             "rxPause": match.group("rx_pause").strip(),
    #             "txPause": match.group("tx_pause").strip(),
    #             "status": match.group("status").strip(),
    #         }
    #     )
    # return result

    return [
        {
            "device": log["hostname"],
            "interface": match.group("interface").strip(),
            "rxPause": match.group("rx_pause").strip(),
            "txPause": match.group("tx_pause").strip(),
            "status": match.group("status").strip(),
        }
        for match in pattern.finditer(command_section)
        if match.group("tx_pause").strip() != "0" or match.group("rx_pause").strip() != "0"
    ]
