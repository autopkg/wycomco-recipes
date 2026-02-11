#!/usr/local/autopkg/python
#
# Copyright 2022 wycomco GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""See docstring for MunkiAutoStaging class"""

# pylint: disable=E0401
# pylint: disable=W4901
import glob
import os
import plistlib
from datetime import datetime, timedelta
from distutils.version import StrictVersion

from autopkglib import Processor, ProcessorError
from autopkglib.munkirepolibs.AutoPkgLib import AutoPkgLib
from autopkglib.munkirepolibs.MunkiLib import MunkiLib

__all__ = ["MunkiAutoStaging"]


def _find_matching_item(repo_library, name):
    """Searches all catalogs for items matching the named one.
    Returns a list of all matching items if found."""

    pkgdb = repo_library.make_catalog_db()

    if not name:
        return pkgdb["items"]

    matching_items = []

    for item in pkgdb["items"]:
        if item["name"] == name:
            matching_items.append(item)

    return matching_items


def _fetch_repo_library(
    munki_repo,
    munki_repo_plugin,
    munkilib_dir,
    repo_subdirectory,
    force_munki_lib,
):
    if munki_repo_plugin == "FileRepo" and not force_munki_lib:
        return AutoPkgLib(munki_repo, repo_subdirectory)

    return MunkiLib(
        munki_repo, munki_repo_plugin, munkilib_dir, repo_subdirectory
    )


