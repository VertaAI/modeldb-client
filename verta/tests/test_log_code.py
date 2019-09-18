import six

import os
import zipfile

import verta

import pytest
import utils


# check if in git repo
try:
    verta._utils.get_git_repo_root_dir()
except OSError:
    IN_GIT_REPO = False
else:
    IN_GIT_REPO = True


class TestLogGit:
    @pytest.mark.skipif(not IN_GIT_REPO, reason="not in git repo")
    def test_log_git(self, client):
        """git mode succeeds inside git repo"""
        for mdb_entity in (client.set_project(), client.set_experiment(), client.set_experiment_run()):
            mdb_entity._conf.use_git = True

            mdb_entity.log_code()
            code_version = mdb_entity.get_code()

            assert isinstance(code_version, dict)
            assert 'filepaths' in code_version
            assert len(code_version['filepaths']) == 1
            assert __file__.endswith(code_version['filepaths'][0])

    def test_log_git_failure(self, client):
        """git mode fails outside git repo"""
        for mdb_entity in (client.set_project(), client.set_experiment(), client.set_experiment_run()):
            mdb_entity._conf.use_git = True

            with utils.chdir('/'):  # assuming the tester's root isn't a git repo
                with pytest.raises(OSError):
                    mdb_entity.log_code()

    @pytest.mark.skipif(not IN_GIT_REPO, reason="not in git repo")
    def test_log_git_provide_path(self, client):
        for mdb_entity in (client.set_project(), client.set_experiment(), client.set_experiment_run()):
            mdb_entity._conf.use_git = True

            mdb_entity.log_code(exec_path="conftest.py")
            code_version = mdb_entity.get_code()

            assert isinstance(code_version, dict)
            assert 'filepaths' in code_version
            assert len(code_version['filepaths']) == 1
            assert os.path.abspath("conftest.py").endswith(code_version['filepaths'][0])


class TestLogSource:
    def test_log_script(self, client):
        """source mode succeeds for Python script"""
        for mdb_entity in (client.set_project(), client.set_experiment(), client.set_experiment_run()):
            mdb_entity._conf.use_git = False

            mdb_entity.log_code()
            zipf = mdb_entity.get_code()

            assert isinstance(zipf, zipfile.ZipFile)
            assert len(zipf.namelist()) == 1
            assert __file__.endswith(zipf.namelist()[0])
            assert open(__file__, 'rb').read() == zipf.open(zipf.infolist()[0]).read()

    def test_log_script_provide_path(self, client):
        for mdb_entity in (client.set_project(), client.set_experiment(), client.set_experiment_run()):
            mdb_entity._conf.use_git = False

            mdb_entity.log_code("conftest.py")
            zipf = mdb_entity.get_code()

            assert isinstance(zipf, zipfile.ZipFile)
            assert len(zipf.namelist()) == 1
            assert os.path.abspath("conftest.py").endswith(zipf.namelist()[0])
            assert open("conftest.py", 'rb').read() == zipf.open(zipf.infolist()[0]).read()


class TestConflict:
    @pytest.mark.skipif(not IN_GIT_REPO, reason="not in git repo")
    def test_log_two_git(self, client):
        client._conf.use_git = True

        for mdb_entity in (client.set_project(), client.set_experiment(), client.set_experiment_run()):
            mdb_entity.log_code()

            with pytest.raises(ValueError):
                mdb_entity.log_code()

    def test_log_two_source(self, client):
        client._conf.use_git = False

        for mdb_entity in (client.set_project(), client.set_experiment(), client.set_experiment_run()):
            mdb_entity.log_code()

            with pytest.raises(ValueError):
                mdb_entity.log_code()

    @pytest.mark.skipif(not IN_GIT_REPO, reason="not in git repo")
    def test_log_git_then_source(self, client):
        for mdb_entity in (client.set_project(), client.set_experiment(), client.set_experiment_run()):
            mdb_entity._conf.use_git = True
            mdb_entity.log_code()

            mdb_entity._conf.use_git = False
            with pytest.raises(ValueError):
                mdb_entity.log_code()

    @pytest.mark.skipif(not IN_GIT_REPO, reason="not in git repo")
    def test_log_source_then_git(self, client):
        for mdb_entity in (client.set_project(), client.set_experiment(), client.set_experiment_run()):
            mdb_entity._conf.use_git = False
            mdb_entity.log_code()

            mdb_entity._conf.use_git = True
            with pytest.raises(ValueError):
                mdb_entity.log_code()
