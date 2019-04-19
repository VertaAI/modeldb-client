# Verta: Model Lifecycle Management

Thanks for stopping by, and for taking your first step towards a healthier, more sustainable model lifecycle!

Come see [our user guide and documentation](https://verta.readthedocs.io/en/docs/index.html) to get started.

---

# Contributing
1. from the root directory of the repository, run these commands:
    1. `git submodule init`
    1. `git submodule update`
    1. `cd verta/`
    1. `./fix-import.sh`
        1. if you run into an error, see [issue #23](https://github.com/VertaAI/modeldb-client/issues/23)
    1. `pip3 install -e .`
        1. this means you don't have to rerun `pip3 install` whenever you make changes
    1. (optional) `pip3 install -r requirements.txt`
        1. this installs packages for PyPI publication, unit testing, and documentation
1. use ModelDBClient
1. tackle issues
