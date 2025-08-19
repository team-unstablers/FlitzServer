#!/usr/bin/env python3

import os
import json

def get_dependencies_licenses():
    """
    Get the licenses of the dependencies in the project.

    Returns:
        dict: A dictionary containing the licenses of each dependency.
    """
    # Run pip-licenses command to get licenses in JSON format
    result = os.popen('pip-licenses --format=json --with-urls --with-license-file').read()

    # Parse the JSON output
    licenses = json.loads(result)

    return licenses


if __name__ == '__main__':
    licenses = get_dependencies_licenses()

    for license in licenses:
        print(f"### {license['Name']}")
        print()
        print(license['URL'])
        print()
        print('```')
        print(license['LicenseText'])
        print('```')
        print()


