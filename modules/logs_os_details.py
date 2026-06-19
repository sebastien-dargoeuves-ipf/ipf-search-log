import contextlib
import re

import pandas as pd

with contextlib.suppress(ImportError):
    from rich import print


# Matches ANSI/CSI terminal control sequences (cursor moves, screen clears...),
# e.g. "\x1b[150;1H", "\x1b[2K", "\x1b[?25h". The repo only stripped the bell
# char so far, but the arubasw logs are full of these sequences.
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)


def get_device_family(ipf_devices, sn):
    return [device["family"] for device in ipf_devices if device["sn"] == sn][0]


def save_to_csv(result, title: str):
    # use pandas to save the result to a csv file
    df = pd.DataFrame(result)
    df.to_csv(f"{title}.csv", index=False)


def find_os_details(
    ipf_devices: list,
    log_list,
    prompt_delimiter: str,
    verbose: bool = False,
):
    result = []
    for log in log_list:
        family = get_device_family(ipf_devices, log["sn"])
        if family == "arubacx":
            result.extend(arubacx_os_details(log=log, prompt_delimiter=prompt_delimiter))
        elif family == "arubasw":
            result.extend(arubasw_os_details(log=log, prompt_delimiter=prompt_delimiter))
    try:
        save_to_csv(result, "os_details")
    except Exception as e:
        print(f"Error saving to CSV: {e}")
        # save as a json file
        with open("os_details.json", "w") as f:
            json_result = str(result).replace("'", '"')
            f.write(json_result)
        print("Saved as JSON file")

    return result


def _extract_first_command_block(full_logs, hostname, prompt_delimiter, command):
    """Return the first complete output block for `command`, or None.

    Using .search() (first match only) means a log with the command repeated more
    than once still yields a single, complete block (from the first command echo up
    to the next prompt).
    """
    # Wrap the prompt delimiter in a non-capturing group so a multi-option
    # delimiter (e.g. "#|>") doesn't break the surrounding pattern's precedence.
    delim = rf"(?:{prompt_delimiter})"
    command_pattern = rf"({hostname}\S*{delim}\s*{command}.*?(?={hostname}\S*{delim}))"
    command_regex = re.compile(command_pattern, re.DOTALL)
    if command_section := command_regex.search(full_logs):
        return command_section[0].replace("\r\n", "\n")
    return None


def arubacx_os_details(log, prompt_delimiter: str = "#"):
    """Extract the BIOS Version from the `show version` output of an AOS-CX device.

    Args:
    ----
        log (dict): The log information containing the hostname and text.
        prompt_delimiter (str): The delimiter used in the command prompt.

    Returns:
    -------
        list: A list with a single dict (normalized row) for the device.

    """
    detail = "BIOS Version"
    value_pattern = r"BIOS Version\s*:\s*(?P<value>\S+)"
    device_hostname = log["hostname"].split(".")[0]
    # Clean ANSI control sequences and the bell char before matching
    full_logs = strip_ansi(log["text"]).replace("\x07", "")

    command_section = _extract_first_command_block(
        full_logs, device_hostname, prompt_delimiter, "show version"
    )
    # Fall back to the cleaned full log if the command echo can't be matched
    search_text = command_section if command_section is not None else full_logs

    value = "not found"
    if match := re.search(value_pattern, search_text):
        value = match.group("value").strip()

    return [
        {
            "device": device_hostname,
            "family": "arubacx",
            "detail": detail,
            "value": value,
        }
    ]


def arubasw_os_details(log, prompt_delimiter: str = "#"):
    """Extract the Boot ROM Version from the `show version` output of an AOS-Switch device.

    Args:
    ----
        log (dict): The log information containing the hostname and text.
        prompt_delimiter (str): The delimiter used in the command prompt.

    Returns:
    -------
        list: A list with a single dict (normalized row) for the device.

    """
    detail = "Boot ROM Version"
    value_pattern = r"Boot ROM Version\s*:\s*(?P<value>\S+)"
    device_hostname = log["hostname"].split(".")[0]
    # ANSI stripping is essential here: the arubasw log interleaves cursor control
    # sequences with the text, fragmenting the command echo (show versi...on).
    full_logs = strip_ansi(log["text"]).replace("\x07", "")

    command_section = _extract_first_command_block(
        full_logs, device_hostname, prompt_delimiter, "show version"
    )
    # Fall back to the cleaned full log if the command echo can't be matched
    search_text = command_section if command_section is not None else full_logs

    value = "not found"
    if match := re.search(value_pattern, search_text):
        value = match.group("value").strip()

    return [
        {
            "device": device_hostname,
            "family": "arubasw",
            "detail": detail,
            "value": value,
        }
    ]
