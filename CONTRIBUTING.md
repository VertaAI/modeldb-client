## Package Publication

1. Run the test suite and see that they pass to an acceptable degree.
2. Update `__version__` in [`__about__.py`](https://github.com/VertaAI/modeldb-client/blob/development/verta/verta/__about__.py) with a new version number.
   - We're not stable yet, so we're not strictly adhering to [Semantic Versioning](https://semver.org/).
   - Increment the minor version for backwards-incompatible changes or a major set of new features.
   - Increment the patch version for minor new features and bug fixes.
3. Update [changelog.rst](https://github.com/VertaAI/modeldb-client/blob/development/verta/docs/reference/changelog.rst).
   - The categories of changes are as follows, in this order, each one being optional:
     1. Backwards Incompatibilities — features that will cause errors if a user runs old code with this new version
     2. Deprecations — features that will be removed in a future version
     3. New Features
     4. Bug Fixes
     5. Internal Changes — features that do not change the way users interact with the package
4. Add the updated `__about__.py` and `changelog.rst` in a single commit using the message `"Increment {major,minor,patch} version"`.
5. Tag the commit with the version number using e.g. `git tag -a v0.0.0 -m ''`, with the appropriate version number.
6. Push the commit and tag using `git push --follow-tags`.

### Publish to PyPI

1. `cd verta/` from the repository root.
2. `./upload.sh`
3. Enter your PyPI username and password when prompted.
4. Verify that the package number has been updated [on PyPI](https://pypi.org/project/verta/).
5. The new version will be `pip install`able shortly.

### Publish to conda-forge

1. Some time after PyPI publication, a conda-forge bot will automatically submit [a Pull Request to the `verta` feedstock repository](https://github.com/conda-forge/verta-feedstock/pulls).
2. Make any necessary additional changes to `recipe/meta.yaml`.
   - The only changes we might need to make are in our package's listed dependencies, since the conda-forge bot simply copies it from the previous version.
   - Other organizations would need to make additional changes if e.g. they have C dependencies, but we do not so there is no need to worry.
   - Verify the checksum if you'd like.
3. Wait for the build tests in the Pull Request to succeed.
4. Merge the Pull Request.
5. Verify that the package number has been updated [on Anaconda Cloud](https://anaconda.org/conda-forge/verta).
6. The new version will be `conda install -c conda-forge`able after an hour or so.
