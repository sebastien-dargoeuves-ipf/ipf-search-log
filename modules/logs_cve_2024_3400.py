import contextlib
import re

from ipfabric import IPFClient

with contextlib.suppress(ImportError):
    from rich import print


def display_cve_2024_3400(result: list):
    """
    Print the result
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

def get_os_version(ipf_devices, sn):
    return [device["version"] for device in ipf_devices if device["sn"] == sn][0]


def search_cve_2024_3400(
    ipf_client: IPFClient,
    ipf_devices: list,
    log_list,
    prompt_delimiter: str,
    verbose: bool = False,
):
    result = []
    for log in log_list:
        family = get_device_family(ipf_devices, log["sn"])
        version = get_os_version(ipf_devices, log["sn"])
        if family in ["pan-os"]:
            result.append(pan_os_config_cve_2024_3400(log, prompt_delimiter, version))
    return result


def pan_os_config_cve_2024_3400(log, prompt_delimiter, version):
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
        "command": "show config merged",
        "match": r"global-protect.*enable;"
        # "match": r"(global-protect[^{}*]*\{[^{}]*\})|(device-telemetry \{[^{}]*\})|(telemetry\senable;)"
    }
    # we search and extract the output for the show ip interface command
    hostname_altered = log["hostname"].split("/")[0] if "/" in log["hostname"] else log["hostname"]
    command_pattern = rf'(.*{hostname_altered}{prompt_delimiter}.*{input_string["command"]}.*[\s\S]*?(?=.*{hostname_altered}{prompt_delimiter}))'
    command_regex = re.compile(command_pattern, re.MULTILINE)

    if command_section := command_regex.search(log["text"]):
        pattern = re.compile(input_string["match"], re.MULTILINE)
        matches = pattern.findall(command_section[0])
    else:
        return {log["hostname"]: ""}

    output = [version]
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
            output.append(match.strip())
    return {log["hostname"]: output}
