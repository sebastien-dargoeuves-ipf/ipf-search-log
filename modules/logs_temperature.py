import contextlib
import re

from ipfabric import IPFClient

with contextlib.suppress(ImportError):
    from rich import print


def display_temperature(result: list):
    """Takes the result and display if an interfce is conigured via DHCP or not
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


def find_temperature(
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
            result.append(iosxe_temperature(log, prompt_delimiter))
        elif family == "ios-xr":
            result.append(iosxr_temperature(log, prompt_delimiter))
        elif family == "nx-os":
            result.append(nxos_temperature(log, prompt_delimiter))
        # elif family == "junos":
        #     result.append(junos_temperature(log, prompt_delimiter))
    return result


def iosxr_temperature(log, prompt_delimiter):
    """Searches for specific patterns in a log text and extracts relevant information.

    Args:
    ----
        log (dict): The log information containing the hostname and text.
        prompt_delimiter (str): The delimiter used in the command prompt.

    Returns:
    -------
        dict: A dictionary containing the hostname as the key and a list of extracted information as the value.

    """
    input_string = {
        "command": "show running-config",
        "match": r"\busername\s\w+|snmp-server.user.*\n|server-private.*\n|tacacs-server.host.*\n|key.chain.*\n|key-string\s\S+|.*secret\s\d+\s|.*key\s\S\s\S+\b",
    }
    # we search and extract the output for the show ip interface command
    command_pattern = rf'({log["hostname"]}{prompt_delimiter}\s*{input_string["command"]}.*?[\s\S]*?(?={log["hostname"]}{prompt_delimiter}))'
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


def nxos_temperature(log, prompt_delimiter):
    """Searches for specific patterns in a log text and extracts relevant information.

    Args:
    ----
        log (dict): The log information containing the hostname and text.
        prompt_delimiter (str): The delimiter used in the command prompt.

    Returns:
    -------
        dict: A dictionary containing the hostname as the key and a list of extracted information as the value.

    """
    input_string = {
        "command": "show environment",
        "match": r"Temperature\n-+\nModule\s+Sensor\s+MajorThresh\s+MinorThres\s+CurTemp\s+Status\n\s*\(Celsius\)\s*\(Celsius\)\s*\(Celsius\)\s*\n-+\n(.*?)\n\n",
    }
    full_logs = log["text"].replace("\x07", "")
    # we search and extract the output for the show ip interface command
    command_pattern = rf'({log["hostname"]}{prompt_delimiter}\s*{input_string["command"]}.*?[\s\S]*?(?={log["hostname"]}{prompt_delimiter}))'
    command_regex = re.compile(command_pattern, re.MULTILINE)
    if not (command_section := command_regex.search(full_logs)):
        return {log["hostname"]: "No matches found"}
    command_section = command_section[0].replace("\r\n", "\n")
    temperatures = []

    if temp_match := re.search(input_string["match"], command_section, re.DOTALL):
        for line in temp_match[1].strip().split("\n"):
            parts = line.split()
            if len(parts) >= 6:
                temperatures.append(
                    {
                        "module": parts[0],
                        "sensor": parts[1],
                        "major_threshold": parts[2],
                        "minor_threshold": parts[3],
                        "temp": parts[4],
                        "status": parts[5],
                    },
                )

    # print(f'host: {log["hostname"]}\n{temperatures}')
    return {log["hostname"]: temperatures}

def iosxe_temperature(log, prompt_delimiter):
    """Searches for specific patterns in a log text and extracts relevant information.

    Args:
    ----
        log (dict): The log information containing the hostname and text.
        prompt_delimiter (str): The delimiter used in the command prompt.

    Returns:
    -------
        dict: A dictionary containing the hostname as the key and a list of extracted information as the value.

    """
    input_string = {
        "command": "show env all",
        "match": r"Temp: ([\w\s]+?)(?:\s{2,})(\w+)\s+([\w\s]+)\s+(\d+)\s+Celsius",
        # "match": r"^.*Temp: (.*)$",
    }
    full_logs = log["text"].replace("\x07", "")
    # we search and extract the output for the show ip interface command
    command_pattern = rf'({log["hostname"]}{prompt_delimiter}\s*{input_string["command"]}.*?[\s\S]*?(?={log["hostname"]}{prompt_delimiter}))'
    command_regex = re.compile(command_pattern, re.MULTILINE)
    if not (command_section := command_regex.search(full_logs)):
        return {log["hostname"]: "No matches found"}
    command_section = command_section[0].replace("\r\n", "\n")

    pattern = re.compile(input_string["match"], re.MULTILINE)
    temperatures = []
    for match in pattern.finditer(command_section):
        temperatures.append({
            'sensor': match.group(1).strip(),
            'location': match.group(2).strip(),
            'state': match.group(3).strip(),
            'temp': match.group(4).strip()
        })
    
    return temperatures

    # Parse each temperature line into a structured format
    temp_lines = re.findall(input_string["match"], command_section, re.MULTILINE)
    temperatures = []
    for line in temp_lines:
        # Split the line into components
        parts = line.split()
        
        # Ensure we have enough parts to parse
        if len(parts) >= 5:
            from ipdb import set_trace as debug; debug()
            temperatures.append({
                'sensor': ' '.join(parts[1:3]).strip(':'),  # Combine "Temp:" and sensor name
                'location': parts[3],
                'state': parts[4],
                'reading': parts[5] if len(parts) > 5 else None
            })

    # print(f'host: {log["hostname"]}\n{temperatures}')
    return {log["hostname"]: temperatures}
