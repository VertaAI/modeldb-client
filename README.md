# Verta: Model Lifecycle Management

Thanks for stopping by, and for taking your first step towards a healthier, more sustainable model lifecycle!

Come see [our user guide and documentation](https://verta.readthedocs.io/en/master/index.html) to get started.

## `verta/`
This subdirectory contains the actual Python package.

### `verta/verta/`
This subdirectory contains all the source code for the package.

### `verta/tests/`
This subdirectory contains unit and integrartion test scripts.

### `verta/docs/`
This subdirectory contains documentation source files for hosting on ReadTheDocs.

### `verta/requirements.txt`
This requirements file lists packages for developing the Verta package.

### `verta/setup.py`
This script contains metadata for building and distributing the Verta package.

### `verta/upload.sh
This shell script builds and uploads the Verta package to PyPI.

## `workflows/`
This subdirectory contains example and demo Jupyter notebooks

## Contributing
1. from the root directory of the repository, run these commands:
    1. `git submodule init`
    1. `git submodule update`
    1. `cd verta/`
    1. `pip install -e .`
        1. this means you don't have to rerun `pip install` whenever you make changes
    1. (optional) `pip install -r requirements.txt`
        1. this installs packages for PyPI publication, unit testing, and documentation
1. use Client
1. tackle issues
