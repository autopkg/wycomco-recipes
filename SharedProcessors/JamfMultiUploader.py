#!/usr/local/autopkg/python
# -*- coding: utf-8 -*-
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
"""See docstring for JamfMultiUploader class"""

from __future__ import absolute_import

import os
import pathlib
import pprint
import sys
import traceback

from autopkglib import (
    AutoPackagerError,
    AutoPackagerLoadError,
    Processor,
    get_processor,
)

__all__ = ["JamfMultiUploader"]


def get_fake_recipe():
    """Since get_processor requires a recipe to find any non-standard
    processors we make a simple fake_recipe to provide a base search path"""

    fake_recipe = {
        "RECIPE_PATH": pathlib.Path(__file__).parent.resolve(),
        "PARENT_RECIPES": None,
    }

    return fake_recipe


class JamfMultiUploader(Processor):
    """This processor invokes the JamfUploader processor multiple times
    to support multiple Jamf environments at once."""

    def __init__(self, env=None, infile=None, outfile=None):
        super().__init__(env, infile, outfile)
        self.verbose = 0
        self.options = {}
        self.processor_results = []

    description = __doc__
    input_variables = {
        "pkg_path": {
            "required": True,
            "description": "Path to a pkg or dmg to import - provided by "
            "previous pkg recipe/processor.",
            "default": "",
        },
        "jamf_server_configs": {
            "required": False,
            "description": "List of dictionaries containing individual configs"
            "parameters for specific Jamf Pro servers.",
        },
    }
    output_variables = {
        "jamf_multi_uploader_summary_result": {
            "description": "Description of interesting results."
        },
    }

    def check_dependencies(self, processor_name):
        """Make sure that we have access to all needed resources."""
        # Initialize variable set with input variables.
        variables = set(self.env.keys())

        processor_class = self.get_processor_class(processor_name)

        # Add this processors input and output vars to our internal vars
        self.input_variables.update(processor_class.input_variables)
        self.output_variables.update(processor_class.output_variables)

        # Make sure all required input variables exist.
        for key, flags in list(self.input_variables.items()):
            if flags["required"] and (key not in variables):
                raise AutoPackagerError(
                    f"{processor_name} requires missing argument {key}"
                )

        # Add output variables to set.
        variables.update(set(processor_class.output_variables.keys()))

    def update_env(self, custom_config, substituted_vars):
        """Update env with config, preserving original values in variable"""

        if self.verbose:
            print("Update env with custom config, preserving original values")

        if self.verbose > 2:
            pprint.pprint({"env before temporary override": self.env})

        if custom_config:
            for key, value in custom_config.items():
                if self.env[key]:
                    substituted_vars.update({key: self.env[key]})
                self.env[key] = value

        if self.verbose > 2:
            pprint.pprint({"env after temporary override": self.env})

    def restore_env(self, custom_config, substituted_vars):
        """Restore env with original values"""

        if self.verbose > 2:
            pprint.pprint({"env before reset": self.env})

        if self.verbose:
            print("Resetting original values")
        if custom_config:
            for key in custom_config.keys():
                if substituted_vars[key]:
                    self.env[key] = substituted_vars[key]
                else:
                    del self.env[key]

        if self.verbose > 2:
            pprint.pprint({"env after reset": self.env})

    def get_processor_class(self, processor_name):
        """Get the processor class"""

        fake_recipe = get_fake_recipe()

        try:
            processor_class = get_processor(
                processor_name=processor_name,
                recipe=fake_recipe,
                verbose=self.verbose,
                env=self.env,
            )
        except (KeyError, AttributeError) as err:
            msg = f"Unknown processor '{processor_name}'."
            raise AutoPackagerError(msg) from err
        except AutoPackagerLoadError as err:
            msg = (
                f"Unable to import '{processor_name}', likely due "
                "to syntax or Python error."
            )
            raise AutoPackagerError(msg) from err

        return processor_class

    def execute_processor(self, processor, run_results):
        """Executes a processor and stores results in var"""

        input_dict = {}
        for key in list(processor.input_variables.keys()):
            if key in processor.env:
                input_dict[key] = processor.env[key]

        if self.verbose > 1:
            # pretty print any defined input variables
            pprint.pprint({"Input": input_dict})

        try:
            self.env = processor.process()
        # Disable broad-except error since we do not know what
        # exception may occur
        except Exception as err:  # pylint: disable=broad-except
            if self.verbose > 2:
                exc_traceback = sys.exc_info()[2]
                traceback.print_exc(file=sys.stdout)
                traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)

            print(err, file=sys.stderr)
            run_results["Status"] = "ERROR"
            run_results["Message"] += str(err)

        output_dict = {}

        for key in list(processor.output_variables.keys()):
            # Safety workaround for Processors that may output
            # differently-named output variables than are given in
            # their output_variables
            if processor.env.get(key):
                output_dict[key] = self.env[key]

        if self.verbose > 1:
            # pretty print output variables
            pprint.pprint({"Output": output_dict})

        if not run_results["Status"]:
            if "pkg_uploaded" in output_dict and output_dict["pkg_uploaded"]:
                run_results["Status"] = "Uploaded"
            else:
                run_results["Status"] = "Not uploaded"

    def prepare_and_run(self, processor_name, custom_config):
        """Temporarly override env and run processor"""
        substituted_vars = {}
        run_results = {
            "JSS_URL": "",
            "Status": "",
            "Message": "",
        }

        self.update_env(
            custom_config=custom_config, substituted_vars=substituted_vars
        )

        # Actually running the given processor, using the code from autopkglib
        processor_class = self.get_processor_class(processor_name)
        processor = processor_class(self.env)

        self.execute_processor(processor=processor, run_results=run_results)

        self.restore_env(
            custom_config=custom_config, substituted_vars=substituted_vars
        )

        if custom_config["JSS_URL"]:
            run_results["JSS_URL"] = custom_config["JSS_URL"]
        else:
            run_results["JSS_URL"] = "n/a"

        self.processor_results.append(run_results)

        del processor
        del processor_class
        del substituted_vars

    def run_processor(self, processor_name):
        """Run the needed processor"""
        self.check_dependencies(processor_name=processor_name)

        for jamf_server_config in self.env["jamf_server_configs"]:
            self.prepare_and_run(
                processor_name=processor_name, custom_config=jamf_server_config
            )

    def main(self, options=None):

        if options:
            self.options = options
            if self.options.verbose:
                self.verbose = self.options.verbose

        self.run_processor(
            processor_name="com.github.grahampugh.jamf-upload.processors"
            "/JamfPackageUploader"
        )

        # clear any pre-existing summary result
        if "jamf_multi_uploader_summary_result" in self.env:
            del self.env["jamf_multi_uploader_summary_result"]

        server_status = []

        for single_result in self.processor_results:
            server_status.append(
                f'{single_result["JSS_URL"]} ({single_result["Status"]})'
            )

        if "pkg_path" in self.env:
            pkg_name = os.path.basename(self.env["pkg_path"])
        else:
            pkg_name = "n/a"

        self.env["jamf_multi_uploader_summary_result"] = {
            "summary_text": (
                "Package upload to one or more Jamf instances was processed:"
            ),
            "report_fields": [
                "PKG Name",
                "Version",
                "Jamf Servers (Status)",
            ],
            "data": {
                "PKG Name": pkg_name,
                "Version": self.env["version"],
                "Jamf Servers (Status)": ", ".join(server_status),
            },
        }


if __name__ == "__main__":
    PROCESSOR = JamfMultiUploader()
    PROCESSOR.execute_shell()
