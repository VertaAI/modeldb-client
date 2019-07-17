import six

import numpy as np
import os
import pytest
import time
import utils
import shutil

from verta import Dataset, DatasetVersion, S3DatasetVersionInfo, FilesystemDatasetVersionInfo
from verta._protos.public.modeldb import DatasetService_pb2 as _DatasetService
from verta._protos.public.modeldb import DatasetVersionService_pb2 as _DatasetVersionService


if six.PY2: FileNotFoundError = IOError

class TestBaseDatasets:
    def test_creation_from_scratch(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf, name=name, 
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.PATH)
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.DatasetType.PATH
        assert dataset.id

    def test_creation_by_id(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf, name=name, 
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.PATH)
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.DatasetType.PATH
        assert dataset.id

        same_dataset = Dataset(client._conn, client._conf, 
            _dataset_id=dataset.id)
        assert dataset.id == same_dataset.id

class TestBaseDatasetVersions:
    def test_creation_from_scratch(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf, name=name, 
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.PATH)
        
        version = DatasetVersion(client._conn, client._conf, dataset_id=dataset.id,
            dataset_version_info = _DatasetVersionService.PathBasedDatasetInfo(),
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.PATH)
        assert version.dataset_type == _DatasetService.DatasetTypeEnum.DatasetType.PATH
        assert version.id

    def test_creation_by_id(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf, name=name, 
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.PATH)
        
        version = DatasetVersion(client._conn, client._conf, dataset_id=dataset.id, 
            dataset_version_info = _DatasetVersionService.PathBasedDatasetInfo(),
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.PATH)
        assert version.dataset_type == _DatasetService.DatasetTypeEnum.DatasetType.PATH
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
        dataset = Dataset(client._conn, client._conf, name=name, 
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.PATH)
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.DatasetType.PATH
        assert dataset.id

    def test_creation_by_id(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf, name=name, 
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.PATH)
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.DatasetType.PATH
        assert dataset.id

        same_dataset = Dataset(client._conn, client._conf, 
            _dataset_id=dataset.id)
        assert dataset.id == same_dataset.id

class TestPathBasedDatasetVersions:
    def test_creation_from_scratch(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf, name=name, 
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.PATH)

        version = DatasetVersion(client._conn, client._conf, dataset_id=dataset.id,
            dataset_version_info = _DatasetVersionService.PathBasedDatasetInfo(),
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.PATH)
        assert version.dataset_type == _DatasetService.DatasetTypeEnum.DatasetType.PATH
        assert version.id

    def test_creation_by_id(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf, name=name, 
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.PATH)

        version = DatasetVersion(client._conn, client._conf, dataset_id=dataset.id,
            dataset_version_info = _DatasetVersionService.PathBasedDatasetInfo(),
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.PATH)
        assert version.dataset_type == _DatasetService.DatasetTypeEnum.DatasetType.PATH
        assert version.id

        same_version = DatasetVersion(client._conn, client._conf, 
            _dataset_version_id=version.id)
        assert version.id == same_version.id

class TestQueryDatasets:
    def test_creation_from_scratch(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf, name=name, 
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.QUERY)
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.DatasetType.QUERY
        assert dataset.id

    def test_creation_by_id(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf, name=name, 
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.QUERY)
        assert dataset.dataset_type == _DatasetService.DatasetTypeEnum.DatasetType.QUERY
        assert dataset.id

        same_dataset = Dataset(client._conn, client._conf, 
            _dataset_id=dataset.id)
        assert dataset.id == same_dataset.id

class TestQueryDatasetVersions:
    def test_creation_from_scratch(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf, name=name, 
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.QUERY)

        version = DatasetVersion(client._conn, client._conf, dataset_id=dataset.id,
            dataset_version_info = _DatasetVersionService.QueryDatasetInfo(),
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.QUERY)
        assert version.dataset_type == _DatasetService.DatasetTypeEnum.DatasetType.QUERY
        assert version.id

    def test_creation_by_id(self, client):
        name = utils.gen_str()
        dataset = Dataset(client._conn, client._conf, name=name, 
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.QUERY)

        version = DatasetVersion(client._conn, client._conf, dataset_id=dataset.id,
            dataset_version_info = _DatasetVersionService.QueryDatasetInfo(),
            dataset_type=_DatasetService.DatasetTypeEnum.DatasetType.QUERY)
        assert version.dataset_type == _DatasetService.DatasetTypeEnum.DatasetType.QUERY
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
        assert s3dvi.size == 9950413

    def test_bucket(self, s3_bucket):
        s3dvi = S3DatasetVersionInfo(s3_bucket)
        assert len(s3dvi.dataset_part_infos) == 2
        assert s3dvi.size == 13221986

class TestQueryDatasetVersionInfo:
    def test_big_query_dataset(self):
        pass