import json
import os
import tempfile

import theia_picker

username = os.environ["THEIA_IDENT"]
password = os.environ["THEIA_PASS"]

with tempfile.TemporaryDirectory() as output_dir:
    # Login
    cat = theia_picker.TheiaCatalog(
        credentials={"ident": username, "pass": password}
    )
    print("Login OK")

    # Search
    features = cat.search(
        start_date="2022-01-14",
        bbox=[4.9, 43.99, 5.0, 44.05],
        level="LEVEL2A"
    )
    assert len(features) == 1
    print("Search OK")

    # Download some files
    patterns = [".jpg", ".xml", "EDG_R2.tif", "FRE_B7.tif"]
    for feat in features:
        assert feat.properties.product_identifier == \
               "SENTINEL2A_20220114-103855-001_L2A_T31TFJ_D"
        files = feat.list_files_in_archive()
        assert len(files) == 527
        for file in files:
            if any(pattern in file for pattern in patterns):
                feat.download_single_file(
                    filename=file,
                    download_dir=output_dir
                )
                out_file = os.path.join(output_dir, file)
                assert os.path.isfile(out_file)
    print("Download single file OK")

    # Download files batch
    feats = cat.search(
        tile_name="T31TEJ", start_date="14/01/2021", level="LEVEL2A"
    )
    for f in feats:
        f.download_files(
            matching=["FRE_B4.tif", "FRE_B8.tif"], download_dir="/tmp"
        )
    print("Download multiple files OK")
