#!/usr/bin/env python3
"""
This application enables to search and download Sentinel-2 images.

# Search

Products can be searched by date, bbox, tile name, and level.

```commandLine
theia-picker-cli
  --theia_cfg credentials.json
  --start_date 01/02/2023
  --tile T31TEJ
```

Here **tile** is used to search a particular tile name, but a bounding box
could also have been provided.

When the **end_date** is not provided, the day after **start_date** is used
instead. This allows to quickly search products acquired at **start_date**.
Of course **end_date** can be provided to specify a time range:

```commandLine
theia-picker-cli
  --theia_cfg credentials.json
  --start_date 01/02/2023
  --end_date 01/03/2023
  --tile T31TEJ
```

# Remote archives content

To show the content of the remote archive for each product found, just append
the **info** parameter to the CLI:

```commandLine
theia-picker-cli ... --info
```

# Download

For each product found from the search, the following can be downloaded:

- The entire archive: just set **download_dir** to the directory where you
  want to download the products archives. If the destination file already
  exist in the download directory, the md5 checksum is computed to check if
  the file is complete. If yes, the download is skipped. Else, the destination
  file is overwritten.

```commandLine
theia-picker-cli
  --theia_cfg credentials.json
  --start_date 01/02/2023
  --tile T31TEJ
  --download_dir /tmp
```

- A selection of files that are inside the remote archive, without downloading
  the whole archive. For this, you have to set the **download_dir** and the
  **download_files_patterns**. This latter is a list of patterns separated
  with space (e.g. `FRE_B4.tif FRE_B5 QL.jpg .xml`). When a file in the remote
  archive matches one of the patterns, it is downloaded and extracted in the
  download directory. If the destination file already exist in the download
  directory, the CRC32 checksum is computed to check if the file is complete.
  If yes, the download is skipped. Else, the destination file is overwritten.

```commandLine
theia-picker-cli
  --theia_cfg credentials.json
  --start_date 01/02/2023
  --tile T31TEJ
  --download_dir /tmp
  --download_files_patterns FRE_B4.tif FRE_B5 QL.jpg .xml
```

"""
import argparse

from theia_picker import TheiaCatalog
from theia_picker.utils import log


def main():
    """
    Main function

    """
    # Arguments
    parser = argparse.ArgumentParser(
        description="Theia picker command line interface"
    )
    parser.add_argument(
        "--theia_cfg",
        required=True,
        help="JSON file for the credentials "
             "{\"ident\": \"...\", \"pass\": \"...\")")
    parser.add_argument(
        "--download_dir",
        help="Local directory to download files"
    )
    parser.add_argument(
        "--download_files_patterns",
        type=str,
        nargs='+',
        default=[],
        help="Download only files matching one of the provided "
             "patterns from the remote archive"
    )
    parser.add_argument(
        "--bbox",
        type=float,
        nargs='+',
        default=[],
        help="4 values of the bounding box in WGS84 CRS: "
             "{lonmin}, {latmin}, {lonmax}, {latmax}"
    )
    parser.add_argument(
        "--start_date",
        type=str,
        required=True,
        help="Start date")

    parser.add_argument(
        "--end_date",
        type=str,
        help="Completion date. "
             "If not provided, the day after start_date is used."
    )
    parser.add_argument(
        "--tile",
        type=str,
        help="Tile name, starting with \"T\" (e.g. T31TEJ)"
    )
    parser.add_argument(
        "--level",
        type=str,
        default="LEVEL2A",
        help="Product level (e.g. LEVEL2A, LEVEL3A)"
    )
    parser.add_argument(
        '--info',
        dest='info',
        action='store_true',
        help="Show files in the remote archive"
    )
    parser.set_defaults(info=False)
    params = parser.parse_args()

    log.info("Using credentials from %s", params.theia_cfg)
    catalog = TheiaCatalog(params.theia_cfg)
    log.info("Searching...")
    features = catalog.search(
        start_date=params.start_date,
        end_date=params.end_date,
        tile_name=params.tile,
        bbox=params.bbox,
        level=params.level
    )
    n_feats = len(features)
    log.info("Got %s result(s)", n_feats)
    for i, feat in enumerate(features):
        log.info(
            "Result %s/%s: %s", i + 1, n_feats,
            feat.properties.product_identifier
        )
        if params.info or \
                params.download_dir and params.download_files_patterns:
            files = feat.list_files_in_archive()
            if params.info:
                print(f"{len(files)} files in archive:")
                for filename in files:
                    print(f"\t{filename}")
        if params.download_dir:
            if params.download_files_patterns:
                log.info(
                    "Downloading files with patterns %s",
                    params.download_files_patterns
                )
                to_download = [
                    filename
                    for filename in files
                    for pattern in params.download_files_patterns
                    if pattern in filename
                ]
                for filename in to_download:
                    log.info("Downloading file %s", filename)
                    feat.download_single_file(
                        filename=filename,
                        download_dir=params.download_dir
                    )
            else:
                log.info("Downloading the whole archive")
                feat.download_archive(download_dir=params.download_dir)
