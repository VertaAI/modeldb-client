import six

import numpy as np
import os
import pytest
import time
import utils
import shutil

from verta._dataset import Dataset, DatasetVersion, S3DatasetVersionInfo, FilesystemDatasetVersionInfo
from verta._protos.public.modeldb import DatasetService_pb2 as _DatasetService
from verta._protos.public.modeldb import DatasetVersionService_pb2 as _DatasetVersionService


class TestBaseDatasets:
    def test_creation_from_scratch(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf,
                          name=name, dataset_type=_DatasetService.DatasetTypeEnum.PATH)
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.PATH
        assert dataset.id

    def test_creation_by_id(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf,
                          name=name, dataset_type=_DatasetService.DatasetTypeEnum.PATH)
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.PATH
        assert dataset.id

        same_dataset = Dataset(client._conn, client._conf,
                               _dataset_id=dataset.id)
        assert dataset.id == same_dataset.id


class TestBaseDatasetVersions:
    def test_creation_from_scratch(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf,
                          name=name, dataset_type=_DatasetService.DatasetTypeEnum.PATH)
        version = DatasetVersion(client._conn, client._conf,
                                 dataset_id=dataset.id,
                                 dataset_version_info=_DatasetVersionService.PathDatasetVersionInfo(),
                                 dataset_type=_DatasetService.DatasetTypeEnum.PATH)
        assert version.dataset_type == _DatasetService.DatasetTypeEnum.PATH
        assert version.id

    def test_creation_by_id(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf,
                          name=name, dataset_type=_DatasetService.DatasetTypeEnum.PATH)
        version = DatasetVersion(client._conn, client._conf,
                                 dataset_id=dataset.id,
                                 dataset_version_info=_DatasetVersionService.PathDatasetVersionInfo(),
                                 dataset_type=_DatasetService.DatasetTypeEnum.PATH)
        assert version.dataset_type == _DatasetService.DatasetTypeEnum.PATH
        assert version.id

        same_version = DatasetVersion(client._conn, client._conf,
                                      _dataset_version_id=version.id)
        assert version.id == same_version.id


# TODO: not implemented
class TestRawDatasets:
    pass


# TODO: not implemented
class TestRawDatasetVersions:
    pass


class TestPathDatasets:
    def test_creation_from_scratch(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf,
                          name=name, dataset_type=_DatasetService.DatasetTypeEnum.PATH)
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.PATH
        assert dataset.id

    def test_creation_by_id(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf,
                          name=name, dataset_type=_DatasetService.DatasetTypeEnum.PATH)
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.PATH
        assert dataset.id

        same_dataset = Dataset(client._conn, client._conf,
                               _dataset_id=dataset.id)
        assert dataset.id == same_dataset.id


class TestClientDatasetFunctions:
    def test_creation_from_scratch_client_api(self, client):
        name = utils.gen_str()
        dataset = client.set_dataset(name=name, type="s3")
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.PATH
        assert dataset.id

    def test_creation_by_id_client_api(self, client):
        name = utils.gen_str()
        dataset = client.set_dataset(name=name, type="s3")
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.PATH
        assert dataset.id

        same_dataset = client.set_dataset(id=dataset.id)
        assert dataset.id == same_dataset.id
        assert dataset.name == same_dataset.name

    def test_get_dataset_client_api(self, client):
        name = utils.gen_str()
        dataset = client.set_dataset(name=name, type="s3")
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.PATH
        assert dataset.id

        same_dataset = client.get_dataset(id=dataset.id)
        assert dataset.id == same_dataset.id
        assert dataset.name == same_dataset.name

        same_dataset = client.get_dataset(name=dataset.name)
        assert dataset.id == same_dataset.id
        assert dataset.name == same_dataset.name

    def test_find_datasets_client_api(self, client):
        name1 = utils.gen_str()
        dataset1 = client.set_dataset(name=name1, type="big query",
            tags=["test1-" + name1, "test2-" + name1])
        assert dataset1.dataset_type == _DatasetService.DatasetTypeEnum.QUERY
        assert dataset1.id

        name2 = utils.gen_str()
        dataset2 = client.set_dataset(name=name2, type="s3", tags=["test1"])
        assert dataset2.dataset_type == _DatasetService.DatasetTypeEnum.PATH
        assert dataset2.id

        # TODO: update once RAW is supported
        # name = utils.gen_str()
        # dataset3 = client.set_dataset(name=name, type="raw")
        # assert dataset3.dataset_type == _DatasetService.DatasetTypeEnum.RAW
        # assert dataset3.id

        # datasets = client.find_datasets()
        # assert len(datasets) == 3
        # assert datasets[0].id == dataset1.id
        # assert datasets[1].id == dataset2.id
        # assert datasets[2].id == dataset3.id

        datasets = client.find_datasets()
        assert len(datasets) >= 2 # at least 2 because they were just created. Needs to be updated

        datasets = client.find_datasets(tags=["test1-" + name1,
            "test2-" + name1])
        assert len(datasets) == 1
        assert datasets[0].id == dataset1.id


