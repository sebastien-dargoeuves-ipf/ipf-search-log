"""
Set of functions to download log file from IP Fabric and search through those
2022-11 - version 1.0
"""

import contextlib
import copy
import re
from tqdm import tqdm

with contextlib.suppress(ImportError):
    from rich import print


def display_log_compliance(result: list):
    """
    Takes the result and display if an interfce is conigured via DHCP or not
    """
    result_ok = []
    result_nok = []
    for check in result:
        if "YES" in check["found"]:
            result_ok.append(check)
        else:
            result_nok.append(check)
    print("\n------------- COMPLIANCE OK -------------")
    print(result_ok)
    print("\n!!!!!!!!!!!!! COMPLIANCE NOT OK !!!!!!!!!!!!!")
    print(result_nok)


def download_logs(logs, ipf_devices: list, supported_families: list):
    """
    Function to download the IP Fabric log of provided list of devices
    """
    return_list = []
    progress_bar = tqdm(total=len(ipf_devices), desc="Downloading logs")
    for host in ipf_devices:
        progress_bar.update(1)
        if host["family"] not in supported_families:  # , "ios-xr", "nx-os", "eos"]:
            continue
        # Get the log file
        if dev_log := logs.get_text_log(host):
            return_list.append(
                {
                    **{
                        "hostname": host["hostname"],
                        "sn": host["sn"],
                        "text": dev_log,
                    },
                }
            )
    return return_list


def search_logs(input_strings, log_list, prompt_delimiter: str, verbose: bool = False):
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
    for log in log_list:
        for input_string in input_strings:
            # create a deepcopy to edit the item without affecting input_strings
            item = copy.deepcopy(input_string)
            item["hostname"] = log["hostname"]
            if "command" in item.keys():
                # we extract the output for the specified command
                command_pattern = rf'({log["hostname"]}{prompt_delimiter}.{item["command"]}.*[\s\S]*?(?={log["hostname"]}{prompt_delimiter}))'
                command_regex = re.compile(command_pattern, re.MULTILINE)
                if command_section := command_regex.search(log["text"]):
                    if "section" in item.keys():
                        # we extract the section within the output of the command
                        pattern = rf'(^{item["section"]}.*$[\n\r]*(?:^\s.*$[\n\r]*)*)'
                        section_regex = re.compile(pattern, re.MULTILINE)
                        if section := section_regex.search(command_section[0]):
                            present_in_log = (
                                "YES" if item["match"] in section[0] else "NO"
                            )
                            if verbose:
                                item["matched_section"] = section[0]
                        else:
                            present_in_log = "SECTION NOT FOUND"
                    else:
                        present_in_log = (
                            "YES - NO SECTION"
                            if item["match"] in command_section[0]
                            else "NO - NO SECTION"
                        )
                        if verbose:
                            item["matched_section"] = command_section[0]
                else:
                    present_in_log = "COMMAND NOT FOUND"
            else:
                present_in_log = "COMMAND NOT SPECIFIED"
            item["found"] = present_in_log
            result.append(item)
    return result
