# DataGerry - OpenSource Enterprise CMDB
# Copyright (C) 2025 becon GmbH
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""
Implementation of BaseCmdbApp
"""
import logging

from flask import Flask
from Crypto import Random
from Crypto.PublicKey import RSA

from cmdb import __CLOUD_MODE__, __LOCAL_MODE__
from cmdb.database import MongoDatabaseManager
# -------------------------------------------------------------------------------------------------------------------- #

LOGGER = logging.getLogger(__name__)

# -------------------------------------------------------------------------------------------------------------------- #
#                                                  BaseCmdbApp - CLASS                                                 #
# -------------------------------------------------------------------------------------------------------------------- #
class BaseCmdbApp(Flask):
    """
    A base class for the CMDB application, extending Flask
    """
    def __init__(self, import_name: str, database_manager: MongoDatabaseManager | None = None) -> None:
        """
        Initializes the BaseCmdbApp instance

        Args:
            import_name (str): The name of the application module
            database_manager (MongoDatabaseManager | None, optional): Database interaction manager. Defaults to None
        """
        self.database_manager: MongoDatabaseManager | None = database_manager
        self.temp_folder = '/tmp/'
        self.cloud_mode: bool = __CLOUD_MODE__
        self.local_mode: bool = __LOCAL_MODE__

        # Used for local development.
        # Generate ephemeral keys at startup to avoid shipping static secrets.
        self.asymmetric_key: dict[str, bytes] = self._generate_development_asymmetric_key()
        self.symmetric_key: bytes = Random.get_random_bytes(32)

        super().__init__(import_name)

    @staticmethod
    def _generate_development_asymmetric_key() -> dict[str, bytes]:
        """
        Generates a temporary asymmetric keypair for local development mode.
        """
        keypair = RSA.generate(2048)
        return {
            'private': keypair.export_key(),
            'public': keypair.publickey().export_key(),
        }
