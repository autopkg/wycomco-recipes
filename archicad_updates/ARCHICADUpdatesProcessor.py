#!/usr/local/autopkg/python
# -*- coding: utf-8 -*-

"""
Copyright 2019 Zack T (mlbz521)
Fixed and ammended by jutonium for wycomco, copyright Aug 2020
Updated to adhere to coding standards by jutonium for wycomco Jan 23

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from __future__ import absolute_import, print_function

import json
import re

# pylint: disable=W0611
from autopkglib import Processor, ProcessorError, URLGetter  # noqa: F401

__all__ = ["ARCHICADUpdatesProcessor"]


# pylint: disable=E0239
# pylint: disable=R0903
class ARCHICADUpdatesProcessor(URLGetter):
    """
    This processor finds the URL for the desired version, localization, and
    type of ARCHICAD.
    """

    input_variables = {
        "major_version": {
            "required": True,
            "description": (
                "The ARCHICAD Major Version to look for available patches."
            ),
        },
        "localization": {
            "required": True,
            "description": "The Localization to looks for available patches.",
        },
        "release_type": {
            "required": True,
            "description": "The release type to look for available patches.",
        },
        "ARCHITECTURE": {
            "required": False,
            "description": "INTEL or ARM, falls back to INTEL if not set.",
        },
    }
    # Amended to output build number and version (jutonium)
    output_variables = {
        "url": {"description": "Returns the url to download."},
        "build": {"description": "Returns the build number."},
        "supported_architecture": {
            "description": "Returns a corresponding string for Munki"
        },
        "version": {
            "description": "Returns the version computed from major_version "
            "and build number. Same as CFBundleVersion."
        },
    }

    description = __doc__

    def main(self):
        """Main process."""

        # Define some variables.
        major_version = self.env.get("major_version")
        localization = self.env.get("localization")
        release_type = self.env.get("release_type")
        architecture = self.env.get("ARCHITECTURE", "INTEL")
        available_builds = {}

        # Grab the available public downloads page
        response = self.download(
            "https://graphisoft.com/de/service-support/downloads"
        )

        # Parse the html to get the retrieve the actual json data for the categories.
        json_response = re.search(
            r":categories='(.*)'", response.decode("utf-8")
        ).group(1)
        json_data = json.loads(json_response)

        # Parse through the available categories to identify the category id for updates.
        slug = None
        for json_object in json_data:
            slug = "update"

            if json_object.get("slug") == slug:
                category_id = json_object.get("id")

        if not slug or not category_id:
            raise ProcessorError(
                "Unable to find a url based on the type update."
            )

        # Parse the html to get the retrieve the actual json data for the platforms.
        json_response = re.search(
            r":platforms='(.*)'", response.decode("utf-8")
        ).group(1)
        json_data = json.loads(json_response)

        # Parse through the available platforms to identify the platform id
        # for the requested architecture.
        slug = None
        for json_object in json_data:
            if architecture == "INTEL":
                slug = "mac-intel-processor"
            elif architecture == "ARM":
                slug = "mac-apple-silicon"

            if json_object.get("slug") == slug:
                platform_id = json_object.get("id")

        if not slug or not platform_id:
            raise ProcessorError(
                "Unable to find a url based on the provided architecture."
            )

        # Parse the html to get the retrieve the actual json data for the downloads.
        json_response = re.search(
            r":downloads='(.*)'", response.decode("utf-8")
        ).group(1)
        json_data = json.loads(json_response)

        # Parse through the available downloads for versions that match the
        # requested paramters.
        for json_object in json_data:

            # Only proceed if json_object is a dict, some items seem to be lists.
            if not isinstance(json_object, dict):
                continue

            if all(
                (
                    json_object.get("category") == category_id,
                    json_object.get("version") == major_version,
                    json_object.get("locale") == localization,
                    json_object.get("edition") == release_type,
                    json_object.get("platform") == int(platform_id),
                    json_object.get("type") == "Archicad",
                    json_object.get("build"),
                )
            ):
                # Get the actual download url and map it to the build number.
                mac_link = json_object.get("data", {}).get("url")
                available_builds[str(json_object.get("build"))] = mac_link

        # Get the latest version.
        # Avoid unrelated errors and compute propper version
        if available_builds:
            build = sorted(available_builds.keys())[-1]
            version = f"{major_version}.0.0.{build}"
            url = available_builds[build]
            build = str(build)
        else:
            build = "0"
            version = "0"
            url = None

        if url:
            self.env["url"] = url
            self.output(f"Download URL: {url}")
            # Build and version instead of build as version
            self.env["build"] = build
            self.output(f"build: {build}")
            self.env["version"] = version
            self.output(f"version: {version}")
            if architecture == "ARM":
                self.env["supported_architecture"] = "arm64"
            else:
                self.env["supported_architecture"] = "x86_64"
        else:
            raise ProcessorError(
                "Unable to find a url based on the parameters provided."
            )


if __name__ == "__main__":
    PROCESSOR = ARCHICADUpdatesProcessor()
    PROCESSOR.execute_shell()
