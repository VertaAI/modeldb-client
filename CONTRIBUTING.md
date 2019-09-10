## Developer Installation

From the root directory of the repository, run these commands:
1. `git submodule init`
1. `git submodule update`
1. `cd verta/`
1. `pip install -e .`
   1. This means you don't have to rerun `pip install` whenever you make changes.
1. `pip install -r requirements.txt`
   1. This installs packages relating to PyPI publication, unit testing, and documentation.

### Troubleshooting

If you receive an `EnvironmentError: [Errno 13]` regarding permissions during `pip install -e .`, consider these potential solutions:
- Append `--user` to the command: `pip install -e . --user`
- Use Python3 by using the command: `pip3 install -e .`

## Example and Demo Writing

### Jupyter Notebook Formatting

Before committing a Jupyter notebook we have to:
- remove code cell outputs to prevent merge conflicts later, since outputs may change from run to run
- preserve code cell execution numbers to enable easy reference in walkthroughs

This can be done automatically with a pre-save hook:
1. create a Jupyter config file using `jupyter notebook --generate-config`
1. open the resulting `~/.jupyter/jupyter_notebook_config.py` in a code editor
1. replace the line
   ```python
   #c.ContentsManager.pre_save_hook = None
   ```
   with
   ```python
   def number_cells(model, **kwargs):
       if model['type'] != 'notebook':
           return  # only run on notebooks
       if model['content']['nbformat'] != 4:
           return  # only run on nbformat v4
       code_cells = (cell
                     for cell in model['content']['cells']
                     if cell['cell_type'] == 'code')
       for i, cell in enumerate(code_cells, start=1):
           cell['outputs'] = []
           cell['execution_count'] = i
   c.ContentsManager.pre_save_hook = number_cells
   ```

## Package Publication

1. Run the test suite and see that they pass to an acceptable degree.
1. Update `__version__` in [`__about__.py`](https://github.com/VertaAI/modeldb-client/blob/development/verta/verta/__about__.py) with a new version number.
   - We're not stable yet, so we're not strictly adhering to [Semantic Versioning](https://semver.org/).
   - Increment the minor version for backwards-incompatible changes or a major set of new features.
   - Increment the patch version for minor new features and bug fixes.
1. Update [changelog.rst](https://github.com/VertaAI/modeldb-client/blob/development/verta/docs/reference/changelog.rst).
   - The categories of changes are as follows, in this order, each one being optional:
     1. Backwards Incompatibilities — features that will cause errors if a user runs old code with this new version
     1. Deprecations — features that will be removed in a future version
     1. New Features
     1. Bug Fixes
     1. Internal Changes — features that do not change the way users interact with the package
1. Add the updated `__about__.py` and `changelog.rst` in a single commit on `development` using the message `"Increment major|minor|patch version"`.
   - Since this is a release, the `master` branch should also be fast-forwarded to point at this commit.
1. Tag the commit with the version number using e.g. `git tag -a v0.0.0 -m ''`, with the appropriate version number.
1. Push the commit and tag using `git push --follow-tags`.

### Publish to PyPI

1. `cd verta/` from the repository root.
1. `./upload.sh`
1. Enter your PyPI username and password when prompted.
1. Verify that the package number has been updated [on PyPI](https://pypi.org/project/verta/).
1. The new version will be `pip install`able shortly.

### Publish to conda-forge

1. Some time after PyPI publication, a conda-forge bot will automatically submit [a Pull Request to the `verta` feedstock repository](https://github.com/conda-forge/verta-feedstock/pulls).
1. Make any necessary additional changes to `recipe/meta.yaml`.
   - The only changes we might need to make are in our package's listed dependencies, since the conda-forge bot simply copies it from the previous version.
   - Other organizations would need to make additional changes if e.g. they have C dependencies, but we do not so there is no need to worry.
   - Verify the checksum if you'd like.
1. Wait for the build tests in the Pull Request to succeed.
1. Merge the Pull Request.
1. Verify that the package number has been updated [on Anaconda Cloud](https://anaconda.org/conda-forge/verta).
1. The new version will be `conda install -c conda-forge`able after an hour or so.
