import json
import os
from minio.error import NoSuchKey
from flask import Flask, request, abort, jsonify
from typing import Dict
from redis import Redis

from engine.data_sources.atlas.atlas_table import AtlasTable
from engine.data_sources.base_source import GUIDMissing
from engine.data_sources.atlas.atlas_source import AtlasSource
from engine.data_sources.base_db import BaseDB
from engine.data_sources.base_table import BaseTable
from engine.data_sources.minio.minio_source import MinioSource
from engine.data_sources.minio.minio_table import MinioTable
from engine.utils.api_utils import AtlasPayload, get_atlas_payload, validate_matcher, get_atlas_source, \
     get_holistic_matches, format_matches, get_matcher, MinioPayload, get_minio_payload
from engine.utils.exceptions import check_if_table_has_columns, check_if_db_is_empty
from engine.utils.utils import get_sha1_hash_of_string, get_timestamp

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False  # this is needed for the sorted list output because we sort by value


redis_db: Redis = Redis(host=os.environ['REDIS_HOST'], port=os.environ['REDIS_PORT'])


@app.route("/matches/atlas/holistic/<table_guid>", methods=['GET'])
def find_holistic_matches_of_table_atlas(table_guid: str):
    payload: AtlasPayload = get_atlas_payload(request.json)
    validate_matcher(payload.matching_algorithm, payload.matching_algorithm_params, "atlas")
    atlas_src: AtlasSource = get_atlas_source(payload)
    try:
        table: AtlasTable = atlas_src.get_db_table(table_guid)
        check_if_table_has_columns(table)
        schemata: Dict[object, BaseDB] = atlas_src.get_all_dbs()
    except json.JSONDecodeError:
        abort(500, "Couldn't connect to Atlas. This is a network issue, "
                   "try to lower the request_chunk_size and the request_parallelism in the payload")
    except GUIDMissing:
        abort(400, 'This guid does not correspond to any database in atlas! '
                   'Check if the given database types are correct or if there is a mistake in the guid')
    except KeyError:
        abort(400, 'This guid does not correspond to any table in atlas! '
                   'Check if the given table types are correct or if there is a mistake in the guid')
    else:
        matches = get_holistic_matches(schemata, table, payload)
        matching_jobs_guid = get_sha1_hash_of_string(
            get_timestamp() + '/atlas/holistic/' + str(table.unique_identifier))
        redis_db.set(matching_jobs_guid, format_matches(matches, payload.max_number_matches))
        return matching_jobs_guid


@app.route('/matches/atlas/other_db/<table_guid>/<db_guid>', methods=['GET'])
def find_matches_other_db_atlas(table_guid: str, db_guid: str):
    payload: AtlasPayload = get_atlas_payload(request.json)
    validate_matcher(payload.matching_algorithm, payload.matching_algorithm_params, "atlas")
    atlas_src: AtlasSource = get_atlas_source(payload)
    try:
        table: AtlasTable = atlas_src.get_db_table(table_guid)
        check_if_table_has_columns(table)
        db_schema: BaseDB = atlas_src.get_db(db_guid)
    except json.JSONDecodeError:
        abort(500, "Couldn't connect to Atlas. This is a network issue, "
                   "try to lower the request_chunk_size and the request_parallelism in the payload")
    except GUIDMissing:
        abort(400, 'This guid does not correspond to any database in atlas! '
                   'Check if the given database types are correct or if there is a mistake in the guid')
    except KeyError:
        abort(400, 'This guid does not correspond to any table in atlas! '
                   'Check if the given table types are correct or if there is a mistake in the guid')
    else:
        check_if_db_is_empty(db_schema)
        matcher = get_matcher(payload.matching_algorithm, payload.matching_algorithm_params)
        matches: list = matcher.get_matches(db_schema, table)
        matching_jobs_guid = get_sha1_hash_of_string(
            get_timestamp() + '/atlas/other_db/' + db_guid + str(table.unique_identifier))
        redis_db.set(matching_jobs_guid, format_matches(matches, payload.max_number_matches))
        return matching_jobs_guid


