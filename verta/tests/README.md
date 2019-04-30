To install the packages needed for developing `verta`, run:

```
cd ..
pip install -r requirements.txt
cd tests
```

Note that on macOS, importing `matplotlib` can raise an error depending on how Python was installed.
Refer to [this StackOverflow post](https://stackoverflow.com/a/21789908/) for a solution.

---

To execute tests, run:

```
pytest
```

You can also run specific test scripts like so:

```
pytest test_entities.py
```

Pytest by default captures print statement outputs and only displays them when errors are encountered, but outputs can be unsuppressed:

```
pytest -s
```

---

The test configuration script attempts to read the following environment variables:

- `VERTA_HOST`
- `VERTA_PORT`
- `VERTA_EMAIL`
- `VERTA_DEV_KEY`
