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


class TeamsMessage:
    """
    Class to create and send messages to Microsoft Teams through a webhook.
    """

    title = ""
    subtitle = ""
    facts = []
    links = []
    image_url = ""
    set_webhook_url = ""
    verbose_level = 1

    def __init__(
        self,
        title="",
        image_url="",
        webhook_url="",
        verbose_level=1,
    ):
        self.title = title
        self.image_url = image_url
        self.facts = []
        self.links = []
        self.verbose_level = verbose_level
        self.set_webhook_url = webhook_url

    def output(self, msg, verbose_level=1) -> None:
        """Print a message if verbosity is >= verbose_level"""
        if self.verbose_level >= verbose_level:
            print(f"{self.__class__.__name__}: {msg}")

    def set_title(self, title):
        self.title = title

    def set_subtitle(self, subtitle):
        self.subtitle = subtitle

    def add_fact(self, name, value):
        self.facts += [{"name": name, "value": value}]

    def add_link(self, link_options):
        self.links += [
            {
                "url": link_options.get("url", ""),
                "name": link_options.get("name", ""),
                "tooltip": link_options.get("tooltip", ""),
                "icon": link_options.get("icon", ""),
                "mode": link_options.get("mode", ""),
                "style": link_options.get("style", ""),
            }
        ]

    def set_image(self, image_url):
        self.image_url = image_url

    def set_webhook(self, webhook_url):
        self.set_webhook_url = webhook_url

    def _curl_json_poster(self, message_json, teams_webhook_url):
        """
        Sends a JSON formatted Adaptive Card via curl through a teams webhook.
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
                out, err = proc.communicate()
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

    def create_content_items(self):
        content_items = []
        if self.title:
            content_items += [
                {
                    "type": "TextBlock",
                    "text": self.title,
                    "wrap": True,
                    "style": "heading",
                }
            ]

        if self.subtitle:
            content_items += [
                {
                    "type": "TextBlock",
                    "text": self.subtitle,
                    "wrap": True,
                    "style": "columnHeader",
                }
            ]

        if self.facts:
            fact_items = []
            for fact in self.facts:
                fact_items += [{"title": fact["name"], "value": fact["value"]}]
            content_items += [{"type": "FactSet", "facts": fact_items}]

        if self.links:
            action_items = []
            for link in self.links:
                action_items += [
                    {
                        "type": "Action.OpenUrl",
                        "title": link["name"],
                        "url": link["url"],
                        "iconUrl": (
                            (f"icon:{link.get('icon')}")
                            if link.get("icon")
                            else None
                        ),
                        "tooltip": link.get("tooltip"),
                        "mode": link.get("mode", "primary"),
                        "style": link.get("style", "default"),
                    }
                ]
            content_items += [{"type": "ActionSet", "actions": action_items}]

        return content_items

    def send(self, webhook_url=None):
        """
        Converts the TeamsMessage to a JSON formatted string and
        invokes _curl_json_poster to send it to teams.
        """

        if not webhook_url and not self.set_webhook_url:
            raise ProcessorError("No webhook url set for Teams Message.")

        if webhook_url:
            self.set_webhook(webhook_url)

        message = {
            "type": "AdaptiveCard",
            "$schema": "https://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.5",
            "body": [],
        }

        content_items = self.create_content_items()

        if self.image_url:
            body = [
                {
                    "type": "ColumnSet",
                    "columns": [
                        {
                            "type": "Column",
                            "width": "auto",
                            "items": [
                                {
                                    "type": "Image",
                                    "url": self.image_url,
                                    "size": "Medium",
                                }
                            ],
                        },
                        {
                            "type": "Column",
                            "width": "stretch",
                            "items": content_items,
                        },
                    ],
                }
            ]
        else:
            body = [{"type": "Container", "items": content_items}]

        message["body"] = body

        message_json = json.dumps(message)

        self.output(
            f"Prepared Teams message JSON: {message_json}", verbose_level=3
        )

        for count in range(1, 6):
            self.output(f"Teams webhook post attempt {count}", verbose_level=2)
            success = self._curl_json_poster(
                message_json, self.set_webhook_url
            )
            if success:
                break
            sleep(10)
        else:
            self.output("Giving up posting to Teams:")
            self.output("Teams webhook send did not succeed after 5 attempts")
            raise ProcessorError(
                "ERROR: Teams webhook failed to send 5 times."
            )


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
            "default": (
                "https://github.com/munki/munki/blob/"
                "c3ea21c9c754611c5d78364f05a94abc0a45adf7/code/apps/"
                "Managed%20Software%20Center/Managed%20Software%20Center/"
                "Assets.xcassets/AppIcon.appiconset/"
                "MunkiStatus_128_1x.png?raw=true"
            ),
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

    message = None

    __doc__ = description

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

    def munki_message(self, munki_summary, munki_info, verbosity):
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
            self.message.add_fact("Name", name)

        self.message.add_fact("new Version", version)

        if verbosity >= 1:
            self.message.add_fact("in Catalogs", catalogs)
            if supported_archs:
                self.message.add_fact(
                    "supported architectures", supported_archs
                )
        if verbosity >= 2:
            self.message.add_fact("PkgInfo Path", pkginfo_path)
            self.message.add_fact("Package Path", pkg_repo_path)
        if verbosity >= 3:
            if icon_repo_path:
                self.message.add_fact("Icon Path", icon_repo_path)
            else:
                self.message.add_fact("Icon Path", "no icon path given")

        icon_url = self.gen_icon_url(munki_info)

        if icon_url:
            self.message.set_image(icon_url)

        # Teams does not support Munki links
        # self.message.add_link(
        #     {
        #         "url": "munki://detail-" + name,
        #         "name": "Show in Munki",
        #         "icon": "Open",
        #         "style": "positive",
        #     }
        # )

        return name

    def staging_message(self, autostaging_summary, munki_info, verbosity):
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
            self.message.add_fact("Name", name)

        self.message.add_fact("autostaged Versions", versions)

        if verbosity >= 1:
            self.message.add_fact(
                "from Staging Catalog", munki_staging_catalog
            )
            self.message.add_fact(
                "to Production Catalogs", munki_production_catalog
            )
            if supported_archs:
                self.message.add_fact(
                    "supported architectures", supported_archs
                )

        icon_url = self.gen_icon_url(munki_info)

        if icon_url:
            self.message.set_image(icon_url)

        # Teams does not support Munki links
        # self.message.add_link(
        #     {
        #         "url": "munki://detail-" + name,
        #         "name": "Show in Munki",
        #         "icon": "Open",
        #         "style": "positive",
        #     }
        # )

        return name

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
        teams_icon_url = self.env.get("teams_icon_url", None) or (
            "https://github.com/munki/munki/blob/"
            "c3ea21c9c754611c5d78364f05a94abc0a45adf7/code/apps/"
            "Managed%20Software%20Center/Managed%20Software%20Center/"
            "Assets.xcassets/AppIcon.appiconset/"
            "MunkiStatus_128_1x.png?raw=true"
        )
        munki_repo_changed = self.env.get("munki_repo_changed") or False
        munki_summary = self.env.get("munki_importer_summary_result")
        autostaging_summary = self.env.get("munki_autostaging_summary_result")

        self.message = TeamsMessage(
            title=teams_username,
            image_url=teams_icon_url,
            webhook_url=teams_webhook_url,
            verbose_level=self.env.get("verbose", 0),
        )

        if munki_repo_changed and munki_summary and autostaging_summary:

            self.message.set_subtitle("MunkiImporter and AutoStaging")

            munki_name = self.munki_message(
                munki_summary, munki_info, verbosity
            )

            staging_name = self.staging_message(
                autostaging_summary, munki_info, verbosity
            )

            if nice_name != munki_name:
                name = f"{nice_name} ({munki_name})"
            else:
                name = f"{munki_name}"

        elif munki_repo_changed and munki_summary:

            self.message.set_subtitle("MunkiImporter")

            munki_name = self.munki_message(
                munki_summary, munki_info, verbosity
            )

            if nice_name != munki_name:
                name = f"{nice_name} ({munki_name})"
            else:
                name = f"{munki_name}"

        elif munki_repo_changed and autostaging_summary:

            self.message.set_subtitle("MunkiAutoStaging")

            staging_name = self.staging_message(
                autostaging_summary, munki_info, verbosity
            )

            if nice_name != staging_name:
                name = f"{nice_name} ({staging_name})"
            else:
                name = f"{staging_name}"
        else:
            self.output("Nothing to report to Teams")
            return

        if name:
            self.message.set_title(name)

        self.message.send()


if __name__ == "__main__":
    PROCESSOR = MunkiRepoTeamsNotifier()
    PROCESSOR.execute_shell()
