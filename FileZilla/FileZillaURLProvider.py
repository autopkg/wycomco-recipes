#!/usr/local/autopkg/python
#
# Copyright 2025 wycomco GmbH
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
"""See docstring for FileZillaURLProvider class"""


import base64
import re
from typing import List

from autopkglib import URLGetter
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

__all__: List[str] = ["FileZillaURLProvider"]


FILEZILLA_BASE_URL: str = (
    "https://filezilla-project.org/download.php?show_all=1"
)


class FileZillaURLProvider(URLGetter):
    """
    Provides URL to the latest FileZilla release.

    Requires import of cryptography package:
        sudo /Library/AutoPkg/Python3/Python.framework/Versions/Current/bin/pip3 install cryptography
    """

    description = __doc__
    input_variables = {
        "ARCH": {
            "required": False,
            "default": "arm64",
            "description": "Which architecture to download: 'arm64' (default), 'x86'.",
        },
        "base_url": {
            "required": False,
            "description": (
                f"(Advanced) URL for downloads.  Default is '{FILEZILLA_BASE_URL}'."
            ),
            "default": FILEZILLA_BASE_URL,
        },
    }
    output_variables = {
        "url": {"description": "URL to the latest FileZilla product release."},
        "version": {
            "description": ("Resolved version number for the release")
        },
    }

    def parse_version_from_url(self, url: str) -> str:
        """
        Parse version number from the given URL.

        Example URL:
        https://download.filezilla-project.org/client/FileZilla_3.66.1_macos-x86.app.tar.bz2

        Returns:
            str: Extracted version number (e.g., "3.66.1")
        """
        version_pattern = r"FileZilla_(\d+\.\d+\.\d+)_macos"
        match = re.search(version_pattern, url)
        if match:
            return match.group(1)
        else:
            raise ValueError("Could not parse version from URL")

    def parse_download_url(self, html_string: str, arch: str):
        """
        Parse the download URL from the HTML string based on architecture.

        The HTML contains download links for multiple architectures and platforms

        """

        needle = f"macos-{arch}.app.tar.bz2"

        # Find all href links in the HTML
        href_pattern = r'href=["\'](.*?)["\']'
        hrefs = re.findall(href_pattern, html_string, re.IGNORECASE)
        for href in hrefs:
            if needle in href:
                return href
        raise ValueError(
            f"Could not find download URL for architecture: {arch}"
        )

    def decrypt_string(self, content: str, attributes: dict) -> str:
        """
        Decrypt the content of a div element that contains encrypted data.

        This function replicates the JavaScript decryption logic:
        1. Extracts base64-encoded cipher, IV, key, and algorithm from div attributes
        2. Performs AES-CBC decryption using the extracted parameters
        3. Returns the decrypted content as UTF-8 text

        Args:
            content (str): String containing the encrypted content (base64-encoded)
            attributes (dict): Dictionary containing the div attributes.
                                - v1 attribute: base64-encoded IV
                                - v2 attribute: base64-encoded encryption key
                                - v3 attribute: base64-encoded algorithm name

        Returns:
            str: Decrypted content as UTF-8 string

        """
        # Parse HTML to find the contentwrapper div
        # Extract encrypted data and parameters from div attributes
        cipher_b64 = content  # Base64 encrypted content
        iv_b64 = attributes.get("v1")  # Base64 IV (initialization vector)
        rawkey_b64 = attributes.get("v2")  # Base64 encryption key
        algorithm_b64 = attributes.get("v3")  # Base64 algorithm name

        # Validate all required components are present
        if not all([cipher_b64, iv_b64, rawkey_b64, algorithm_b64]):
            raise ValueError(
                "Missing required attributes (v1, v2, v3) or content"
            )

        # Base64 decode all components
        cipher = base64.b64decode(cipher_b64)
        iv = base64.b64decode(iv_b64)
        rawkey = base64.b64decode(rawkey_b64)
        algorithm = base64.b64decode(algorithm_b64).decode("utf-8")

        # Verify algorithm is AES-CBC (as expected by the JavaScript)
        if algorithm != "AES-CBC":
            raise ValueError(
                f"Unsupported algorithm: {algorithm}. Expected AES-CBC"
            )

        # Create AES-CBC cipher with the extracted key and IV
        cipher_obj = Cipher(
            algorithms.AES(rawkey), modes.CBC(iv), backend=default_backend()
        )
        decryptor = cipher_obj.decryptor()

        # Decrypt the data
        padded_plaintext = decryptor.update(cipher) + decryptor.finalize()

        # Remove PKCS7 padding (standard padding for AES-CBC)
        padding_length = padded_plaintext[-1]
        plaintext = padded_plaintext[:-padding_length]

        # Decode the decrypted bytes as UTF-8 text
        decrypted_content = plaintext.decode("utf-8")

        return decrypted_content

    def parse_html_div(self, html_string):
        """
        Parse HTML string to extract div attributes using regex.

        Args:
            html_string (str): HTML string containing the div

        Returns:
            dict: Dictionary with div content and attributes
        """

        # Find div with id="contentwrapper"
        div_pattern = r'<div[^>]*id=["\']contentwrapper["\'][^>]*>(.*?)</div>'
        div_match = re.search(
            div_pattern, html_string, re.DOTALL | re.IGNORECASE
        )

        if not div_match:
            raise ValueError("Could not find div with id 'contentwrapper'")

        full_div = div_match.group(0)
        content = div_match.group(1).strip()

        # Extract attributes
        attributes = {}

        # Extract v1, v2, v3 attributes
        for attr in ["v1", "v2", "v3"]:
            attr_pattern = rf'{attr}=["\']([^"\']*)["\']'
            attr_match = re.search(attr_pattern, full_div, re.IGNORECASE)
            if attr_match:
                attributes[attr] = attr_match.group(1)

        return {"content": content, "attributes": attributes}

    def get_filezilla_download_page(self, url: str) -> str:
        """Retrieve the FileZilla download page HTML content."""
        header = {
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1 Safari/605.1.15"
        }
        response = self.download(url, text=True, headers=header)
        return response

    def main(self):
        """Provide a FileZilla download URL"""
        # Determine product_name, release, locale, and base_url.
        arch = self.env.get("ARCH", "arm64")
        base_url = self.env.get("base_url", FILEZILLA_BASE_URL)

        # Download the FileZilla download page
        download_page_html = self.get_filezilla_download_page(base_url)

        # Parse the HTML to extract the encrypted div content and attributes
        div_data = self.parse_html_div(download_page_html)

        # Decrypt the content to get the actual download URLs as HTML
        div_data["content"] = self.decrypt_string(
            div_data["content"], div_data["attributes"]
        )

        self.env["url"] = self.parse_download_url(div_data["content"], arch)

        self.env["version"] = self.parse_version_from_url(self.env["url"])
        self.output(f"Found URL {self.env['url']}")


if __name__ == "__main__":
    PROCESSOR = FileZillaURLProvider()
    PROCESSOR.execute_shell()
