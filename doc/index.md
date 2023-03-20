# Theia picker

<p align="center">
<img src="forklift.png" width="320px">
</p>

## Installation

```commandline
pip install theia-picker
```

## Quickstart

``` py
from theia_picker import TheiaCatalog

theia = TheiaCatalog("/path/to.credentials.json")
features = theia.search(...)
for f in features:
    # download the entire archive
    f.download_archive(output_dir="...")
    # or... download only the file you want
    files = f.list_files_in_archive()
    some_file = files[0]  # pick one file name
    f.download_single_file(some_file, output_dir="...")
```
