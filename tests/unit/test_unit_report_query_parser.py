# DATAGERRY - OpenSource Enterprise CMDB
# Copyright (C) 2026 becon GmbH
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
Tests for secure report query parsing.
"""
from datetime import datetime
import pytest
from bson import json_util

from cmdb.interface.rest_api.routes.report_routes.report_routes import parse_report_query


def test_parse_report_query_supports_extended_json() -> None:
    """
    JSON/BSON serialized report queries should deserialize to a dict with datetime values.
    """
    serialized = json_util.dumps({'created': {'$gte': datetime(2025, 1, 1, 0, 0)}})
    parsed = parse_report_query(serialized)

    assert isinstance(parsed, dict)
    assert isinstance(parsed['created']['$gte'], datetime)
    assert parsed['created']['$gte'].year == 2025


def test_parse_report_query_supports_legacy_datetime_repr() -> None:
    """
    Legacy Python-string report queries should still parse without using eval.
    """
    legacy_query = (
        "{'$and': [{'fields': {'$elemMatch': {'name': 'created', "
        "'value': {'$gte': datetime.datetime(2025, 1, 1, 0, 0)}}}}]}"
    )
    parsed = parse_report_query(legacy_query)

    assert parsed['$and'][0]['fields']['$elemMatch']['value']['$gte'] == datetime(2025, 1, 1, 0, 0)


def test_parse_report_query_rejects_code_execution_payload() -> None:
    """
    Arbitrary code execution payloads must be rejected.
    """
    with pytest.raises(ValueError):
        parse_report_query("__import__('os').system('whoami')")


def test_parse_report_query_rejects_too_large_payload() -> None:
    """
    Query payload size must be bounded.
    """
    with pytest.raises(ValueError):
        parse_report_query('{' + ('a' * 100_001) + '}')