class TestClientDatasetVersionFunctions:
    def test_creation_from_scratch(self, client):
        name = utils.gen_str()
        dataset = client.set_dataset(name=name, type="local")

        version = dataset.create_version(__file__)
        assert version.dataset_type == _DatasetService.DatasetTypeEnum.PATH
        assert version.id

    def test_creation_by_id(self, client):
        name = utils.gen_str()
        dataset = client.set_dataset(name=name, type="local")

        version = dataset.create_version(__file__)
        assert version.dataset_type == _DatasetService.DatasetTypeEnum.PATH
        assert version.id

        same_version = client.get_dataset_version(id=version.id)
        assert version.id == same_version.id

    def test_get_versions(self, client):
        name = utils.gen_str()
        dataset = client.set_dataset(name=name, type="local")

        version1 = dataset.create_version(path=__file__)
        assert version1.dataset_type == _DatasetService.DatasetTypeEnum.PATH
        assert version1.id

        version2 = dataset.create_version(path=pytest.__file__)
        assert version2.dataset_type == _DatasetService.DatasetTypeEnum.PATH
        assert version2.id

        versions = dataset.get_all_versions()
        assert len(versions) == 2

        dataset_version1 = client.get_dataset_version(id=version1.id)
        assert dataset_version1.id == version1.id

        version = dataset.get_latest_version(ascending=True)
        assert version.id == version1.id

    def test_reincarnation(self, client):
        """Consecutive identical versions are assigned the same ID."""
        name = utils.gen_str()
        dataset = client.set_dataset(name=name, type="local")

        version1 = dataset.create_version(path=__file__)
        version2 = dataset.create_version(path=__file__)
        assert version1.id == version2.id

        versions = dataset.get_all_versions()
        assert len(versions) == 1

        version = dataset.get_latest_version(ascending=True)
        assert version.id == version1.id


class TestPathBasedDatasetVersions:
    def test_creation_from_scratch(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf,
                          name=name, dataset_type=_DatasetService.DatasetTypeEnum.PATH)

        version = DatasetVersion(client._conn, client._conf,
                                 dataset_id=dataset.id,
                                 dataset_version_info=_DatasetVersionService.PathDatasetVersionInfo(),
                                 dataset_type=_DatasetService.DatasetTypeEnum.PATH)
        assert version.dataset_type == _DatasetService.DatasetTypeEnum.PATH
        assert version.id

    def test_creation_by_id(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf,
                          name=name, dataset_type=_DatasetService.DatasetTypeEnum.PATH)

        version = DatasetVersion(client._conn, client._conf,
                                 dataset_id=dataset.id,
                                 dataset_version_info=_DatasetVersionService.PathDatasetVersionInfo(),
                                 dataset_type=_DatasetService.DatasetTypeEnum.PATH)
        assert version.dataset_type == _DatasetService.DatasetTypeEnum.PATH
        assert version.id

        same_version = DatasetVersion(client._conn, client._conf,
                                      _dataset_version_id=version.id)
        assert version.id == same_version.id


class TestQueryDatasets:
    def test_creation_from_scratch(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf,
                          name=name, dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.QUERY)
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.DatasetType.QUERY
        assert dataset.id

    def test_creation_by_id(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf,
                          name=name, dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.QUERY)
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.DatasetType.QUERY
        assert dataset.id

        same_dataset = Dataset(client._conn, client._conf,
                               _dataset_id=dataset.id)
        assert dataset.id == same_dataset.id


class TestQueryDatasetVersions:
    def test_creation_from_scratch(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf,
                          name=name, dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.QUERY)

        version = DatasetVersion(client._conn, client._conf,
                                 dataset_id=dataset.id,
                                 dataset_version_info=_DatasetVersionService.QueryDatasetVersionInfo(),
                                 dataset_type=_DatasetService.DatasetTypeEnum.QUERY)
        assert version.dataset_type == _DatasetService.DatasetTypeEnum.QUERY
        assert version.id

    def test_creation_by_id(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf,
                          name=name, dataset_type=_DatasetService.DatasetTypeEnum.QUERY)

        version = DatasetVersion(client._conn, client._conf,
                                 dataset_id=dataset.id,
                                 dataset_version_info=_DatasetVersionService.QueryDatasetVersionInfo(),
                                 dataset_type=_DatasetService.DatasetTypeEnum.QUERY)
        assert version.dataset_type == _DatasetService.DatasetTypeEnum.QUERY
        assert version.id

        same_version = DatasetVersion(client._conn, client._conf,
                                      _dataset_version_id=version.id)
        assert version.id == same_version.id


