# -*- coding: utf-8 -*-
"""
This module handles the download of Theia products.

"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import struct
import time
import uuid
import zlib
from contextlib import nullcontext
from typing import Any, Dict, List, Union, Callable
from urllib.parse import urlencode
from pydantic import BaseModel, Field, validator, Extra  # pylint: disable = no-name-in-module, line-too-long  # noqa: E501
from requests.adapters import HTTPAdapter, Retry
from tqdm.autonotebook import tqdm
import requests

from .utils import log

REQUESTS_TIMEOUT = 10
MAX_NB_RETRIES = 5
SECONDS_BTW_RETRIES = 2


def retry(
        err_cls: Any,
        action: str,
        times: int = MAX_NB_RETRIES,
        sleep_duration: int = SECONDS_BTW_RETRIES
) -> Callable:
    """
    Wrapper to retry multiple times something.
    On the second try, the `renew_token` kwargs is set to `True`.

    Args:
        err_cls: Exception(s) to catch
        action: name of the action
        times: number of retries
        sleep_duration: sleep duration after each fail attempt

    Returns:
        decorator

    """

    def retry_decorator(function: Callable) -> Callable:
        """
        Decorator for function retry.

        Args:
            function: function to retry

        Returns:
            wrapper

        """

        def wrapper(*args, **kwargs):
            """
            Function wrapper.

            Args:
                *args: function args
                **kwargs: function kwargs

            Returns:
                function return value

            """
            for retry_nb in range(times):
                try:
                    extra_opts = {} if retry_nb == 0 else {"renew_token": True}
                    return function(*args, **{**kwargs, **extra_opts})
                except err_cls as err:
                    log.warning("Failed to %s: %s", action, err)
                    if retry_nb == times - 1:
                        raise
                log.warning(
                    "%s attempts left. Retry in %s seconds...",
                    times - retry_nb - 1, sleep_duration
                )
                time.sleep(sleep_duration)
            return None  # should never happen

        return wrapper

    return retry_decorator


def compute_md5(filename: str) -> str:
    """
    Compute md5sum of the contents of the given filename.

    Args:
        filename: file name

    Returns:
        MD5 checksum

    """
    hash_md5 = hashlib.md5()
    with open(filename, "rb") as file:
        for chunk in iter(lambda: file.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def compute_crc32(filename: str) -> str:
    """
    Compute the CRC-32 checksum of the contents of the given filename.

    Args:
        filename: file name

    Returns:
        CRC32 checksum

    """
    with open(filename, "rb") as file:
        checksum = 0
        while chunk := file.read(65536):
            checksum = zlib.crc32(chunk, checksum)
        return checksum


class RemoteZipCreationException(Exception):
    """
    RemoteZip instance creation exception

    """


class RemoteZipDownloadException(Exception):
    """
    RemoteZip download exception

    """


class ArchiveDownloadException(Exception):
    """
    Archive download exception.

    """


class InvalidToken(Exception):
    """
    Theia token is invalid.

    """


class RequestsManager:
    """
    Class to handle requests.

    """

    auth_endpoint = "https://theia.cnes.fr/atdistrib/services/authenticate/"

    def __init__(self, credentials: Dict[str, str]):
        """
        Initializer.

        Args:
            credentials: credentials {"ident": "...", "pass": "..."}

        """
        self.credentials = credentials

        self.sess = requests.Session()
        retries = Retry(
            total=MAX_NB_RETRIES,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504]
        )
        self.sess.mount('https://', HTTPAdapter(max_retries=retries))

        self.authorization_headers = {}
        self.renew_authorization_headers()

    def renew_authorization_headers(self):
        """
        Renew the authentication header.

        """
        log.info("Renew token")
        response = self.sess.post(
            self.auth_endpoint,
            data=self.credentials,
            timeout=REQUESTS_TIMEOUT
        )
        txt = response.text
        log.debug("Response from authentication server: %s", txt)
        if response.status_code != 200:
            raise ConnectionError(
                f"Unable to ask for a token: {txt}, "
                "maybe check your internet connection?"
            )
        try:
            uuid.UUID(txt)
        except ValueError as err:
            raise InvalidToken(
                "Unable to get a valid token. "
                "Maybe check your credentials?"
            ) from err

        self.authorization_headers = {
            "Authorization": f"Bearer {txt}",
            "Content-Type": "application/json"
        }

    def get(
            self,
            url: str,
            headers: Dict[str, str] = None,
    ) -> Any:
        """
        HTTP GET with authentication headers.
        When the requests.get() is failing due to authentication error, it is
        retried `MAX_NB_RETRIES` times.

        Args:
            url: requested url
            headers: HTTP headers

        Returns:
            requests response

        """
        if not headers:
            headers = {}
        for attempt in range(MAX_NB_RETRIES):
            response = self.sess.get(
                url,
                headers={**headers, **self.authorization_headers},
                stream=True,
                timeout=REQUESTS_TIMEOUT
            )
            if response.status_code in (200, 206):
                return response
            if attempt == MAX_NB_RETRIES - 1:
                response.raise_for_status()
            if response.reason == "Forbidden":
                log.info("Renewing Theia token")
                self.renew_authorization_headers()
            if attempt > 0:
                log.warning("Attempt %s over %s", attempt + 1, MAX_NB_RETRIES)
            log.debug("Waiting %s seconds", SECONDS_BTW_RETRIES)
            time.sleep(SECONDS_BTW_RETRIES)
        return None  # Should never be reached


class RemoteZip:
    """
    Class to handle remote archives.
    """

    def __init__(  # pylint: disable = too-many-locals
            self,
            url: str,
            requests_mgr: RequestsManager
    ):
        """
        Initializer.

        Args:
            url: url of the remote archive
            requests_mgr: requests manager
        """
        self.url = url
        self.requests_mgr = requests_mgr

        # Get end of central directory
        response = self.requests_mgr.get(self.url)
        tot_bytes = int(response.headers.get('content-length', 0))
        eocd_buf_bytes = 100  # EOCD lookup buffer
        buf = self._get_range(
            start=tot_bytes - eocd_buf_bytes,
            length=eocd_buf_bytes
        )
        cd_loc_in_buf = buf.find(bytearray(b'\x50\x4b\x05\x06'))
        if cd_loc_in_buf < 0:
            raise RemoteZipCreationException("CD not found in remote archive")

        _, _, _, _, total_num_records, cd_size, cd_offset, _ = \
            struct.unpack_from("<IHHHHIIH", buf, offset=cd_loc_in_buf)
        log.debug(
            "Total number of records in remote archive: %s",
            total_num_records
        )

        # Get compressed files information
        cd_bytes = self._get_range(start=cd_offset, length=cd_size)
        fmt_cd = '<IHHHHHHIIIHHHHHII'
        cd_hdr_size = struct.calcsize(fmt_cd)
        cur_addr = 0
        self.infos = {}
        zip64_fmt = {8: "<Q", 16: "<QQ", 24: "<QQQ", 28: "<QQQI"}
        zip64_ones = 0xffffffff
        while cur_addr < cd_size:
            _, _, _, flags, method, _, _, crc, complen, uncomplen, fnlen, \
                extralen, commentlen, _, _, _, ofs = \
                struct.unpack_from(fmt_cd, cd_bytes, offset=cur_addr)
            cur_addr += cd_hdr_size
            filename = cd_bytes[cur_addr:cur_addr + fnlen].decode()
            cur_addr += fnlen
            extra = cd_bytes[cur_addr:cur_addr + extralen]
            cur_addr += extralen + commentlen

            # Deal with Zip64
            i = 0
            while i < extralen:
                fieldid, fieldsz = struct.unpack_from('<HH', extra, i)
                i += 4
                if fieldid == 0x0001:  # ZIP64
                    log.debug("Archive is Zip64")
                    fmt = zip64_fmt[fieldsz]
                    vals = list(struct.unpack_from(fmt, extra, i))
                    if uncomplen == zip64_ones:
                        uncomplen = vals.pop(0)
                    if complen == zip64_ones:
                        complen = vals.pop(0)
                    if ofs == zip64_ones:
                        ofs = vals.pop(0)
                i += fieldsz

            # Store compressed files information
            self.infos[filename] = {
                "method": method,
                "flags": flags,
                "crc": crc,
                "header_offset": ofs,
                "file_size": uncomplen,
                "compress_size": complen,
            }
            assert method == 8
            log.debug("File %s info: %s", filename, self.infos[filename])

    def _get_range(  # pylint: disable = too-many-arguments
            self,
            start: int,
            length: int,
            block_size: int = 1024 * 32,
            output_file: str = None,
            decomp: Any = None
    ) -> bytearray:
        """
        HTTP GET with custom-made byte-range
        (because Theia server byte-range support is real crap).

        Args:
            start: bytes start
            length: bytes length
            block_size: block size
            output_file: absolute path of output file. If `None`, the bytes are
                kept in memory and returned.
            decomp: decompressor. Default to zlib (Deflate) if `None`. Must
                have `decompress()`.

        Returns:
            Received bytes if `output_file` is `None`

        """
        decomp = zlib.decompressobj(-15) if not decomp else decomp

        log.debug("HTTP GET range start at %s, length %s", start, length)
        headers = {"Range": f"bytes={start}-"}
        resp = self.requests_mgr.get(self.url, headers=headers)

        if output_file:
            log.debug("Decompressing data in output file: %s", output_file)

        content = bytearray()
        n_bytes = 0
        with open(output_file, 'wb') if output_file else nullcontext() as file:
            if file:
                progress_bar = tqdm(total=length, unit='iB', unit_scale=True)
            for data in resp.iter_content(block_size):
                n_bytes += len(data)
                n_extra_bytes = n_bytes - length
                if n_extra_bytes > 0:
                    data = data[:-n_extra_bytes]
                if file:
                    decomp_data = decomp.decompress(data)
                    file.write(decomp_data)
                    progress_bar.update(len(data))
                else:
                    content.extend(data)
                if n_extra_bytes > 0:
                    # Avoid requests.exceptions.ChunkedEncodingError since
                    # Theia server does not send the correct amount of bytes
                    break
            if file:
                file.write(decomp.flush())
                progress_bar.close()

        log.debug("Returning %s bytes", len(content))
        return content

    @property
    def files_list(self) -> List[str]:
        """

        Returns: list of the files in the remote archive

        """
        return list(self.infos.keys())

    def download_single_file(  # pylint: disable = too-many-locals
            self,
            filename: str,
            output_dir: str,
            renew_token: bool = False
    ):
        """
        Download a single file from the remote archive.

        If the destination file already exists in the download directory, the
        CRC32 checksum is computed and compared with the CRC32 of the
        compressed file in the remote archive. If they match, the download is
        skipped. After the download, the CRC32 checksum is computed and
        compared with the CRC32 of the compressed file in the remote archive.
        If they don't match, the download is retried.

        Args:
            filename: file path in the remote archive
            output_dir: output directory
            renew_token: can be used to force the token renewal

        """
        if filename not in self.infos:
            raise KeyError(
                f"File {filename} not in available. "
                f"Available files: {self.infos.keys()}"
            )

        info = self.infos[filename]
        log.debug("File %s info: %s", filename, info)
        fmt_localhdr = '<IHHHHHIIIHH'
        sizeof_localhdr = struct.calcsize(fmt_localhdr)
        if renew_token:
            self.requests_mgr.renew_authorization_headers()
        resp = self._get_range(
            start=info["header_offset"],
            length=sizeof_localhdr
        )
        _, _, _, _, _, _, crc, size, _, fnlen, extralen = struct.unpack_from(
            fmt_localhdr,
            resp
        )
        log.debug("CRC32 (expected): %s", crc)
        output_file = os.path.join(output_dir, os.path.basename(filename))

        # Check if file already exist
        if os.path.isfile(output_file):
            crc_out = compute_crc32(output_file)
            log.debug("CRC32 (existing file): %s", crc_out)
            if crc_out == crc:
                log.info("File %s already downloaded. Skipping.", output_file)
                return

        start = info["header_offset"] + sizeof_localhdr + fnlen + extralen
        self._get_range(start=start, length=size, output_file=output_file)

        # Check that the file has been properly downloaded
        crc_out = compute_crc32(output_file)
        log.debug("CRC32 (downloaded): %s", crc_out)
        if crc != crc_out:
            raise RemoteZipDownloadException(
                f"Downloaded file {output_file} CRC32 is {crc_out} "
                f"and doesn't match expected one ({crc})"
            )


class Download(BaseModel):  # pylint: disable = too-few-public-methods
    """
    Download model
    """
    url: str = Field(alias="url")
    checksum: str = Field(alias="checksum")

    @validator('url', each_item=True)
    def make_url(cls, url: str) -> str:  # pylint: disable=no-self-argument
        """
        Model validator

        Args:
            url: old url

        Returns:
            transformed url

        """
        return url + "/?issuerId=theia"


class Services(BaseModel):  # pylint: disable = too-few-public-methods
    """
    Services model
    """
    download: Download = Field(alias="download")


class Properties(BaseModel):  # pylint: disable = too-few-public-methods
    """
    Properties model
    """
    collection: str = Field(alias="collection")
    product_identifier: str = Field(alias="productIdentifier")
    title: str = Field(alias="title")
    product_type: str = Field(alias="productType")
    acquisition_date: datetime.datetime = Field(alias="startDate")
    level: str = Field(alias="processingLevel")
    water_cover: int = Field(alias="waterCover")
    snow_cover: int = Field(alias="snowCover")
    cloud_cover: int = Field(alias="cloudCover")
    tile: str = Field(alias="location")
    services: Services = Field(alias="services")


class Feature(BaseModel, extra=Extra.allow):
    """
    Feature model
    Extended with custom functions to be helpful
    """

    _requests_mgr: RequestsManager
    _remote_zip: RemoteZip = None
    id: str = Field(alias="id")
    properties: Properties = Field(alias="properties")

    @retry(
        action="download remote archive",
        err_cls=ArchiveDownloadException,
    )
    def _download_file(
            self,
            out_file: str,
            renew_token: bool,
            checksum: str = None,
    ):
        """
        Download a file.

        Args:
            out_file: output file
            checksum: checksum
            renew_token: can be used to force the token renewal

        """
        if renew_token:
            self._requests_mgr.renew_authorization_headers()
        resp = self._requests_mgr.get(self.properties.services.download.url)
        try:
            tot_size_in_bytes = int(resp.headers.get('content-length', 0))
            block_size = 32 * 1024  # 32 Kb
            pbar = tqdm(total=tot_size_in_bytes, unit='iB', unit_scale=True)
            with open(out_file, 'wb') as file:
                for data in resp.iter_content(block_size):
                    pbar.update(len(data))
                    file.write(data)
            pbar.close()
        except requests.exceptions.RequestException as err:
            raise ArchiveDownloadException("Download has failed") from err

        if checksum:
            if checksum != compute_md5(out_file):
                raise ArchiveDownloadException(
                    "Downloaded archive is corrupted"
                )

    def download_archive(self, download_dir: str, renew_token: bool = True):
        """
        Download the entire archive.

        If the destination file already exists in the download directory, the
        MD5 checksum is computed and compared with the MD5 of the remote
        archive. If they match, the download is skipped. After the download,
        the MD5 checksum is computed and compared with the MD5 of the
        compressed file in the remote archive. If they don't match, the
        download is retried.

        Args:
            download_dir: download directory
            renew_token: force the token renewal prior to download

        """
        log.debug("Downloading archive in %s", download_dir)

        # create output directory
        Path(download_dir).mkdir(parents=True, exist_ok=True)

        properties = self.properties
        archive_fn = os.path.join(
            download_dir,
            properties.product_identifier + ".zip"
        )
        checksum = properties.services.download.checksum

        # check if file already exist
        if os.path.isfile(archive_fn):
            if checksum == compute_md5(archive_fn):
                log.info(
                    "Archive %s already downloaded. Skipping.", archive_fn
                )
                return

        self._download_file(
            out_file=archive_fn,
            checksum=checksum,
            renew_token=renew_token
        )

    @retry(
        err_cls=RemoteZipCreationException,
        action="grab remote archive information",
    )
    def _get_remote_zip(self, renew_token=False) -> RemoteZip:
        """
        Remote zip instance.

        """
        if renew_token:
            self._requests_mgr.renew_authorization_headers()
        if not self._remote_zip:
            self._remote_zip = RemoteZip(
                url=self.properties.services.download.url,
                requests_mgr=self._requests_mgr
            )
        return self._remote_zip

    def list_files_in_archive(self) -> List[str]:
        """
        Grab the list of files in the remote archive.

        Returns:
            List of files in the remote archive

        """
        return self._get_remote_zip().files_list

    @retry(
        action="download/extract single file from remote archive",
        err_cls=(RemoteZipDownloadException, struct.error)
    )
    def download_single_file(
            self,
            filename: str,
            download_dir: str,
            renew_token: bool = False
    ):
        """
        Download a single file from the remote archive.

        Args:
            filename: file path of the file to download/extract from the
                remote archive
            download_dir: download directory
            renew_token: can be used to force the token renewal

        """
        log.debug("Downloading file %s in %s", filename, download_dir)

        # create output directory
        output_dir = os.path.join(
            download_dir,
            os.path.dirname(filename)
        )
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Grab the remote_zip. No need to explicitly renew token here, since
        # it will be done only if needed (with the retry decorator).
        remote_zip = self._get_remote_zip()

        # Download the single file. Here we can force the token renewal
        # because since the download can take a while, it can make sense to
        # renew the token before.
        remote_zip.download_single_file(
            filename=filename,
            output_dir=output_dir,
            renew_token=renew_token
        )

    def download_files(
            self,
            download_dir: str,
            matching: List[str],
            renew_token: bool = False
    ):
        """
        Download multiple files from the remote archive.

        Args:
            download_dir: download directory
            matching: list of string to match filenames
            renew_token: force the token renewal prior to download each file

        """
        for filename in self.list_files_in_archive():
            if any(match in filename for match in matching):
                self.download_single_file(
                    filename=filename,
                    download_dir=download_dir,
                    renew_token=renew_token
                )


class TheiaCatalog:  # pylint: disable = too-few-public-methods
    """The TheiaCatalog class enables to download Theia products."""

    atdistrib_url = "https://theia.cnes.fr/atdistrib"

    def __init__(self, config_file_json: str, max_records: int = 500):
        """
        Args:
            config_file_json: JSON configuration file. Should look like this:

                ```json
                {
                    "ident": "username",
                    "pass": "xxxxxxx"
                }
                ```

            max_records: Maximum number of records

        """
        # Read THEIA credentials
        with open(config_file_json, encoding='UTF-8') as json_file:
            credentials = json.load(json_file)
            self._requests_mgr = RequestsManager(credentials=credentials)

        self.max_records = max_records

    def _query(self, dict_query: dict) -> List[Feature]:
        """
        Search products in THEIA catalog

        Args:
            dict_query: the search query

        Returns:
            features

        """
        log.debug("Performing search in Theia catalog...")
        log.debug("Query is %s", dict_query)
        url = f"{self.atdistrib_url}/resto2/api/collections/" \
              f"SENTINEL2/search.json?{urlencode(dict_query)}"
        search = requests.get(
            url,
            headers={"Accept": "application/json"},
            timeout=REQUESTS_TIMEOUT
        )
        if search.status_code != 200:
            raise ConnectionError(
                "Unable to search for products, "
                f"server returned: {search.text}"
            )

        features = search.json().get("features")
        log.debug("Got %s results", len(features))
        return [
            Feature(_requests_mgr=self._requests_mgr, **record)
            for record in features
        ]

    def search(  # pylint: disable = too-many-arguments
            self,
            start_date: Union[datetime.datetime, str],
            end_date: Union[datetime.datetime, str] = None,
            bbox: List[float] = None,
            level: str = None,
            tile_name: str = None,
    ) -> List[Feature]:
        """
        Search products in THEIA catalog.

        Args:
            start_date: start date. The following formats are accepted:
                '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y%m%d'
            end_date: end date. If not specified, the day after start_date is
                used. Same formats as start_date are accepted.
            bbox: bounding box [lonmin, latmin, lonmax, latmax]. Must be a
                list of 4 float values, e.g. [3.01, 43.2, 4.0, 45.0]
            level: product level, e.g. "LEVEL2A"
            tile_name: tile name, starting with "T", e.g. "T31TEJ"

        Returns:
            Features list

        """

        def get_date(value):
            if isinstance(value, datetime.datetime):
                return value
            formats = ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y%m%d')
            for fmt in formats:
                try:
                    return datetime.datetime.strptime(value, fmt)
                except ValueError:
                    pass
            raise ValueError(
                'No valid date format found. '
                f'Accepted formats are {formats}. Input was: {value}'
            )

        start_date = get_date(start_date)
        oneday = datetime.timedelta(days=1)
        end_date = get_date(end_date) if end_date else start_date + oneday

        dict_query = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "completionDate": end_date.strftime("%Y-%m-%d"),
            "maxRecords": self.max_records,
        }
        if level:
            dict_query["processingLevel"] = level
        if bbox:
            if len(bbox) != 4:
                raise ValueError("Bounding box must be a list of 4 values")
            dict_query["box"] = ",".join(str(coord) for coord in bbox)
        if tile_name:
            if not tile_name.startswith("T"):
                raise ValueError(
                    f"Tile name must start with \"T\" (got {tile_name})"
                )
            dict_query["location"] = tile_name

        return self._query(dict_query)
