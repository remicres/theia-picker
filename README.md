# Theia picker

<p align="center">
<img src="doc/forklift.png" width="320px">
<br>
<a href="https://gitlab.irstea.fr/umr-tetis/theia-picker/-/releases">
<img src="https://gitlab.irstea.fr/umr-tetis/theia-picker/-/badges/release.svg">
</a>
<a href="https://gitlab.irstea.fr/umr-tetis/theia-picker/-/commits/main">
<img src="https://gitlab.irstea.fr/umr-tetis/theia-picker/badges/main/pipeline.svg">
</a>
<a href="LICENSE">
<img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg">
</a>
</p>

**Theia-picker** provides everything to **download efficiently** 
[theia products](https://www.theia-land.fr/en/products/).
In particular, it is able to **download selected files from the remote 
archive**, without the entire data (typically, a single spectral band of a 
Sentinel-2 product).

Read the **[documentation](https://umr-tetis.gitlab.irstea.page/theia-picker)** 
to know more.

## Quickstart

Install the package from pip:

```commandline
pip install theia-picker
```

Perform searches and downloads. 
Here is an example to download only spectral bands 4 and 8 of level-2a products:
```python
from theia_picker import TheiaCatalog

theia = TheiaCatalog("/path/to.credentials.json")
features = theia.search(...)
for ft in features:
    for fn in ft.list_files_in_archive():  
    ft.download_single_file(some_file, output_dir="...")
```

## Contact

remi cresson @ inrae
