import json
import os
import tempfile

import theia_picker

username = os.environ["THEIA_IDENT"]
password = os.environ["THEIA_PASS"]

with tempfile.NamedTemporaryFile("w+") as credentials_file, \
        tempfile.TemporaryDirectory() as output_dir:
    # Save credentials to JSON file
    data = {"ident": username, "pass": password}
    json.dump(data, credentials_file)
    credentials_file.flush()

    # Login
    cat = theia_picker.TheiaCatalog(credentials_file.name)
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
                    output_dir=output_dir
                )
                out_file = os.path.join(output_dir, os.path.basename(file))
                assert os.path.isfile(out_file)
    print("Download single file OK")
