#!/usr/local/autopkg/python

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

    def _get_category_id(self, response):
        """Extract and return the category ID for updates."""
        json_response = re.search(
            r":categories='(.*)'", response.decode("utf-8")
        ).group(1)
        json_data = json.loads(json_response)

        for json_object in json_data:
            if json_object.get("slug") == "update":
                return json_object.get("id")

        raise ProcessorError("Unable to find a url based on the type update.")

    def _get_platform_id(self, response, architecture):
        """Extract and return the platform ID for the architecture."""
        json_response = re.search(
            r":platforms='(.*)'", response.decode("utf-8")
        ).group(1)
        json_data = json.loads(json_response)

        if architecture == "INTEL":
            slug = "mac-intel-processor"
        elif architecture == "ARM":
            slug = "mac-apple-silicon"
        else:
            raise ProcessorError("Invalid architecture specified.")

        for json_object in json_data:
            if json_object.get("slug") == slug:
                return json_object.get("id")

        raise ProcessorError(
            "Unable to find a url based on the provided architecture."
        )

    def _find_available_builds(self, response, criteria):
        """Find and return available builds matching the criteria."""
        json_response = re.search(
            r":downloads='(.*)'", response.decode("utf-8")
        ).group(1)
        json_data = json.loads(json_response)
        available_builds = {}

        for json_object in json_data:
            if not isinstance(json_object, dict):
                continue

            if all(
                (
                    json_object.get("category") == criteria["category_id"],
                    json_object.get("version") == criteria["major_version"],
                    json_object.get("locale") == criteria["localization"],
                    json_object.get("edition") == criteria["release_type"],
                    json_object.get("platform")
                    == int(criteria["platform_id"]),
                    json_object.get("type") == "Archicad",
                    json_object.get("build"),
                )
            ):
                mac_link = json_object.get("data", {}).get("url")
                available_builds[str(json_object.get("build"))] = mac_link

        return available_builds

    def _set_output_variables(self, url, build, version, architecture):
        """Set output variables in the environment."""
        self.env["url"] = url
        self.output(f"Download URL: {url}")
        self.env["build"] = build
        self.output(f"build: {build}")
        self.env["version"] = version
        self.output(f"version: {version}")

        if architecture == "ARM":
            self.env["supported_architecture"] = "arm64"
        else:
            self.env["supported_architecture"] = "x86_64"

    def main(self):
        """Main process."""
        major_version = self.env.get("major_version")
        localization = self.env.get("localization")
        release_type = self.env.get("release_type")
        architecture = self.env.get("ARCHITECTURE", "INTEL")

        response = self.download(
            "https://graphisoft.com/de/service-support/"
            "downloads?section=update"
        )

        category_id = self._get_category_id(response)
        platform_id = self._get_platform_id(response, architecture)

        criteria = {
            "category_id": category_id,
            "platform_id": platform_id,
            "major_version": major_version,
            "localization": localization,
            "release_type": release_type,
        }
        available_builds = self._find_available_builds(response, criteria)

        if available_builds:
            build = sorted(available_builds.keys())[-1]
            version = f"{major_version}.0.0.{build}"
            url = available_builds[build]
            self._set_output_variables(url, build, version, architecture)
        else:
            raise ProcessorError(
                "Unable to find a url based on the parameters provided."
            )


if __name__ == "__main__":
    PROCESSOR = ARCHICADUpdatesProcessor()
    PROCESSOR.execute_shell()
