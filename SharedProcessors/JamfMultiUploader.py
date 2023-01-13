#!/usr/local/autopkg/python
# -*- coding: utf-8 -*-
#
# Copyright 2023 wycomco GmbH
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
    """This processor invokes the given JamfUploader processor multiple times
    to support multiple Jamf environments at once."""

    def __init__(self, env=None, infile=None, outfile=None):
        super().__init__(env, infile, outfile)
        self.verbose = 0
        self.options = {}
        self.processor_results = []

    description = __doc__
    input_variables = {
        "jamf_uploader_name": {
            "required": True,
            "description": "Name of the JamfUploader processor to be used, "
            "for example: com.github.grahampugh.jamf-upload.processors"
            "/JamfPackageUploader",
        },
        "jamf_server_configs": {
            "required": False,
            "description": "List of dictionaries containing individual config"
            "parameters for specific Jamf Pro servers.",
        },
        "jamf_uploader_processor_parameters": {
            "required": False,
            "description": "Dictionary with parameters for the used processor."
            " If specific JSS need different parameters, these should be "
            "grouped in a separate dictionary item, identified by the "
            "JSS_URL from jamf_server_configs, default parameters should "
            "then be made available with a 'default' key."
            "jamf_server_configs as key, or 'default'.",
        },
    }
    output_variables = {
        "jamf_multi_uploader_summary_result": {
            "description": "Description of interesting results."
        },
    }

    def check_dependencies(
        self,
        processor_name,
        jamf_server_configs,
        default_params,
        custom_params,
    ):
        """Make sure that we have access to all needed resources."""
        processor_class = self.get_processor_class(processor_name)

        # Add this processors input and output vars to our internal vars
        self.input_variables.update(processor_class.input_variables)
        self.output_variables.update(processor_class.output_variables)

        for jamf_server_config in jamf_server_configs:
            # Initialize variable set with input variables.
            variables = set(self.env.keys())

            # Get the JSS URL for this run, to identify special params
            jss_url = jamf_server_config.get("JSS_URL", "")

            # Get special params for this JSS
            jss_params = custom_params.get(jss_url, {})

            # Join the different configs...
            jamf_server_config.update(default_params)
            jamf_server_config.update(jss_params)

            variables.update(jamf_server_config.keys())

            # Make sure all required input variables exist.
            for key, flags in list(self.input_variables.items()):
                if flags["required"] and (key not in variables):
                    raise AutoPackagerError(
                        f"{processor_name} requires missing argument {key}"
                        " for JSS URL {jss_url}"
                    )

    def update_env(self, custom_config, substituted_vars):
        """Update env with config, preserving original values in variable"""

        if self.verbose:
            print("Update env with custom config, preserving original values")

        if self.verbose > 2:
            pprint.pprint({"env before temporary override": self.env})

        if custom_config:
            for key, value in custom_config.items():
                if key in self.env:
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
                if key in substituted_vars:
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

        custom_params = self.env.get("jamf_uploader_processor_parameters", {})

        # Get any default params, if any.
        default_params = custom_params.get("default", {})

        if "jamf_server_configs" in self.env:
            jamf_server_configs = self.env["jamf_server_configs"]
        else:
            # If there is no list of configs, look for the default parameters
            config = {}
            if "JSS_URL" in self.env:
                config["JSS_URL"] = self.env["JSS_URL"]

            if "API_USERNAME" in self.env:
                config["API_USERNAME"] = self.env["API_USERNAME"]

            if "API_PASSWORD" in self.env:
                config["API_PASSWORD"] = self.env["API_PASSWORD"]

            jamf_server_configs = []
            jamf_server_configs.append(config)

        self.check_dependencies(
            processor_name=processor_name,
            jamf_server_configs=jamf_server_configs,
            default_params=default_params,
            custom_params=custom_params,
        )

        for jamf_server_config in jamf_server_configs:

            # Get the JSS URL for this run, to identify special params
            jss_url = jamf_server_config.get("JSS_URL", "")

            # Get special params for this JSS
            jss_params = custom_params.get(jss_url, {})

            # Join the different configs...
            jamf_server_config.update(default_params)
            jamf_server_config.update(jss_params)

            self.prepare_and_run(
                processor_name=processor_name,
                custom_config=jamf_server_config,
            )

    def generate_summary_result(self):
        """Generate an autopkg summary result"""
        # clear any pre-existing summary result
        if "jamf_multi_uploader_summary_result" in self.env:
            del self.env["jamf_multi_uploader_summary_result"]

        processor_name = self.env["jamf_uploader_name"].split("/")[1]

        server_status = []

        for single_result in self.processor_results:
            server_status.append(
                f'{single_result["JSS_URL"]} ({single_result["Status"]})'
            )

        if "pkg_path" in self.env:
            pkg_name = os.path.basename(self.env["pkg_path"])
        else:
            pkg_name = "n/a"

        if "version" in self.env:
            version = self.env["version"]
        else:
            version = "n/a"

        self.env["jamf_multi_uploader_summary_result"] = {
            "summary_text": ("Running JamfUploader processor multiple times:"),
            "report_fields": [
                "Processor",
                "PKG",
                "Version",
                "Jamf Servers (Status)",
            ],
            "data": {
                "Processor": processor_name,
                "PKG": pkg_name,
                "Version": version,
                "Jamf Servers (Status)": ", ".join(server_status),
            },
        }

    def main(self, options=None):

        if options:
            self.options = options
            if self.options.verbose:
                self.verbose = self.options.verbose

        self.run_processor(processor_name=self.env["jamf_uploader_name"])

        self.generate_summary_result()


if __name__ == "__main__":
    PROCESSOR = JamfMultiUploader()
    PROCESSOR.execute_shell()