@app.route('/matches/atlas/within_db/<table_guid>', methods=['GET'])
def find_matches_within_db_atlas(table_guid: str):
    payload: AtlasPayload = get_atlas_payload(request.json)
    validate_matcher(payload.matching_algorithm, payload.matching_algorithm_params, "atlas")
    atlas_src: AtlasSource = get_atlas_source(payload)
    try:
        table: AtlasTable = atlas_src.get_db_table(table_guid)
        check_if_table_has_columns(table)
        db_schema: BaseDB = atlas_src.get_db(table.db_belongs_uid)
    except json.JSONDecodeError:
        abort(500, "Couldn't connect to Atlas. This is a network issue, "
                   "try to lower the request_chunk_size and the request_parallelism in the payload")
    except GUIDMissing:
        abort(400, 'This guid does not correspond to any database in atlas! '
                   'Check if the given database types are correct or if there is a mistake in the guid')
    except KeyError:
        abort(400, 'This guid does not correspond to any table in atlas! '
                   'Check if the given table types are correct or if there is a mistake in the guid')
    else:
        # remove the table from the schema so that it doesn't compare against itself
        r_table: BaseTable = db_schema.remove_table(table_guid)
        check_if_db_is_empty(db_schema)
        matcher = get_matcher(payload.matching_algorithm, payload.matching_algorithm_params)
        matches: list = matcher.get_matches(db_schema, table)
        # add the removed table back into the schema
        db_schema.add_table(r_table)
        matching_jobs_guid = get_sha1_hash_of_string(
            get_timestamp() + '/atlas/within_db/' + str(table.unique_identifier))
        redis_db.set(matching_jobs_guid, format_matches(matches, payload.max_number_matches))
        return matching_jobs_guid


@app.route("/matches/minio/holistic", methods=['GET'])
def find_holistic_matches_of_table_minio():
    payload: MinioPayload = get_minio_payload(request.json)
    validate_matcher(payload.matching_algorithm, payload.matching_algorithm_params, "minio")
    minio_source: MinioSource = MinioSource()
    try:
        table: MinioTable = minio_source.get_db_table(payload.table_name, payload.db_name)
        check_if_table_has_columns(table)
        dbs: Dict[object, BaseDB] = minio_source.get_all_dbs()
    except NoSuchKey:
        abort(400, "The table does not exist")
    else:
        matches = get_holistic_matches(dbs, table, payload)
        matching_jobs_guid = get_sha1_hash_of_string(
            get_timestamp() + '/minio/holistic/' + str(table.unique_identifier))
        redis_db.set(matching_jobs_guid, format_matches(matches, payload.max_number_matches))
        return matching_jobs_guid


@app.route('/matches/minio/other_db/<db_name>', methods=['GET'])
def find_matches_other_db_minio(db_name: str):
    payload: MinioPayload = get_minio_payload(request.json)
    validate_matcher(payload.matching_algorithm, payload.matching_algorithm_params, "minio")
    minio_source: MinioSource = MinioSource()
    try:
        table: MinioTable = minio_source.get_db_table(payload.table_name, payload.db_name)
        check_if_table_has_columns(table)
        db_schema: BaseDB = minio_source.get_db(db_name)
    except NoSuchKey:
        abort(400, "The table does not exist")
    else:
        check_if_db_is_empty(db_schema)
        matcher = get_matcher(payload.matching_algorithm, payload.matching_algorithm_params)
        matches: list = matcher.get_matches(db_schema, table)
        matching_jobs_guid = get_sha1_hash_of_string(
            get_timestamp() + '/minio/other_db/' + db_name + str(table.unique_identifier))
        redis_db.set(matching_jobs_guid, format_matches(matches, payload.max_number_matches))
        return matching_jobs_guid


@app.route('/matches/minio/within_db', methods=['GET'])
def find_matches_within_db_minio():
    payload: MinioPayload = get_minio_payload(request.json)
    validate_matcher(payload.matching_algorithm, payload.matching_algorithm_params, "minio")
    minio_source: MinioSource = MinioSource()
    try:
        table: MinioTable = minio_source.get_db_table(payload.table_name, payload.db_name)
        check_if_table_has_columns(table)
        db_schema: BaseDB = minio_source.get_db(table.db_belongs_uid)
    except NoSuchKey:
        abort(400, "The table does not exist")
    else:
        r_table: BaseTable = db_schema.remove_table(payload.table_name)
        check_if_db_is_empty(db_schema)
        matcher = get_matcher(payload.matching_algorithm, payload.matching_algorithm_params)
        matches: list = matcher.get_matches(db_schema, table)
        # add the removed table back into the schema
        db_schema.add_table(r_table)
        matching_jobs_guid = get_sha1_hash_of_string(get_timestamp()+'/minio/within_db/' + str(table.unique_identifier))
        redis_db.set(matching_jobs_guid, format_matches(matches, payload.max_number_matches))
        return matching_jobs_guid


@app.route('/test/redis', methods=['POST'])
def put_test_redis():
    matches = [
        {"source": {"name": "s1", "guid": "g1"},
         "target": {"name": "t1", "guid": "g2"},
         "sim": 0.78532},
        {"source": {"name": "s2", "guid": "g3"},
         "target": {"name": "t2", "guid": "g4"},
         "sim": 0.5234}]
    redis_db.set("test_key", json.dumps(matches))
    matches_from_redis = list(json.loads(redis_db.get("test_key")))
    return jsonify(matches_from_redis)


if __name__ == '__main__':
    app.run(debug=False)