class MunkiAutoStaging(Processor):
    """This processor will automatically move all given Munki items from a
    testing catalog to a production catalog after a given amount of days."""

    description = __doc__
    input_variables = {
        "MUNKI_REPO": {
            "description": "Path to a mounted Munki repo.",
            "required": True,
        },
        "MUNKI_REPO_PLUGIN": {
            "description": (
                "Munki repo plugin. Defaults to FileRepo. Munki must be "
                "installed and available at MUNKILIB_DIR if a plugin other "
                "than FileRepo is specified."
            ),
            "required": False,
            "default": "FileRepo",
        },
        "MUNKI_REPO_SUBDIR": {
            "description": (
                "Subdirectory of Munki repo, useful for large repositories."
            ),
            "required": False,
            "default": "",
        },
        "MUNKILIB_DIR": {
            "description": (
                "Directory path that contains munkilib. Defaults to "
                "/usr/local/munki"
            ),
            "required": False,
            "default": "/usr/local/munki",
        },
        "MUNKI_PKGINFO_FILE_EXTENSION": {
            "description": (
                "Extension for output pkginfo files. Default is 'plist'.",
            ),
            "required": False,
            "default": "plist",
        },
        "MUNKI_STAGING_CATALOG": {
            "description": (
                "Name of the staging catalog. Defaults to testing"
            ),
            "required": False,
            "default": "testing",
        },
        "MUNKI_PRODUCTION_CATALOG": {
            "description": (
                "Name of the production catalog. Defaults to production"
            ),
            "required": False,
            "default": "production",
        },
        "MUNKI_STAGING_DAYS": {
            "description": (
                "Amount of days as float to keep a new item in the staging"
                "catalog."
                "Staging depends on the timestamp of the munki import. To "
                "allow some wiggle room for varying runtimes use e.g. 4.9 "
                "instead of 5 days."
                "Defaults to 5.0"
            ),
            "required": False,
            "default": 5.0,
        },
        "NAME": {
            "description": ("Name of the Munki item to be checked."),
            "required": True,
        },
        "force_munki_repo_lib": {
            "description": (
                "When True, munki code libraries will be utilized when the "
                "FileRepo plugin is used. Munki must be installed and "
                "available at MUNKILIB_DIR"
            ),
            "required": False,
            "default": False,
        },
    }
    output_variables = {
        "munki_repo_changed": {"description": "True if an item was updated."},
        "munki_autostaging_summary_result": {
            "description": "Description of interesting results."
        },
    }

    def _find_pkginfo_files_in_repo(self, pkginfo, file_extension="plist"):
        """Returns the full path to pkginfo file in the repo."""

        destination_path = os.path.join(self.env["MUNKI_REPO"], "pkgsinfo")

        if not os.path.exists(destination_path):
            raise ProcessorError(
                f"Did not find pkgsinfo directory at {destination_path}"
            )

        if len(file_extension) > 0:
            name = pkginfo.get("name", None)
            self.output(
                f"Adding {file_extension} to filename for {name}...", 2
            )
            file_extension = "." + file_extension.strip(".")

        pkginfo_basename = f"{pkginfo['name']}-{pkginfo['version'].strip()}"

        self.output(
            "Searching through repository for a file named "
            f"{pkginfo_basename} with an extension of {file_extension}",
            2,
        )

        file_list = glob.iglob(
            os.path.join(
                destination_path, "**", f"{pkginfo_basename}*{file_extension}"
            ),
            recursive=True,
        )

        return file_list

    def _find_items_to_promote(self, repo_library):
        """Finds and returns all pkginfo files which may be promoted to
        production catalog"""

        items = _find_matching_item(repo_library, self.env["NAME"])

        items_to_promote = []

        for item in items:
            if "catalogs" not in item:
                self.output(
                    "Did not find any catalogs in item with name "
                    f"{item['name']}...",
                    2,
                )
                continue

            if self.env["MUNKI_STAGING_CATALOG"] not in item["catalogs"]:
                self.output(
                    "Did not find staging catalog in item with name "
                    f"{item['name']}...",
                    2,
                )
                continue

            files = self._find_pkginfo_files_in_repo(
                item, self.env["MUNKI_PKGINFO_FILE_EXTENSION"]
            )

            for file in files:
                self.output(f"Opening file {file}...", 2)
                with open(file, "rb") as file_handler:
                    pkginfo = plistlib.load(file_handler)
                    file_handler.close()

                self.output("Checking pkginfo for staging catalog...", 2)
                if ("catalogs" not in pkginfo) or (
                    self.env["MUNKI_STAGING_CATALOG"]
                    not in pkginfo["catalogs"]
                ):
                    self.output(
                        "No catalog or no staging catalog found... skipping.",
                        2,
                    )
                    continue

                self.output("Checking _metadata for creation_date...", 2)
                if ("_metadata" not in pkginfo) or (
                    "creation_date" not in pkginfo["_metadata"]
                ):
                    self.output(
                        "No _metadata or no creation_date found... skipping.",
                        2,
                    )
                    continue

                period = timedelta(float(self.env["MUNKI_STAGING_DAYS"]))
                delta = datetime.now() - pkginfo["_metadata"]["creation_date"]

                if delta > period:
                    self.output(f"Found item to promote at {file}")
                    items_to_promote.append(file)
                else:
                    self.output(
                        f"Item {file} is too young to promote... skipping", 1
                    )

        return items_to_promote

    def promote_items(self, repo_library):
        """Promotes all pkginfo items matching the given criteria to
        production catalog"""

        files = self._find_items_to_promote(repo_library)

        versions_promoted = []

        for file in files:
            with open(file, "rb") as file_handler:
                pkginfo = plistlib.load(file_handler)
                file_handler.close()

            pkginfo["catalogs"].remove(self.env["MUNKI_STAGING_CATALOG"])
            pkginfo["catalogs"].append(self.env["MUNKI_PRODUCTION_CATALOG"])
            pkginfo["_metadata"]["promoted_by"] = os.getlogin()
            pkginfo["_metadata"]["promotion_date"] = datetime.now()

            versions_promoted.append(pkginfo["version"])

            with open(file, "wb") as file_handler:
                plistlib.dump(pkginfo, file_handler)
                file_handler.close()

        return versions_promoted

    def main(self):
        """Will promote all pkginfo file to production catalog which have
        been in staging catalog for the given amount of days"""
        try:
            library = _fetch_repo_library(
                self.env["MUNKI_REPO"],
                self.env["MUNKI_REPO_PLUGIN"],
                self.env["MUNKILIB_DIR"],
                self.env["MUNKI_REPO_SUBDIR"],
                self.env["force_munki_repo_lib"],
            )

            self.output(f"Using repo lib: {library.__class__.__name__}")
            self.output(f'        plugin: {self.env["MUNKI_REPO_PLUGIN"]}')
            self.output(f'          repo: {self.env["MUNKI_REPO"]}')

            # clear any pre-existing summary result
            if "munki_autostaging_summary_result" in self.env:
                del self.env["munki_autostaging_summary_result"]

            versions_promoted = self.promote_items(library)
            versions_promoted.sort(key=StrictVersion, reverse=True)

            if len(versions_promoted) > 0:
                self.env["munki_repo_changed"] = True

                self.env["munki_autostaging_summary_result"] = {
                    "summary_text": ("The following new items were promoted:"),
                    "report_fields": [
                        "name",
                        "versions",
                        "staging_catalog",
                        "production_catalog",
                    ],
                    "data": {
                        "name": self.env["NAME"],
                        "versions": ", ".join(versions_promoted),
                        "staging_catalog": self.env["MUNKI_STAGING_CATALOG"],
                        "production_catalog": self.env[
                            "MUNKI_PRODUCTION_CATALOG"
                        ],
                    },
                }

            else:
                if "munki_repo_changed" not in self.env:
                    self.env["munki_repo_changed"] = False

        except Exception as err:
            # handle unexpected errors here
            raise ProcessorError(err) from err


if __name__ == "__main__":
    PROCESSOR = MunkiAutoStaging()
    PROCESSOR.execute_shell()
