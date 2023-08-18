# Theia picker

<p align="center">
<img src="forklift.png" width="320px">
</p>

## Installation

```commandline
pip install theia-picker
```

## Credentials

The credentials must be stored in a JSON file. It should look like this:

*credentials.json*
```json
{
  "ident": "username1234",
  "pass": "thisisnotmypassword"
}
```

Or, you can also write the credentials in your python code inside a `dict`.

## Searching products

The `TheiaCatalog` class is the top level API to access the products. It uses 
the credentials stored in the *credentials.json* file.

```python
from theia_picker import TheiaCatalog

theia = TheiaCatalog("credentials.json")
features = theia.search(
    start_date="01/01/2022",
    end_date="01/01/2023",
    bbox=[4.01, 42.99, 4.9, 44.05],
    level="LEVEL2A"
)
```

The `end_date` is optional. If not provided, the products are searched only for 
`start_date`. The `tile_name` parameter enables to search for products in a 
specific tile.

Here is another example of search without `end_date` and `bbox`, using 
`tile_name`:

```python
features = theia.search(
    start_date="01/01/2022",
    tile_name="T31TEJ",
    level="LEVEL2A"
)
```

The `search()` returns a `list` of `Feature` instances. For each `Feature`, one 
can retrieve its information.

```python
for f in features:
    print(f.properties.product_identifier)
```

And the most interesting thing is how we can download files from one `Feature`.

## Downloading products

Theia-picker enable to download **archives** or **individual files** from the 
remote archive. When individual files are downloaded, only the bytes relative 
to the compressed file in the remote archive are downloaded. Then they are 
decompressed and written as the file. This is particularly interesting when a 
few files are needed. No need to download the entire archive!

### Archives

The following will download the entire archive.

```python
f.download_archive(download_dir="/tmp")
```

When the archive already exist in the download directory, the md5sum is 
computed and compared with the one in the catalog, in order to determine if it 
has to be downloaded again. If the file is already downloaded and is complete 
according to the md5sum, its download is skipped. 

### Individual files

The **list of files** in the remote archive can be retrieved:

```python
files = f.list_files_in_archive()
```

Filenames are returned from `list_files_in_archive()` as a `list` of `str`.

Then one can **download a specific file** using `download_single_file()`:

```python
f.download_single_file(filename="S.../MASKS/...EDG_R1.tif", download_dir="/tmp")
```

Here the theia token is renewed automatically when a request fails. If you 
prefer, you can force the token renewal prior to download the file with 
`renew_token=True`.

Finally, you can **download multiple files** matching a set of patterns.
The following example show how to download only files containing *FRE_B4.tif* 
or *FRE_B8.tif* expressions.

```python
f.download_files(matching=["FRE_B4.tif", "FRE_B8.tif"], download_dir="/tmp")
```
Theia-picker downloads only the part of the remote archive containing the 
compressed bytes of files, and decompresses the data. The CRC32 checksum is 
computed to check that the files are correctly downloaded. If not, the download 
is retried. When the destination file already exists, the CRC32 is computed and 
compared with the CRC32 of the file in the remote archive. If both checksums 
match, the download is skipped.
