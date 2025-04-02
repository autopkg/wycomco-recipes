#!/usr/local/autopkg/python

"""
Copyright 2022 bock@wycomco.de
Inspiration taken from and looseley based on JamfUploaderTeamsNotifier.py by
Graham Pugh, Jacob Burley

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
import subprocess
from time import sleep

from autopkglib import ProcessorError
from autopkglib.URLGetter import URLGetter

__all__ = ["MunkiRepoTeamsNotifier"]


class MunkiRepoTeamsNotifier(URLGetter):
    description = (
        "Posts changes to Teams via webhook based on output of a "
        "MunkiImporter or MunkiAutoStaging process."
    )
    input_variables = {
        "NAME": {"required": False, "description": ("Generic product name.")},
        "teams_webhook_url": {
            "required": True,
            "description": ("Teams webhook."),
        },
        "teams_username": {
            "required": False,
            "description": ("Teams MessageCard display name."),
            "default": "AutoPkg",
        },
        "verbosity": {
            "required": False,
            "description": ("Verbosity of messages. 0=brief - 3=all details."),
            "default": 0,
        },
        "teams_icon_url": {
            "required": False,
            "description": ("Teams display icon URL."),
            "default": "https://munkibuilds.org/logo.jpg",
        },
        "ICON_BASE_URL": {
            "required": False,
            "description": (
                "Base url to icons folder, corresponds to Munki's IconURL"
            ),
        },
        "munki_repo_changed": {
            "required": False,
            "description": (
                "Indicates if an item was imported by "
                "MunkiImporter or modified by MunkiAutoStaging."
            ),
            "default": False,
        },
        "munki_importer_summary_result": {
            "required": False,
            "description": (
                "The pkginfo property list. Empty if item was not " "imported."
            ),
        },
        "munki_autostaging_summary_result": {
            "required": False,
            "description": ("Result of the MunkiAutoStaging processor."),
        },
    }
    output_variables = {}

    __doc__ = description

    def _curl_json_poster(self, message_json, teams_webhook_url):
        """
        Sends a JSON formatted message via curl through a teams webhook.
        Essentially:
        curl -H "Content-Type: application/json" -d "${JSON}" "${WEBHOOK_URL}"
        """
        curl_cmd = [
            "/usr/bin/curl",
            "--silent",
            "--show-error",
            "--fail-with-body",
            "-H",
            "Content-Type: application/json",
            "-d",
            message_json,
            teams_webhook_url,
        ]
        try:
            with subprocess.Popen(
                curl_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            ) as proc:
                (out, err) = proc.communicate()
        except OSError as error:
            raise ProcessorError(error) from error
        if proc.returncode != 0 or err:
            self.output(
                "curl returned an error while sending teams message"
                "via webhook."
            )
            self.output(f"returncode: {proc.returncode}")
            self.output(f"stdout: {out}")
            self.output(f"stderr: {err}")
            raise ProcessorError(
                "curl returned an error while sending teams "
                "message via webhook.",
                f"returncode: {proc.returncode}",
                f"stdout: {out}",
                f"stderr: {err}",
            )
            # return False
        return True

    def send_teams_message(self, teams_webhook_url, message):
        """
        Converts a Teams message-dictionary to a JSON formatted string and
        invokes _curl_json_poster to send it to teams.
        """
        message_json = json.dumps(message)
        for count in range(1, 6):
            self.output(f"Teams webhook post attempt {count}", verbose_level=2)
            success = self._curl_json_poster(message_json, teams_webhook_url)
            if success:
                break
            sleep(10)
        else:
            self.output("Giving up posting to Teams:")
            self.output("Teams webhook send did not succeed after 5 attempts")
            raise ProcessorError(
                "ERROR: Teams webhook failed to send 5 times."
            )

    def new_message(
        self,
        title="",
        activity_title="",
        activity_subtitle="",
        activity_image="",
    ):
        """
        Creates an empty Teams activity message dictionary. This empty
        dictionary is accepted when sent to teams.
        Optional parameters like titles can be set / changed through named
        methods of this module.
        """
        message = {
            "@type": "AdaptiveCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "778eb1",
            "summary": title,
            "sections": [
                {
                    "activityTitle": activity_title,
                    "activitySubtitle": activity_subtitle,
                    "facts": [],
                }
            ],
            "potentialAction": [],
        }

        self.set_activity_image(message, activity_image)

        return message

    def set_title(self, message, title):
        """
        Set summary and title in an existing Teams message dictionary.
        """
        message["summary"] = title
        return message

    def set_activity_title(self, message, activity_title):
        """
        Set activityTitle in an existing Teams message dictionary.
        """
        message["sections"][0]["activityTitle"] = activity_title
        return message

    def set_activity_subtitle(self, message, activity_subtitle):
        """
        Set activitySubtitle in an existing Teams message dictionary.
        """
        message["sections"][0]["activitySubtitle"] = activity_subtitle
        return message

    def set_activity_image(self, message, activity_image=""):
        """
        Set activityImage in an existing Teams message dictionary. If no image
        link is given or any other value that is considered False is given, the
        image will be removed.
        """
        if activity_image:
            message["sections"][0]["activityImage"] = activity_image
        else:
            try:
                del message["sections"][0]["activityImage"]
            except KeyError:
                pass
        return message

    def add_fact(self, message, name, value):
        """
        Adds a facts dictionary to a Teams message dictionary.
        """
        message["sections"][0]["facts"] += [{"name": name, "value": value}]
        return message

    def add_link(self, message, name, url):
        """
        Adds a link to a Teams message dictionary.
        """
        message["potentialAction"] += [
            {
                "@type": "OpenUri",
                "name": name,
                "targets": [{"os": "default", "uri": url}],
            }
        ]
        return message

    def gen_icon_url(self, munki_info):
        """
        Derives the icon url from a given pkginfo dictionary
        """

        icon_url = ""

        # Get icon_base_url
        icon_url = self.env.get("ICON_BASE_URL", "")

        if not icon_url or not munki_info:
            return ""

        icon_name = munki_info.get(
            "icon_name", f'{munki_info.get("name")}.png'
        )

        if icon_name:
            icon_url = f"{icon_url}/{icon_name}"

        if self.check_web_url(icon_url):
            return icon_url

        # Try to add .png to the icon_name
        icon_url = f"{icon_url}.png"
        if self.check_web_url(icon_url):
            return icon_url

        return ""

    def check_web_url(self, url):
        """
        Returns true if a given url seems to be valid and reachable
        """

        curl_cmd = self.prepare_curl_cmd()
        curl_cmd.extend(["--head", url])
        raw_headers = self.download_with_curl(curl_cmd)
        header = self.parse_headers(raw_headers)

        self.output(header, 2)

        return header.get("http_result_code") == "200"

    def munki_message(self, message, munki_summary, munki_info, verbosity):
        """
        Compiles the important results of MunkiImporter into a teams message.
        """
        data = munki_summary.get("data")
        name = data.get("name")
        version = data.get("version")
        catalogs = data.get("catalogs")
        pkginfo_path = data.get("pkginfo_path")
        pkg_repo_path = data.get("pkg_repo_path")
        icon_repo_path = data.get("icon_repo_path")

        supported_archs = munki_info.get("supported_architectures", [])
        supported_archs = ", ".join(supported_archs)

        self.output(f"          MunkiImporter name: {name}")
        self.output(f"       MunkiImporter version: {version}")
        self.output(f"      MunkiImporter catalogs: {catalogs}")
        self.output(f"  MunkiImporter pkginfo_path: {pkginfo_path}")
        self.output(f" MunkiImporter pkg_repo_path: {pkg_repo_path}")
        self.output(f"MunkiImporter icon_repo_path: {icon_repo_path}")
        self.output(f"     Supported architectures: {supported_archs}")
        if verbosity >= 3:
            message = self.add_fact(message, "Name", name)
        message = self.add_fact(message, "new Version", version)
        if verbosity >= 1:
            message = self.add_fact(message, "in Catalogs", catalogs)
            if supported_archs:
                message = self.add_fact(
                    message, "supported architectures", supported_archs
                )
        if verbosity >= 2:
            message = self.add_fact(message, "PkgInfo Path", pkginfo_path)
            message = self.add_fact(message, "Package Path", pkg_repo_path)
        if verbosity >= 3:
            if icon_repo_path:
                message = self.add_fact(message, "Icon Path", icon_repo_path)
            else:
                message = self.add_fact(
                    message, "Icon Path", "no icon path given"
                )

        icon_url = self.gen_icon_url(munki_info)

        if icon_url:
            self.set_activity_image(message, icon_url)

        # self.add_link(message, "Show in Munki", "munki://detail-" + name)

        return (message, name)

    def staging_message(
        self, message, autostaging_summary, munki_info, verbosity
    ):
        """
        Compiles the important results of MunkiAutoStaging into a teams
        message.
        """
        data = autostaging_summary.get("data")
        name = data.get("name")
        versions = data.get("versions")
        munki_staging_catalog = data.get("munki_staging_catalog")
        munki_production_catalog = data.get("munki_production_catalog")

        supported_archs = munki_info.get("supported_architectures", [])
        supported_archs = ", ".join(supported_archs)

        self.output(f"                    AutoStaging name: {name}")
        self.output(f"                AutoStaging versions: {versions}")
        self.output(
            f"   AutoStaging munki_staging_catalog: {munki_staging_catalog}"
        )
        self.output(
            f"AutoStaging munki_production_catalog: {munki_production_catalog}"
        )
        self.output(f"     Supported architectures: {supported_archs}")
        if verbosity >= 3:
            message = self.add_fact(message, "Name", name)
        message = self.add_fact(message, "autostaged Versions", versions)
        if verbosity >= 1:
            message = self.add_fact(
                message, "from Staging Catalog", munki_staging_catalog
            )
            message = self.add_fact(
                message, "to Production Catalogs", munki_production_catalog
            )
            if supported_archs:
                message = self.add_fact(
                    message, "supported architectures", supported_archs
                )

        icon_url = self.gen_icon_url(munki_info)

        if icon_url:
            self.set_activity_image(message, icon_url)

        return (message, name)

    def main(self):
        """
        Gets environment variables of MunkiImporter and MunkiAutoStaging and
        hands them to specialised methods for message creation.
        The message will be sent through a webhook to Teams if any relevant
        changes occured in the munki repository.
        """
        munki_info = self.env.get("munki_info", {})
        nice_name = munki_info.get("display_name", self.env.get("NAME", ""))
        teams_webhook_url = self.env.get("teams_webhook_url")
        teams_username = self.env.get("teams_username") or "AutoPkg"
        verbosity = int(self.env.get("verbosity")) or 0
        teams_icon_url = (
            self.env.get("teams_icon_url")
            or "https://munkibuilds.org/logo.jpg"
        )
        munki_repo_changed = self.env.get("munki_repo_changed") or False
        munki_summary = self.env.get("munki_importer_summary_result")
        autostaging_summary = self.env.get("munki_autostaging_summary_result")

        message = self.new_message(
            title=teams_username, activity_image=teams_icon_url
        )

        if munki_repo_changed and munki_summary and autostaging_summary:
            self.set_activity_subtitle(
                message, "MunkiImporter and AutoStaging"
            )
            (message, munki_name) = self.munki_message(
                message, munki_summary, munki_info, verbosity
            )
            (message, staging_name) = self.staging_message(
                message, autostaging_summary, munki_info, verbosity
            )
            if nice_name != munki_name:
                name = f"{nice_name} ({munki_name})"
            else:
                name = f"{munki_name}"
        elif munki_repo_changed and munki_summary:
            self.set_activity_subtitle(message, "MunkiImporter")
            (message, munki_name) = self.munki_message(
                message, munki_summary, munki_info, verbosity
            )
            if nice_name != munki_name:
                name = f"{nice_name} ({munki_name})"
            else:
                name = f"{munki_name}"
        elif munki_repo_changed and autostaging_summary:
            self.set_activity_subtitle(message, "MunkiAutoStaging")
            (message, staging_name) = self.staging_message(
                message, autostaging_summary, munki_info, verbosity
            )
            if nice_name != staging_name:
                name = f"{nice_name} ({staging_name})"
            else:
                name = f"{staging_name}"
        else:
            self.output("Nothing to report to Teams")
            return
        self.set_activity_title(message, name)

        self.send_teams_message(teams_webhook_url, message)


if __name__ == "__main__":
    PROCESSOR = MunkiRepoTeamsNotifier()
    PROCESSOR.execute_shell()
