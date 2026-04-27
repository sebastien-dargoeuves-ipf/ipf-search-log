import contextlib
import re

import pandas as pd

with contextlib.suppress(ImportError):
    from rich import print


def display_temperature(result: list):
    """Takes the result and display it"""
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


def save_to_csv(result, title: str):
    # use pandas to save the result to a csv file
    df = pd.DataFrame(result)
    df.to_csv(f"{title}.csv", index=False)


def find_temperature(
    ipf_devices: list,
    log_list,
    prompt_delimiter: str,
    verbose: bool = False,
):
    result = []
    for log in log_list:
        family = get_device_family(ipf_devices, log["sn"])
        if family == "ios-xe":
            result.extend(iosxe_temperature(log=log, prompt_delimiter=prompt_delimiter))
        # IOS-XR not available as IPF does not execute the right command
        elif family in ["nx-os", "aci"]:
            result.extend(nxos_temperature(log=log, prompt_delimiter=prompt_delimiter))
        elif family == "junos":
            result.extend(junos_temperature(log, prompt_delimiter))
    try:
        save_to_csv(result, "temperature")
    except Exception as e:
        print(f"Error saving to CSV: {e}")
        # save as a json file
        with open("temperature.json", "w") as f:
            json_result = str(result).replace("'", '"')
            f.write(json_result)
        print("Saved as JSON file")
    
    return result


# def iosxr_temperature(log, prompt_delimiter):
#     """Searches for specific patterns in a log text and extracts relevant information.

#     Args:
#     ----
#         log (dict): The log information containing the hostname and text.
#         prompt_delimiter (str): The delimiter used in the command prompt.

#     Returns:
#     -------
#         dict: A dictionary containing the hostname as the key and a list of extracted information as the value.

#     """
#     input_string = {
#         "command": "show running-config",
#         "match": r"\busername\s\w+|snmp-server.user.*\n|server-private.*\n|tacacs-server.host.*\n|key.chain.*\n|key-string\s\S+|.*secret\s\d+\s|.*key\s\S\s\S+\b",
#     }
#     # we search and extract the output for the show ip interface command
#     command_pattern = rf'({log["hostname"]}{prompt_delimiter}\s*{input_string["command"]}.*?[\s\S]*?(?={log["hostname"]}{prompt_delimiter}))'
#     command_regex = re.compile(command_pattern, re.MULTILINE)
#     # matches
#     if command_section := command_regex.search(log["text"]):
#         pattern = re.compile(input_string["match"])
#         matches = pattern.findall(command_section[0])
#     else:
#         return {log["hostname"]: "No matches found"}

#     output = []
#     skip_next = False
#     for i, match in enumerate(matches):
#         if skip_next:
#             skip_next = False
#             continue
#         # if it ends with a carriage return, it means it's a multi-line match, in which case we will append the next match to it
#         for split_item in [
#             "username",
#             "tacacs-server host",
#             "server-private",
#             "key chain",
#         ]:
#             if split_item in match:
#                 # sometimes key is not configured in which case we need to indicate it's not found:
#                 # if matches[i + 1].startswith(" key") or matches[i + 1].startswith(" secret"):
#                 #     output.append(f'{match.strip()}: {matches[i + 1].strip()}')
#                 #     skip_next = True
#                 # else:
#                 #     match=f'{match.strip()}: key or secret not found'
#                 #     skip_next = False

#                 if (
#                     re.match(r"^ *key", matches[i + 1])
#                     or re.match(r"^ *secret", matches[i + 1])
#                     or re.match(r"^ *key-string", matches[i + 1])
#                 ):
#                     output.append(f"{match.strip()}: {matches[i + 1].strip()}")
#                     skip_next = True
#                 else:
#                     match = f"{match.strip()}: key or secret not found"

#         if not skip_next:
#             # output.append(match.replace(" password", ": password").replace("secret",": secret").strip())
#             output.append(match.strip())
#             # key, value = match.replace(" password", ": password").replace("server group","server group:").strip().split(":")
#             # output.append({key.strip(): value.strip()})
#     return {log["hostname"]: output}


