import contextlib
import re

from ipfabric import IPFClient

with contextlib.suppress(ImportError):
    from rich import print


def display_password_encryption(result: list):
    """
    Takes the result and display if an interfce is conigured via DHCP or not
    """
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
    print(result)


def get_device_family(ipf_devices, sn):
    return [device["family"] for device in ipf_devices if device["sn"] == sn][0]


def find_password_encryption(
    ipf_client: IPFClient,
    ipf_devices: list,
    log_list,
    prompt_delimiter: str,
    verbose: bool = False,
):
    result = []
    for log in log_list:
        family = get_device_family(ipf_devices, log["sn"])
        if family == "ios-xe":
            result.append(iosxe_password_encryption(log, prompt_delimiter))
        elif family == "ios-xr":
            result.append(iosxr_password_encryption(log, prompt_delimiter))
        elif family == "nx-os":
            result.append(nxos_password_encryption(log, prompt_delimiter))
        elif family == "eos":
            result.append(eos_password_encryption(log, prompt_delimiter))
    return result


def iosxe_password_encryption(log, prompt_delimiter):
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
        "match": r"\benable password\s\d\s|username.*password\s\d\s|snmp-server.group.*\n|tacacs.server.*\r|radius.server.dnac*\r|.*key\s\d\s\b",
    }
    # we search and extract the output for the show ip interface command
    command_pattern = rf'(^{log["hostname"]}{prompt_delimiter}.{input_string["command"]}.*[\s\S]*?(?={log["hostname"]}{prompt_delimiter}))'
    command_regex = re.compile(command_pattern, re.MULTILINE)

    if command_section := command_regex.search(log["text"]):
        pattern = re.compile(input_string["match"])
        matches = pattern.findall(command_section[0])
    else:
        return {log["hostname"]: "No matches found"}

    output = []
    skip_next = False
    for i, match in enumerate(matches):
        if skip_next:
            skip_next = False
            continue
        # if it ends with a carriage return, it means it's a multi-line match, in which case we will append the next match to it
        if match.endswith("\r"):
            if i < len(matches) - 1:
                output.append(f"{match.strip()}: {matches[i + 1].strip()}")
                # key, value = f'{match.strip()}: {matches[i + 1].strip()}'.split(':')
                # output.append({key.strip(): value.strip()})
                skip_next = True
        else:
            output.append(
                match.replace(" password", ": password")
                .replace("server group", "server group:")
                .strip()
            )
            # key, value = match.replace(" password", ": password").replace("server group","server group:").strip().split(":")
            # output.append({key.strip(): value.strip()})
    return {log["hostname"]: output}


def iosxr_password_encryption(log, prompt_delimiter):
    """
    Searches for specific patterns in a log text and extracts relevant information.

    Args:
        log (dict): The log information containing the hostname and text.
        prompt_delimiter (str): The delimiter used in the command prompt.

    Returns:
        dict: A dictionary containing the hostname as the key and a list of extracted information as the value.
    """

    input_string = {
        "command": "show running-config",
        "match": r"\busername\s\w+|snmp-server.user.*\n|server-private.*\n|tacacs-server.host.*\n|key.chain.*\n|key-string\s\S+|.*secret\s\d+\s|.*key\s\S\s\S+\b",
    }
    # we search and extract the output for the show ip interface command
    command_pattern = rf'(:{log["hostname"]}{prompt_delimiter}.{input_string["command"]}.*[\s\S]*?(?={log["hostname"]}{prompt_delimiter}))'
    command_regex = re.compile(command_pattern, re.MULTILINE)
    # matches
    if command_section := command_regex.search(log["text"]):
        pattern = re.compile(input_string["match"])
        matches = pattern.findall(command_section[0])
    else:
        return {log["hostname"]: "No matches found"}

    output = []
    skip_next = False
    for i, match in enumerate(matches):
        if skip_next:
            skip_next = False
            continue
        # if it ends with a carriage return, it means it's a multi-line match, in which case we will append the next match to it
        for split_item in [
            "username",
            "tacacs-server host",
            "server-private",
            "key chain",
        ]:
            if split_item in match:
                # sometimes key is not configured in which case we need to indicate it's not found:
                # if matches[i + 1].startswith(" key") or matches[i + 1].startswith(" secret"):
                #     output.append(f'{match.strip()}: {matches[i + 1].strip()}')
                #     skip_next = True
                # else:
                #     match=f'{match.strip()}: key or secret not found'
                #     skip_next = False

                if (
                    re.match(r"^ *key", matches[i + 1])
                    or re.match(r"^ *secret", matches[i + 1])
                    or re.match(r"^ *key-string", matches[i + 1])
                ):
                    output.append(f"{match.strip()}: {matches[i + 1].strip()}")
                    skip_next = True
                else:
                    match = f"{match.strip()}: key or secret not found"

        if not skip_next:
            # output.append(match.replace(" password", ": password").replace("secret",": secret").strip())
            output.append(match.strip())
            # key, value = match.replace(" password", ": password").replace("server group","server group:").strip().split(":")
            # output.append({key.strip(): value.strip()})
    return {log["hostname"]: output}


def nxos_password_encryption(log, prompt_delimiter):
    """
    Searches for specific patterns in a log text and extracts relevant information.

    Args:
        log (dict): The log information containing the hostname and text.
        prompt_delimiter (str): The delimiter used in the command prompt.

    Returns:
        dict: A dictionary containing the hostname as the key and a list of extracted information as the value.
    """

    input_string = {
        "command": "show running-config",
        "match": r"\busername\s[\w\S]+\s\w+\s\d+|tacacs-server\shost\s\S+\skey\s\d+|snmp-server\suser\s[\w\S]+.*auth\s\w+\b",
    }
    # we search and extract the output for the show ip interface command
    command_pattern = rf'({log["hostname"]}{prompt_delimiter}\s{input_string["command"]}.*[\s\S]*?(?={log["hostname"]}{prompt_delimiter}))'
    command_regex = re.compile(command_pattern, re.MULTILINE)
    # matches
    if command_section := command_regex.search(log["text"]):
        pattern = re.compile(input_string["match"])
        matches = pattern.findall(command_section[0])
    else:
        return {log["hostname"]: "No matches found"}

    output = [match.strip() for match in matches]
    return {log["hostname"]: output}


def eos_password_encryption(log, prompt_delimiter):
    """
    Searches for specific patterns in a log text and extracts relevant information.

    Args:
        log (dict): The log information containing the hostname and text.
        prompt_delimiter (str): The delimiter used in the command prompt.

    Returns:
        dict: A dictionary containing the hostname as the key and a list of extracted information as the value.
    """

    input_string = {
        "command": "show running-config",
        "match": r"\busername.*secret\s\w+|tacacs-server\shost\s.*key\s\w+\s|.*\w+\skey\s\w+\s|.*\w+\spassword\s\w+\s|snmp-server\suser\s[\w\S]+.*auth\s\w+\b",
    }
    # we search and extract the output for the show ip interface command
    command_pattern = rf'(^{log["hostname"]}{prompt_delimiter}.{input_string["command"]}.*[\s\S]*?(?={log["hostname"]}{prompt_delimiter}))'
    command_regex = re.compile(command_pattern, re.MULTILINE)
    # matches
    if command_section := command_regex.search(log["text"]):
        pattern = re.compile(input_string["match"])
        matches = pattern.findall(command_section[0])
    else:
        return {log["hostname"]: "No matches found"}

    output = [match.strip() for match in matches]
    return {log["hostname"]: output}
