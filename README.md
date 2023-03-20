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

**Theia-picker** enables to **download efficiently** 
[theia products](https://www.theia-land.fr/en/products/).
In particular, it can **download selected files from remote 
archives** (e.g. one specific spectral band).

## Quickstart

Installation:

```commandline
pip install theia-picker
```

Perform searches and downloads. Entire archives can be downloaded, or files can 
be retrieved individually, without downloading the whole archive contents:

```python
from theia_picker import TheiaCatalog

# Download bands 4 and 8 from a Sentinel-2 Level 2A product
cat = TheiaCatalog("credentials.json")
feats = cat.search(tile_name="T31TEJ", start_date="14/01/2021", level="LEVEL2A")
for f in feats:
    f.download_files(matching=["FRE_B4.tif", "FRE_B8.tif"], download_dir="/tmp")
```

Theia-picker computes checksums for archives (MD5) and individual files (CRC32) 
to ensure that they match the versions provided by the catalog and avoiding 
unnecessary requests. 
Read the **[documentation](https://umr-tetis.gitlab.irstea.page/theia-picker)** 
to know more.


## Contact

remi cresson @ inrae
