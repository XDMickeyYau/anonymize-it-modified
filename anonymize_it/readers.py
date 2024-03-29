from abc import ABCMeta, abstractmethod
from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, A
import getpass
import utils
import logging


class ESReaderError(Exception):
    pass


class ProviderInferenceError(Exception):
    pass


def es_field_mappings(es_type, field):
    es_types = {
        "text": [],
        "keyword": [],
        "long": [],
        "integer": [],
        "short": [],
        "byte": [],
        "double": [],
        "float": [],
        "half_float": [],
        "scaled_float": [],
        "date": [],
        "boolean": [],
        "binary": [],
        "integer_range": [],
        "float_range": [],
        "long_range": [],
        "double_range": [],
        "date_range": [],
        "object": [],
        "nested": [],
        "geo_point": [],
        "geo_shape": [],
        "ip": [],
        "completion": [],
        "token_count": [],
        "murmur3": []
    }

    es_types[es_type]
    return field


class BaseReader:
    def __init__(self, params, masked_fields, suppressed_fields):
        self.masked_fields = masked_fields
        self.suppressed_fields = suppressed_fields

        logging.info("masked_fields = {}".format(self.masked_fields))
        logging.info("suppressed_fields = {}".format(self.suppressed_fields))

    @abstractmethod
    def create_mappings(self):
        pass

    @abstractmethod
    def get_data(self, field_maps, suppressed_fields, include_all):
        pass

    @abstractmethod
    def infer_providers(self):
        pass


class ESReader(BaseReader):
    def __init__(self, params, masked_fields, suppressed_fields):
        super().__init__(params, masked_fields, suppressed_fields)

        self.type = 'elasticsearch'
        self.username = getpass.getpass('elasticsearch username: ')
        self.password = getpass.getpass('elasticsearch password: ')
        self.host = params.get('host')
        self.index_pattern = params.get('index')
        self.query = params.get('query')
        self.es = None


        if not all([self.host, self.username, self.password]):
            raise ESReaderError("elasticsearch configuration malformed. please check config.")

        self.es = Elasticsearch([self.host], http_auth=(self.username, self.password), verify_certs=False)

        logging.info("elasticsearch host = {}".format(self.host))
        logging.info("elasticsearch index = {}".format(self.index_pattern))
        logging.info("using query = {}".format(self.query))

    def create_mappings(self):
        logging.info("creating mappings...")
        mappings = {}
        for field, provider in self.masked_fields.items():
            logging.info("getting values for {} using provider {}".format(field, provider))
            mappings[field] = {}
            cont = True
            term = ""
            size = 10000
            fristsearch=True
            if provider:
                while cont:
                    response = self.es.search(index=self.index_pattern,
                                              body=utils.composite_query(field, size, self.query, term,firstquery=fristsearch))
                    logging.info("{}".format(utils.composite_query(field, size, self.query),firstquery=fristsearch))
                    for hit in response['aggregations']['my_buckets']['buckets']:
                        mappings[field][hit['key'][field]] = None
                    logging.info("{}".format(len(response['aggregations']["my_buckets"]['buckets'])))
                    if len(response['aggregations']["my_buckets"]['buckets']) < size:
                        cont = False
                    #last item exist only of len>0
                    if len(response['aggregations']["my_buckets"]['buckets']) > 0:
                        term = response['aggregations']["my_buckets"]['buckets'][-1]['key'][field]
                    fristsearch = False

        logging.info("mappings completed...")
        return mappings

    def get_count(self):
        s = Search(using=self.es, index=self.index_pattern)
        if self.query:
            s.update_from_dict({"query": self.query})
        return s.count()

    def get_data(self, include, suppressed_fields, include_all=False):
        """
        :param field_maps:
        :param suppressed_fields:
        :param include_all:
        :return:
        """

        s = Search(using=self.es, index=self.index_pattern)
        if self.query:
            s.update_from_dict({"query": self.query})

        if not include_all:
            s = s.source(include=include, exclude=suppressed_fields)
        else:
            s = s.source(exclude=suppressed_fields)

        logging.info("gathering data from elasticsearch...")

        response = s.scan()
        return response

    def infer_providers(self):

        for field, provider in self.masked_fields.items():
            types = []
            if provider == 'infer':
                mappings = self.es.indices.get_field_mapping(index=self.index_pattern, fields=[field])
                for index, mapping in mappings.items():
                    suff = field.split(".")[-1]
                    types.append(mapping['mappings']['doc'][field]['mapping'][suff]['type'])
                if len(set(types)) != 1:
                    raise ProviderInferenceError('mappings for {} not consistent across indices. Cannot infer mapping'
                                                 .format(field))
                self.masked_fields[field] = {}
                self.masked_fields[field]['mapping'] = types[0]
                self.masked_fields[field]['inferred'] = None

        print(self.masked_fields)


class CSVReader(BaseReader):
    def __init__(self, params):
        super().__init__(params)

    def get_data(self, field_maps, suppressed_fields, include_all):
        pass

    def infer_providers(self):
        pass


class PandasReader(BaseReader):
    def __init__(self, params):
        super().__init__(params)

    def get_data(self, field_maps, suppressed_fields, include_all):
        pass

    def infer_providers(self):
        pass


reader_mapping = {
    "elasticsearch": ESReader,
    "csv": CSVReader,
    "pandas": PandasReader
}