def nxos_temperature(log, prompt_delimiter: str = "#"):
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
        "pattern": r"Temperature:?\n-+\nModule\s+Sensor\s+MajorThresh\s+MinorThres\s+CurTemp\s+Status\n\s*\(Celsius\)\s*\(Celsius\)\s*\(Celsius\)\s*\n-+\n(.*?)(?:\r|\n{2}|\n$)",
    }
    full_logs = log["text"].replace("\x07", "")
    device_hostname = log["hostname"].split(".")[0]
    # we search and extract the output for the specific command
    command_pattern = (
        rf'({device_hostname}\S*{prompt_delimiter}\s*{input_string["command"]}.*?(?={device_hostname}\S*{prompt_delimiter}))'
    )
    command_regex = re.compile(command_pattern, re.DOTALL)

    if not (command_section := command_regex.search(full_logs)):
        print(f"command not found for {device_hostname}")
        return [{
            "device": device_hostname,
            "module": "not found",
            "sensor": "not found",
            "location": "not found",
            "curTemp": "not found",
            "status": "not found",
        }]
    
    # Find all temperature sections
    command_section = command_section[0].replace("\r\n", "\n")
    regex_split = re.compile(r'\s{2,}')
    temperatures_result = []
    if temp_match := re.search(input_string["pattern"], command_section, re.DOTALL):
        for line in temp_match[1].strip().split("\n"):
            # sometimes the curTemp is not a digit but a string, due to some sensor name in ACI
            # the regex would need improving, but in the meantime, the workaround below seems ok
            parts = regex_split.split(line)
            if len(parts) >= 6:
                temperatures_result.append(
                    {
                        "device": device_hostname,
                        "module": parts[0],
                        "sensor": parts[1],
                        "location": "",
                        "curTemp": parts[4] if parts[4].isdigit() else parts[3],
                        "status": parts[5] if parts[4].isdigit() else parts[4],
                    },
                )

    # If the nexus has FEX, we need to extract the FEX temperature as well
    input_string = {
        "command": "show environment fex all",
        "fex_pattern": r"Temperature Fex (\d+):([\s\S]*?)(?=Fan Fex:?\s\d+:|$)",
        "sensor_pattern": r"(?P<module>\d+)\s+(?P<sensor>\w+-\w+)\s+(?P<majorThresh>\d+)\s+(?P<minorThresh>\d+)\s+(?P<curTemp>\d+)\s+(?P<status>\w+)",
    }

    # we search and extract the output for the specific command
    command_pattern = rf'({device_hostname}\S*{prompt_delimiter}\s*{input_string["command"]}.*?[\s\S]*?(?={device_hostname}\S*{prompt_delimiter}))'
    command_regex = re.compile(command_pattern, re.MULTILINE)
    if not (command_section := command_regex.search(full_logs)):
        print(f"command not found for {device_hostname}")
        return [{
            "device": device_hostname,
            "module": "not found",
            "sensor": "not found",
            "location": "not found",
            "curTemp": "not found",
            "status": "not found",
        }]
    command_section = command_section[0].replace("\r\n", "\n")

    # Find all FEX sections
    fex_matches = re.finditer(input_string["fex_pattern"], command_section, re.DOTALL)

    for fex_match in fex_matches:
        fex_number = fex_match.group(1)
        sensor_data_block = fex_match.group(2)

        # Find all sensor matches in the current FEX block
        sensor_matches = re.finditer(input_string["sensor_pattern"], sensor_data_block)
        # Prepare the list for the current FEX
        # result[f"{log['hostname']}-FEX{fex_number}"] = []
        for match in sensor_matches:
            sensor_data = {
                "device": f"{device_hostname}_FEX{fex_number}",
                "module": match.group("module"),
                "sensor": match.group("sensor"),
                "location": "",
                "curTemp": match.group("curTemp"),
                "status": match.group("status"),
            }
            # result[f"{log['hostname']}-FEX{fex_number}"].append(sensor_data)
            temperatures_result.append(sensor_data)
    return temperatures_result


