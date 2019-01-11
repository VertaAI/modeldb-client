## Data
The `data/` subdirectory is about 33M in size. I decided to push the data files directly to git for the time being. If the subdirectory grows in size down the line, consider the following utilities for tracking large files in git:

- [`git-lfs`](https://git-lfs.github.com/) is developed by GitHub and seems relatively painfree.
  - files show up on GitHub.com as usual
  - locally, large files are represented by pointer files
  - files are stored on a separate server managed by GitHub
- [`git-annex`](https://git-annex.branchable.com/) is too complex for our usecase.
  - seems to be geared more towards file management than project management
