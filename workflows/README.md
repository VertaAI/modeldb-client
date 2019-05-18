## Examples
The `examples/` subdirectory contains simple and complete example notebooks that anyone could run.
Toy datasets are downloaded through Python data science frameworks to demonstrate basic Verta
functionality.

## Demos
The `demos/` subdirectory contains more complex and specific example notebooks to demonstrate
particular capabilities of the end-to-env Verta platform. These usually load datasets from disk,
but it is **very important** to not track these data files with git and therefore they must be
managed locally.

## Data
The `data/` subdirectory is about 33M in size. I decided to push these data files directly to git early
on in the development process for convenience, and now they are grandfathered into our commit history.
