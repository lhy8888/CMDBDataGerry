# DataGerry - OpenSource Enterprise CMDB
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
Implementation of all CmdbReport API routes
"""
import ast
from logging import Logger, getLogger
import json
from typing import Any
from datetime import datetime
from ast import literal_eval
from flask import abort, request
from werkzeug import Response
from werkzeug.exceptions import HTTPException
from bson import json_util

from cmdb.database import MongoDBQueryBuilder
from cmdb.manager.query_builder import BuilderParameters
from cmdb.manager.manager_provider_model import ManagerProvider, ManagerType
from cmdb.manager import (
    ReportsManager,
    ObjectsManager,
)

from cmdb.models.type_model import CmdbType
from cmdb.models.user_model import CmdbUser
from cmdb.models.reports_model.cmdb_report import CmdbReport
from cmdb.models.reports_model.mds_mode_enum import MdsMode
from cmdb.interface.blueprints import APIBlueprint
from cmdb.interface.route_utils import insert_request_user, verify_api_access
from cmdb.interface.rest_api.api_level_enum import ApiLevel
from cmdb.interface.rest_api.responses.response_parameters import CollectionParameters
from cmdb.interface.rest_api.responses import DefaultResponse, GetMultiResponse, UpdateSingleResponse
from cmdb.framework.results import IterationResult

from cmdb.errors.manager.reports_manager import (
    ReportsManagerInsertError,
    ReportsManagerGetError,
    ReportsManagerIterationError,
    ReportsManagerUpdateError,
    ReportsManagerDeleteError,
)
# -------------------------------------------------------------------------------------------------------------------- #

LOGGER: Logger = getLogger(__name__)

reports_blueprint = APIBlueprint('reports', __name__)

MAX_REPORT_QUERY_LENGTH = 100_000

# --------------------------------------------------- CRUD - CREATE -------------------------------------------------- #

@reports_blueprint.route('/', methods=['POST'])
@reports_blueprint.parse_request_parameters()
@insert_request_user
@verify_api_access(required_api_level=ApiLevel.ADMIN)
def create_cmdb_report(params: dict[str, Any], request_user: CmdbUser) -> Response:
    """
    Creates a CmdbReport in the database

    Args:
        params (dict): CmdbReport parameters

    Returns:
        DefaultResponse: public_id of the created CmdbReport
    """
    try:
        reports_manager: ReportsManager = ManagerProvider.get_manager(ManagerType.REPORTS, request_user)

        params['report_category_id'] = int(params['report_category_id'])
        params['type_id'] = int(params['type_id'])
        params['predefined'] = params['predefined'] in ["True", "true"]
        params['mds_mode'] = params['mds_mode'] if params['mds_mode'] in [MdsMode.ROWS,
                                                                          MdsMode.COLUMNS] else MdsMode.ROWS
        params['conditions'] = json.loads(params['conditions'])
        params['selected_fields'] = literal_eval(params['selected_fields'])

        report_type = reports_manager.get_one_from_other_collection(CmdbType.COLLECTION, params['type_id'])
        params['report_query'] = {'data': json_util.dumps(MongoDBQueryBuilder(params['conditions'],
                                                                              CmdbType.from_data(report_type))
                                                                              .build())}

        new_report_id = reports_manager.insert_item(params)

        return DefaultResponse(new_report_id).make_response()
    except ReportsManagerInsertError as err:
        LOGGER.error("[create_cmdb_report] ReportsManagerInsertError: %s", err, exc_info=True)
        abort(400, "Failed to insert the new Report in the database!")
    except Exception as err:
        LOGGER.error("[create_cmdb_report] Exception: %s. Type: %s", err, type(err), exc_info=True)
        abort(500, "An internal server error occured while creating the Report!")

# ---------------------------------------------------- CRUD - READ --------------------------------------------------- #

@reports_blueprint.route('/<int:public_id>', methods=['GET'])
@insert_request_user
@verify_api_access(required_api_level=ApiLevel.ADMIN)
def get_cmdb_report(public_id: int, request_user: CmdbUser) -> Response:
    """
    Retrieves the CmdbReport with the given public_id
    
    Args:
        public_id (int): public_id of CmdbReport which should be retrieved
        request_user (CmdbUser): User which is requesting the CmdbReport
    """
    try:
        reports_manager: ReportsManager = ManagerProvider.get_manager(ManagerType.REPORTS, request_user)

        requested_report = reports_manager.get_item(public_id, as_dict=True)

        if not requested_report:
            abort(404, f"The Report with ID:{public_id} was not found!")

        return DefaultResponse(requested_report).make_response()
    except HTTPException as http_err:
        raise http_err
    except ReportsManagerGetError as err:
        LOGGER.error("[get_cmdb_report] ReportsManagerGetError: %s", err, exc_info=True)
        abort(400, f"Failed to retrieve the Report with ID: {public_id} from the database!")
    except Exception as err:
        LOGGER.error("[get_cmdb_report] Exception: %s. Type: %s", err, type(err), exc_info=True)
        abort(500, f"An internal server error occured while retrieving the Report with ID: {public_id}!")


@reports_blueprint.route('/', methods=['GET', 'HEAD'])
@reports_blueprint.parse_collection_parameters()
@insert_request_user
@verify_api_access(required_api_level=ApiLevel.ADMIN)
def get_cmdb_reports(params: CollectionParameters, request_user: CmdbUser) -> Response:
    """
    Returns all CmdbReports based on the params

    Args:
        params (CollectionParameters): Parameters to identify documents in database
        request_user (CmdbUser): User which is requesting the CmdbReports

    Returns:
        GetMultiResponse: All CmdbReports considering the params
    """
    try:
        reports_manager: ReportsManager = ManagerProvider.get_manager(ManagerType.REPORTS, request_user)

        builder_params: BuilderParameters = BuilderParameters(**CollectionParameters.get_builder_params(params))

        iteration_result: IterationResult[CmdbReport] = reports_manager.iterate_items(builder_params)
        report_list: list[dict] = [report_.__dict__ for report_ in iteration_result.results]

        api_response = GetMultiResponse(report_list,
                                        iteration_result.total,
                                        params,
                                        request.url,
                                        request.method == 'HEAD')

        return api_response.make_response()
    except ReportsManagerIterationError as err:
        LOGGER.error("[get_cmdb_reports] ImpactManagerIterationError: %s", err, exc_info=True)
        abort(400, "Failed to retrieve Reports from the database!")
    except Exception as err:
        LOGGER.error("[get_cmdb_reports] Exception: %s. Type: %s", err, type(err), exc_info=True)
        abort(500, "An internal server error occured while retrieving Reports!")


#TODO: DOCUMENT-API-FIX
@reports_blueprint.route('/<int:public_id>/count_reports_of_type', methods=['GET'])
@insert_request_user
@verify_api_access(required_api_level=ApiLevel.ADMIN)
def count_cmdb_reports_of_type(public_id: int, request_user: CmdbUser):
    """
    Return the number of reports in der database with the given public_id of a CmdbType

    Args:
        public_id (int): public_id of the CmdbType
        request_user (CmdbUser): CmdbUser which is requesting this data

    Returns:
        DefaultResponse: Number of CmdbReports for CmdbType
    """
    try:
        reports_manager: ReportsManager = ManagerProvider.get_manager(ManagerType.REPORTS, request_user)

        reports_count = reports_manager.count_items({'type_id':public_id})

        return DefaultResponse(reports_count).make_response()
    except ReportsManagerGetError as err:
        LOGGER.error("[count_cmdb_reports_of_type] ReportsManagerGetError: %s", err, exc_info=True)
        abort(400, f"Failed to retrieve the number of Reports for Type with ID: {public_id}!")
    except Exception as err:
        LOGGER.error("[count_cmdb_reports_of_type] Exception: %s. Type: %s", err, type(err), exc_info=True)
        abort(500,
              f"An internal server error occured while retrieving the number of Reports for Type with ID: {public_id}!"
             )


@reports_blueprint.route('/run/<int:public_id>', methods=['GET'])
@insert_request_user
@verify_api_access(required_api_level=ApiLevel.ADMIN)
def run_cmdb_report_query(public_id: int, request_user: CmdbUser):
    """
    Returns the result of the query of the CmdbReport

    Args:
        params (int): public_id of the CmdbReport
        request_user (CmdbUser): CmdbUser which is requesting this data

    Returns:
        DefaultResponse: Dict of the query result
    """
    try:
        preview_mode: bool = request.args.get("preview", default="false").lower() == "true"

        reports_manager: ReportsManager = ManagerProvider.get_manager(ManagerType.REPORTS, request_user)
        objects_manager: ObjectsManager = ManagerProvider.get_manager(ManagerType.OBJECTS, request_user)

        requested_report: dict = reports_manager.get_item(public_id, as_dict=True)
        LOGGER.debug(f"requested_report: {requested_report}")

        if not requested_report:
            abort(404, f"The Report with ID:{public_id} was not found!")

        query_str: str = requested_report['report_query']['data']
        report_query = parse_report_query(query_str)

        result = {}

        # Only execute the report if there are conditions
        if len(report_query) > 0:
            builder_params = BuilderParameters(criteria=report_query)

            result = objects_manager.iterate(builder_params).results

            # Only show maximum 2 elements if preview_mode
            if preview_mode:
                result = result[:2]

        LOGGER.debug(f"report result: {result}")
        return DefaultResponse(result).make_response()
    except HTTPException as http_err:
        raise http_err
    except ReportsManagerGetError as err:
        LOGGER.error("[run_cmdb_report_query] ReportsManagerGetError: %s", err, exc_info=True)
        abort(400, f"Failed to retrieve the Report with ID: {public_id} from the database!")
    except ValueError as err:
        LOGGER.error("[run_cmdb_report_query] Invalid report query format: %s", err, exc_info=True)
        abort(400, "The Report query has an invalid format!")
    except Exception as err:
        LOGGER.error("[run_cmdb_report_query] Exception: %s. Type: %s", err, type(err), exc_info=True)
        abort(500, f"An internal server error occured while running the Report with ID: {public_id}!")

# --------------------------------------------------- CRUD - UPDATE -------------------------------------------------- #

@reports_blueprint.route('/<int:public_id>', methods=['PUT','PATCH'])
@reports_blueprint.parse_request_parameters()
@insert_request_user
@verify_api_access(required_api_level=ApiLevel.ADMIN)
def update_cmdb_report(public_id: int, params: dict, request_user: CmdbUser):
    """
    Updates a CmdbReport

    Args:
        public_id (int): public_id of CmdbReport which should be updated
        params (dict): updated CmdbReport parameters
        request_user (CmdbUser): CmdbUser which is requesting this update

    Returns:
        UpdateSingleResponse: The updated CmdbReport as a dict
    """
    try:
        reports_manager: ReportsManager = ManagerProvider.get_manager(ManagerType.REPORTS, request_user)

        params['public_id'] = int(public_id)
        params['report_category_id'] = int(params['report_category_id'])
        params['type_id'] = int(params['type_id'])
        params['predefined'] = params['predefined'] in ["True", "true"]
        params['conditions'] = json.loads(params['conditions'])
        params['selected_fields'] = literal_eval(params['selected_fields'])
        params['mds_mode'] = params['mds_mode'] if params['mds_mode'] in [MdsMode.ROWS,
                                                                          MdsMode.COLUMNS] else MdsMode.ROWS

        current_report = reports_manager.get_item(public_id, as_dict=True)

        if not current_report:
            abort(404, f"The Report with ID:{public_id} was not found!")

        report_type = reports_manager.get_one_from_other_collection(CmdbType.COLLECTION, params['type_id'])
        params['report_query'] = {'data': json_util.dumps(MongoDBQueryBuilder(params['conditions'],
                                                                              CmdbType.from_data(report_type))
                                                                              .build())}

        reports_manager.update_item(public_id, params)
        current_report = reports_manager.get_item(public_id, as_dict=True)

        if not current_report:
            abort(404, f"The updated Report with ID:{public_id} was not found!")

        return UpdateSingleResponse(current_report).make_response()
    except HTTPException as http_err:
        raise http_err
    except ReportsManagerGetError as err:
        LOGGER.error("[update_cmdb_report] ReportsManagerGetError: %s", err, exc_info=True)
        abort(400, f"Failed to retrieve the Report with ID: {public_id} from the database!")
    except ReportsManagerUpdateError as err:
        LOGGER.error("[update_cmdb_report] ReportsManagerUpdateError: %s", err, exc_info=True)
        abort(400, f"Failed to update the Report with ID: {public_id}!")
    except Exception as err:
        LOGGER.error("[update_cmdb_report] Exception: %s. Type: %s", err, type(err), exc_info=True)
        abort(500, f"An internal server error occured while updating the Report with ID: {public_id}!")

# --------------------------------------------------- CRUD - DELETE -------------------------------------------------- #

@reports_blueprint.route('/<int:public_id>/', methods=['DELETE'])
@insert_request_user
@verify_api_access(required_api_level=ApiLevel.ADMIN)
def delete_cmdb_report(public_id: int, request_user: CmdbUser):
    """
    Deletes the CmdbReport with the given public_id
    
    Args:
        public_id (int): public_id of CmdbReport which should be retrieved
        request_user (CmdbUser): User which is requesting the deletion

    Returns:
        DefaultResponse: True if deletion was successful, else False
    """
    try:
        reports_manager: ReportsManager = ManagerProvider.get_manager(ManagerType.REPORTS, request_user)

        report_instance = reports_manager.get_item(public_id)

        if not report_instance:
            abort(404, f"The Report with ID:{public_id} was not found!")

        ack = reports_manager.delete_item(public_id)

        return DefaultResponse(ack).make_response()
    except HTTPException as http_err:
        raise http_err
    except ReportsManagerGetError as err:
        LOGGER.error("[delete_cmdb_report] ReportsManagerGetError: %s", err, exc_info=True)
        abort(400, f"Failed to retrieve the Report with ID: {public_id} from the database!")
    except ReportsManagerDeleteError as err:
        LOGGER.error("[delete_cmdb_report] ReportsManagerDeleteError: %s", err, exc_info=True)
        abort(400, f"Failed to delete the Report with ID: {public_id}!")
    except Exception as err:
        LOGGER.error("[delete_cmdb_report] Exception: %s. Type: %s", err, type(err), exc_info=True)
        abort(500, f"An internal server error occured while deleting the Report with ID: {public_id}!")

# ------------------------------------------------------ HELPERS ----------------------------------------------------- #

def parse_report_query(query_data: str) -> dict[str, Any]:
    """
    Safely parses stored report queries. Supports JSON (preferred) and legacy Python dict strings.
    """
    if not isinstance(query_data, str):
        raise ValueError("Report query data must be a string!")

    if len(query_data) > MAX_REPORT_QUERY_LENGTH:
        raise ValueError("Report query data is too large!")

    json_result = _parse_json_report_query(query_data)
    if json_result is not None:
        return json_result

    return _parse_legacy_report_query(query_data)


def _parse_json_report_query(query_data: str) -> dict[str, Any] | None:
    """
    Parses report queries stored as BSON Extended JSON.
    """
    try:
        parsed_query = json_util.loads(query_data)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None

    if not isinstance(parsed_query, dict):
        raise ValueError("Report query must be a dictionary!")

    return parsed_query


def _parse_legacy_report_query(query_data: str) -> dict[str, Any]:
    """
    Parses legacy report queries that were stored as Python dict string representations.
    """
    normalized_query = query_data.replace("datetime.datetime", "datetime")

    try:
        parsed_tree = ast.parse(normalized_query, mode='eval')
    except SyntaxError as err:
        raise ValueError("Invalid legacy report query syntax!") from err

    parsed_query = _safe_eval_query_node(parsed_tree.body)

    if not isinstance(parsed_query, dict):
        raise ValueError("Parsed report query must be a dictionary!")

    return parsed_query


def _safe_eval_query_node(node: ast.AST) -> Any:
    """
    Evaluates a limited and safe subset of Python AST nodes required for report query parsing.
    """
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (str, int, float, bool, type(None))):
            return node.value
        raise ValueError("Unsupported constant type in report query!")

    if isinstance(node, ast.Dict):
        return {
            _safe_eval_query_node(key): _safe_eval_query_node(value)
            for key, value in zip(node.keys, node.values)
        }

    if isinstance(node, ast.List):
        return [_safe_eval_query_node(element) for element in node.elts]

    if isinstance(node, ast.Tuple):
        return tuple(_safe_eval_query_node(element) for element in node.elts)

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _safe_eval_query_node(node.operand)
        if not isinstance(operand, (int, float)):
            raise ValueError("Unary operations are only allowed on numbers!")
        return operand if isinstance(node.op, ast.UAdd) else -operand

    if isinstance(node, ast.Call):
        return _parse_datetime_call(node)

    raise ValueError(f"Unsupported expression in report query: {ast.dump(node)}")


def _parse_datetime_call(node: ast.Call) -> datetime:
    """
    Parses datetime(...) or datetime.datetime(...) calls from legacy report query strings.
    """
    is_datetime_name = isinstance(node.func, ast.Name) and node.func.id == "datetime"
    is_datetime_attribute = (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "datetime"
        and node.func.attr == "datetime"
    )

    if not (is_datetime_name or is_datetime_attribute):
        raise ValueError("Only datetime constructor calls are allowed in report queries!")

    if node.keywords:
        raise ValueError("Keyword arguments are not allowed in datetime constructors!")

    args = [_safe_eval_query_node(arg) for arg in node.args]
    if not args or any(not isinstance(arg, int) for arg in args):
        raise ValueError("datetime constructor expects integer positional arguments only!")

    return datetime(*args)
