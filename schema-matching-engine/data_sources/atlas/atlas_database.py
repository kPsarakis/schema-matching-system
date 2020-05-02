from typing import Dict
from multiprocessing import get_context

from data_sources.atlas.atlas_table import AtlasTable
from data_sources.atlas.atlas_utils import get_entity_with_guid, get_bulk_entities
from data_sources.base_db import BaseDB
from data_sources.base_table import BaseTable


class AtlasDatabase(BaseDB):

    def __init__(self, url: str, auth: tuple, guid: object, parallelism: int, chunk_size: int):
        self.guid = guid
        self.__url = url
        self.__auth = auth
        self.__parallelism = parallelism
        self.__chunk_size = chunk_size
        self.__db_name = ""
        self.__technology = ""
        self.__tables: Dict[object, BaseTable] = dict()
        self.__get_tables_from_atlas()

    @property
    def unique_identifier(self):
        return self.guid

    @property
    def name(self):
        return self.__db_name

    def get_tables(self) -> Dict[str, BaseTable]:
        tables: Dict[str, BaseTable] = {val.name: val for val in self.__tables.values() if val.number_of_columns > 0}
        return tables

    def remove_table(self, guid: object) -> BaseTable:
        table_to_be_removed = self.__tables[guid]
        del self.__tables[guid]
        return table_to_be_removed

    def add_table(self, table: BaseTable) -> None:
        self.__tables[table.unique_identifier] = table

    def __get_tables_from_atlas(self):
        entity = get_entity_with_guid(self.__url, self.__auth, str(self.guid))["entity"]

        self.__technology = entity["attributes"]["technologyPlatform"]
        self.__db_name = entity["attributes"]["qualifiedName"]

        atlas_tables: list = []

        if self.__technology == "mssql":
            atlas_tables = entity["relationshipAttributes"]["tables"]
        elif self.__technology == "Elasticsearch":
            atlas_tables = entity["relationshipAttributes"]["indices"]

        guids = [table['guid'] for table in atlas_tables]

        if len(guids) == 0:
            return

        column_guids = dict()

        with get_context("spawn").Pool(self.__parallelism) as process_pool:

            responses = list(process_pool.map(self.parallel_bulk_requests,
                                              list(self.entity_table_guid_chunk_generator(guids, self.__chunk_size))))

            for entities in responses:
                for e in entities['entities']:
                    columns = None
                    if self.__technology == "mssql":
                        columns = e['relationshipAttributes']['columns']
                    elif self.__technology == "Elasticsearch":
                        columns = e["relationshipAttributes"]["fields"]
                    tmp = []
                    for column in columns:
                        tmp.append(column['guid'])
                    column_guids[e['guid']] = tmp

            self.__tables = dict(process_pool.map(self.get_table_atlas,
                                                  list(self.parallel_http_request_input_generator(atlas_tables,
                                                                                                  column_guids,
                                                                                                  self.__technology))))

    def parallel_bulk_requests(self, chunk: list):
        return get_bulk_entities(self.__url, self.__auth, chunk)

    def get_table_atlas(self, tup: tuple):
        t_name, t_guid, c_guids, tech = tup
        return t_guid, AtlasTable(self.__url, self.__auth, t_name, t_guid, c_guids, tech, str(self.guid),
                                  self.__chunk_size)

    @staticmethod
    def parallel_http_request_input_generator(atlas_tables: list, column_guids: dict, technology: str):
        for table in atlas_tables:
            yield table['displayText'], table['guid'], column_guids[table['guid']], technology

    @staticmethod
    def entity_table_guid_chunk_generator(guids: list, chunk_size: int):
        for i in range(len(guids) // chunk_size + 1):
            chunk = guids[i * chunk_size:(i + 1) * chunk_size]
            if len(chunk) != 0:
                yield chunk
