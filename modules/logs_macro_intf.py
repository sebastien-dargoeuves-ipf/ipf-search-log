import contextlib
import re

from ipfabric import IPFClient

with contextlib.suppress(ImportError):
    from rich import print


def display_interfaces_macro(result: list):
    """
    Takes the result and display if an interfce is conigured via DHCP or not
    """
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


def search_interfaces_macro(
    ipf_client: IPFClient,
    ipf_devices: list,
    log_list,
    prompt_delimiter: str,
    verbose: bool = False,
):
    result = []
    for log in log_list:
        family = get_device_family(ipf_devices, log["sn"])
        if family in ["ios-xe", "ios"]:
            result.append(ios_xe_interfaces_macro(log, prompt_delimiter, family))
        # elif family == "ios-xr":
        #     result.append(iosxr_interfaces_macro(log, prompt_delimiter))
        # elif family == "nx-os":
        #     result.append(nxos_interfaces_macro(log, prompt_delimiter))
        # elif family == "eos":
        #     result.append(eos_interfaces_macro(log, prompt_delimiter))
    return result


def ios_xe_interfaces_macro(log, prompt_delimiter, family):
    """
    Searches for specific patterns in a log text and extracts relevant information.

    Args:
        log (dict): The log information containing the hostname and text.
        prompt_delimiter (str): The delimiter used in the command prompt.

    Returns:
        dict: A dictionary containing the hostname as the key and a list of extracted information as the value.

    Examples:
        log = {
            "hostname": "Router1",
            "text": "enable password 1234\nusername admin password 5678\ntacacs.server 192.168.1.1\nkey 9876"
        }
        prompt = "# "
        result = iosxe_password_encryption(log, prompt)
        # Output: {"Router1": ["enable: 1234", "username admin: 5678", "tacacs.server: 192.168.1.1", "key: 9876"]}
    """

    input_string = {
        "command": "show running-config",
        "match": r"(?<!\$INTERFACE)\ninterface (\S+)[\s\S]*?macro description (\S+)",
    }
    # we search and extract the output for the show ip interface command

    command_pattern = rf'(^{log["hostname"]}{prompt_delimiter}.{input_string["command"]}.*[\s\S]*?(?={log["hostname"]}{prompt_delimiter}))'
    command_regex = re.compile(command_pattern, re.MULTILINE)

    if command_section := command_regex.search(log["text"]):
        pattern = re.compile(input_string["match"])
        matches = pattern.findall(command_section[0])
    else:
        return {log["hostname"]: "No matches found"}

    output = [{interfaces: macro} for interfaces, macro in matches]
    # output.append({"family": family})
    return {log["hostname"]: output}