class TestFileSystemDatasetVersionInfo:
    def test_single_file(self):
        dir_name, file_names = self.create_dir_with_files(num_files=1)
        fsdvi = FilesystemDatasetVersionInfo(dir_name + "/" + file_names[0])
        assert len(fsdvi.dataset_part_infos) == 1
        assert fsdvi.size == 7
        shutil.rmtree(dir_name)

    def test_dir(self):
        dir_name, _ = self.create_dir_with_files(num_files=10)
        fsdvi = FilesystemDatasetVersionInfo(dir_name)
        assert len(fsdvi.dataset_part_infos) == 10
        assert fsdvi.size == 70
        shutil.rmtree(dir_name)

    def create_dir_with_files(self, num_files=10):
        dir_name = 'FSD:' + str(time.time())
        file_names = []
        os.mkdir(dir_name)
        for num_file in range(num_files):
            file_name = str(num_file) + ".txt"
            f = open(dir_name + "/" + file_name, 'w')
            f.write('123456\n')
            file_names.append(file_name)
        return dir_name, file_names


class TestS3DatasetVersionInfo:
    def test_single_object(self, s3_bucket, s3_object):
        s3dvi = S3DatasetVersionInfo(s3_bucket, s3_object)
        assert len(s3dvi.dataset_part_infos) == 1
        assert s3dvi.size > 0

    def test_bucket(self, s3_bucket):
        s3dvi = S3DatasetVersionInfo(s3_bucket)
        assert len(s3dvi.dataset_part_infos) >= 1
        assert s3dvi.size > 0


class TestS3ClientFunctions:
    def test_s3_dataset_creation(self, client):
        name = utils.gen_str()
        dataset = client.set_dataset("s3-" + name, type="s3")
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.PATH

    def test_s3_dataset_version_creation(self, client, s3_bucket):
        name = utils.gen_str()
        dataset = client.set_dataset("s3-" + name, type="s3")
        dataset_version = dataset.create_version(s3_bucket)

        assert len(dataset_version.dataset_version_info.dataset_part_infos) >= 1


class TestFilesystemClientFunctions:
    def test_filesystem_dataset_creation(self, client):
        name = utils.gen_str()
        dataset = client.set_dataset("fs-" + name, type="local")
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.PATH

    def test_filesystem_dataset_version_creation(self, client):
        dir_name, _ = self.create_dir_with_files(num_files=3)
        name = utils.gen_str()
        dataset = client.set_dataset("fs-" + name, type="local")
        dataset_version = dataset.create_version(dir_name)

        assert len(dataset_version.dataset_version_info.dataset_part_infos) == 3
        shutil.rmtree(dir_name)

    def create_dir_with_files(self, num_files=10):
        dir_name = 'FSD:' + str(time.time())
        file_names = []
        os.mkdir(dir_name)
        for num_file in range(num_files):
            file_name = str(num_file) + ".txt"
            f = open(dir_name + "/" + file_name, 'w')
            f.write('123456\n')
            file_names.append(file_name)
        return dir_name, file_names


class TestBigQueryDatasetVersionInfo:
    def test_big_query_dataset(self, client):
        name = utils.gen_str()
        dataset = client.set_dataset("bq-" + name, type="big query")
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.QUERY

    def test_big_query_dataset_version_creation(self, client, big_query_job):
        name = utils.gen_str()
        dataset = client.set_dataset("bq-" + name, type="big query")
        dataset_version = dataset.create_version(job_id=big_query_job[0], location=big_query_job[1])

        assert dataset_version.dataset_version_info.query == big_query_job[2]

class TestRDBMSDatasetVersionInfo:
    def test_rdbms_dataset(self, client):
        name = utils.gen_str()
        dataset = client.set_dataset("pg-" + name, type="postgres")
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.QUERY

    def test_rdbms_version_creation(self, client):
        name = utils.gen_str()
        dataset = client.set_dataset("pg-" + name, type="postgres")
        dataset_version = dataset.create_version(query="SELECT * FROM ner-table",
                                                 db_connection_str="localhost:6543",
                                                 num_records=100)

        assert dataset_version.dataset_version_info.query == "SELECT * FROM ner-table"
        assert dataset_version.dataset_version_info.data_source_uri == "localhost:6543"
        assert dataset_version.dataset_version_info.num_records == 100

class TestLogDatasetVersion:
    def test_log_dataset_version(self, client, experiment_run, s3_bucket):
        name = utils.gen_str()
        dataset = client.set_dataset("s3-" + name, type="s3")
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.PATH

        dataset_version = dataset.create_version(s3_bucket)
        experiment_run.log_dataset_version('train', dataset_version)

        # _, linked_id = experiment_run.get_dataset('train')
        # assert linked_id == dataset_version.id