def junos_temperature(log, prompt_delimiter: str = "#"):
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
        "command": "show chassis environment",
        # "match": r"Temp: (?P<sensor>[\w\s]+?)(?:\s{2,})(?P<location>\w+)\s+(?P<status>[\w\s]+)\s+(?P<curTemp>\d+)\s+Celsius", #iosxe example
        # "match": r"Temp\s+(?P<location>FPC \d+)\s+(?P<sensor>[\w\s\-]+)\s+(?P<status>OK)\s+(?P<curTemp>\d+)\s+degrees\s+C", #AI option1
        # "match": r"Temp\s+(?P<location>[\w\s]+?)\s+(?P<sensor>[\w\s\-]+)\s+(?P<status>OK)\s+(?P<curTemp>\d+)\s+degrees\s+C", #AI option2
        # "match": r'(?P<location>[\w\s]+\d+)\s+(?P<sensor>[\w\s\-]+)\s+(?P<status>[\w\s]+)\s+(?P<curTemp>\d+)\s+degrees\s+C', #AI option3
        # "match": r'(?P<location>[\w\s]+\d+)\s+(?P<sensor>[\w\s\-]+)\s+(?P<status>\w+)\s+(?P<curTemp>\d+)\s+degrees\s+C', #AI option4
        "match": r"(?=.*degrees\s+C)(?P<location>(?<!Temp)\s+(\w+\s\d+))\s+(?P<sensor>.*?)\s{2,}(?P<status>\w+)\s+(?P<curTemp>\d+)\s+degrees\s+C",  # AI option5 with lookahed
    }
    full_logs = log["text"].replace("\x07", "")
    # we search and extract the output for the show ip interface command
    command_pattern = rf'({log["hostname"]}{prompt_delimiter}\s*{input_string["command"]}.*?[\s\S]*?(?={log["hostname"]}{prompt_delimiter}))'
    command_regex = re.compile(command_pattern, re.MULTILINE)
    if not (command_section := command_regex.search(full_logs)):
        return {log["hostname"]: "No matches found"}
    command_section = command_section[0].replace("\r\n", "\n")

    pattern = re.compile(input_string["match"], re.MULTILINE)
    return [
        {
            "device": log["hostname"],
            "sensor": match.group("sensor").strip(),
            "location": match.group("location").strip(),
            "curTemp": match.group("curTemp").strip(),
            "status": match.group("status").strip(),
        }
        for match in pattern.finditer(command_section)
    ]


def iosxe_temperature(log, prompt_delimiter: str = "#"):
    """Searches for specific patterns in a log text and extracts relevant information.

    Args:
    ----
        log (dict): The log information containing the hostname and text.
        prompt_delimiter (str): The delimiter used in the command prompt.

    Returns:
    -------
        dict: A dictionary containing the hostname as the key and a list of extracted information as the value.

    """
    result = []
    input_string = {
        "command": "show env all",
        "match": r"Temp: (?P<sensor>[\w\s]+?)(?:\s{2,})(?P<location>\w+)\s+(?P<status>[\w\s]+)\s+(?P<curTemp>\d+)\s+Celsius",
    }
    full_logs = log["text"].replace("\x07", "")
    # we search and extract the output for the show ip interface command
    command_pattern = rf'({log["hostname"]}{prompt_delimiter}\s*{input_string["command"]}.*?[\s\S]*?(?={log["hostname"]}{prompt_delimiter}))'
    command_regex = re.compile(command_pattern, re.MULTILINE)
    if not (command_section := command_regex.search(full_logs)):
        return {log["hostname"]: "No matches found"}
    command_section = command_section[0].replace("\r\n", "\n")

    pattern = re.compile(input_string["match"], re.MULTILINE)
    result = [
        {
            "device": log["hostname"],
            "sensor": match.group("sensor").strip(),
            "location": match.group("location").strip(),
            "curTemp": match.group("curTemp").strip(),
            "status": match.group("status").strip(),
        }
        for match in pattern.finditer(command_section)
    ]

    # for the cat9k, output is different, so we need to search for the specific pattern
    if not result:
        cat9k_pattern = r"(?P<sensor>.+?)\s+(?P<location>\d+)\s+(?P<status>\w+)\s+(?P<curTemp>\d+)\sCelsius\s+(?P<minorThresh>\d)+\s*-\s*(?P<majorThresh>\d)+"

        pattern = re.compile(cat9k_pattern, re.MULTILINE)
        result = [
            {
                "device": log["hostname"],
                "sensor": match.group("sensor").strip(),
                "location": match.group("location").strip(),
                "curTemp": match.group("curTemp").strip(),
                "status": match.group("status").strip(),
            }
            for match in pattern.finditer(command_section)
        ]

    return result

# def ios_temperature(log, prompt_delimiter: str = "#"):
#     # Not implemented, it's currently a copy/paste of the iosxr regex, there are a lot of different output depending on the model with IOS.
