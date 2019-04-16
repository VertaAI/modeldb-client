To install the packages needed for developing `verta`, run:

```
cd ..
pip install -r requirements.txt
cd tests
```

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

- `MODELDB_HOST`
- `MODELDB_PORT`
- `MODELDB_EMAIL`
- `MODELDB_DEV_KEY`