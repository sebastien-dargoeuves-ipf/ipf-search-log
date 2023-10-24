"""
Set of functions to download log file from IP Fabric and search through those
2022-11 - version 1.0
2023-10 - version 2.0

We are checking the Administrative Mode of the interface, if it's access or not,
based on the output of the `show interface switchport`

Name: Gi1/0/14
Switchport: Enabled
Administrative Mode: static access

"""
import contextlib
import copy
import re

with contextlib.suppress(ImportError):
    from rich import print
from ipdb import set_trace as debug


def display_switchport_log_compliance(result: list):
    """
    Takes the result and display if an interfce is conigured via DHCP or not
    """
    result_ok = []
    result_nok = []
    for check in result:
        if "YES" in check["access"]:
            result_ok.append(check)
        else:
            result_nok.append(check)
    print("\n------------- ACCESS PORT -------------")
    print(result_ok)
    print("\n!!!!!!!!!!!!! NOT ACCESS PORT !!!!!!!!!!!!!")
    print(result_nok)


def get_device_interfaces(device: str, switchport_interfaces: list):
    """
    Returns a list of interface names for a given device.

    Args:
        device (str): The hostname of the device.
        switchport_interfaces (list): A list of switchport interfaces.

    Returns:
        list: A list of interface names for the given device.

    Examples:
        >>> get_device_interfaces('device1', [{'hostname': 'device1', 'intName': 'GigabitEthernet1/0/1'}, {'hostname': 'device2', 'intName': 'GigabitEthernet1/0/2'}])
        ['GigabitEthernet1/0/1']
    """

    return [
        interface["intName"]
        for interface in switchport_interfaces
        if interface["hostname"] == device
    ]


def search_switchport_logs(
    log_list, prompt_delimiter: str, switchport_interfaces: list, verbose: bool = False
):
    # sourcery skip: low-code-quality
    """A function to search for a specific list of string within the list of log files.
    Attributes:
    ----------
    input_strings: list of strings
        the list of strings to search for
    log_list: list of objects
        object items containing hostnames, log files, ..
    """
    result = []
    input_string = {
        "command": "show interface switchport",
        "match": "Administrative Mode: .*access",
    }  # technically we also need to search for "Administrative Mode: access" maybe play with regex once it's working
    for log in log_list:
        # debug()
        # for input_string in input_strings:
        # create a deepcopy to edit the item without affecting input_strings
        # if "command" in item.keys():
        # we extract the output for the specified command
        command_pattern = rf'({log["hostname"]}{prompt_delimiter}.{input_string["command"]}.*[\s\S]*?(?={log["hostname"]}{prompt_delimiter}))'
        command_regex = re.compile(command_pattern, re.MULTILINE)
        # Now we get the listi of interfaces for the device
        device_interfaces = get_device_interfaces(
            log["hostname"], switchport_interfaces
        )
        print(".", end="")
        for interface in device_interfaces:
            if command_section := command_regex.search(log["text"]):
                item = copy.deepcopy(input_string)
                item["hostname"] = log["hostname"]
                # we extract the section within the output of the command
                item["interface"] = interface
                pattern = rf"(^Name: {interface}([\s\S]*)Name:)"
                section_regex = re.compile(pattern, re.MULTILINE)
                if section := section_regex.search(command_section[0]):
                    # we search for `Administrative Mode: .*access` within the section
                    present_in_log = (
                        "YES" if re.search(item["match"], section[0]) else "NO"
                    )
                    if verbose:
                        item["matched_section"] = section[0]
                else:
                    present_in_log = "NOT IN SWITCHPORT OUTPUT"

            else:
                present_in_log = "COMMAND NOT FOUND"
            item["access"] = present_in_log
            if "command" in item.keys():
                del item["command"]
            if "match" in item.keys():
                del item["match"]
            result.append(item)
    print(" done!")
    return result
