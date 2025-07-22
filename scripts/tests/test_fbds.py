from unittest.mock import patch

import pytest

from scripts.fbds.fbds import FBDSDownloader


class DummyResponse:
    def __init__(self, content=b"", status_code=200):
        self.content = content
        self.status_code = status_code
        self._raise = False

    def raise_for_status(self):
        if self._raise:
            raise Exception("HTTP error")

    def iter_bytes(self):
        yield b"data"


@patch("scripts.fbds.fbds.requests.get")
def test_get_urls_success(mock_get):
    html = b'<a href="/file1.shp">file1</a><a href="/file2.dbf">file2</a>'
    mock_get.return_value = DummyResponse(content=html)
    downloader = FBDSDownloader()
    result = downloader._get_urls("http://test", {"shp", "dbf"})
    assert any("file1.shp" in url for url in result)
    assert any("file2.dbf" in url for url in result)


@patch("scripts.fbds.fbds.requests.get")
def test_get_urls_retry_on_error(mock_get):
    mock_get.side_effect = Exception("fail")
    downloader = FBDSDownloader()
    result = downloader._get_urls("http://fail", {"shp"})
    assert result == set()


@patch("scripts.fbds.fbds.FBDSDownloader._get_urls")
def test_get_file_urls_by_state_cat(mock_get_urls):
    # Simulate municipality URLs and file URLs
    mock_get_urls.side_effect = [
        {"http://base/mun1", "http://base/mun2"},  # municipality_urls
        {"http://base/mun1/USO"},  # mun_cat_url 1
        {"http://base/mun2/USO"},  # mun_cat_url 2
    ]
    downloader = FBDSDownloader()
    result = downloader._get_file_urls_by_state_cat("AC", {"USO"})
    assert isinstance(result, set)


@patch("scripts.fbds.fbds.httpx.stream")
def test_download_file_success(mock_stream, tmp_path):
    mock_stream.return_value.__enter__.return_value.iter_bytes.return_value = [
        b"abc"
    ]
    downloader = FBDSDownloader()
    url = "http://test/file.txt"
    downloader._download_file(url, tmp_path, create_subdirs=False)
    assert (tmp_path / "file.txt").exists()


@patch("scripts.fbds.fbds.httpx.stream")
def test_download_file_retry_on_error(mock_stream, tmp_path):
    mock_stream.side_effect = Exception("fail")
    downloader = FBDSDownloader()
    url = "http://test/file.txt"
    # Should not raise, just print error
    downloader._download_file(url, tmp_path, create_subdirs=False)


def test_download_main(tmp_path):
    with (
        patch.object(FBDSDownloader, "_download_file") as mock_download_file,
        patch.object(
            FBDSDownloader, "_get_file_urls_by_state_cat"
        ) as mock_get_urls,
    ):
        mock_get_urls.return_value = {
            "http://test/file1.shp",
            "http://test/file2.dbf",
        }
        downloader = FBDSDownloader()
        downloader.download(
            str(tmp_path),
            states=["AC"],
            categories=["USO"],
            create_subdirs=False,
        )
        assert mock_download_file.call_count == 2


@patch("scripts.fbds.fbds.FBDSDownloader._get_file_urls_by_state_cat")
def test_download_invalid_state(mock_get_urls):
    downloader = FBDSDownloader()
    with pytest.raises(ValueError):
        downloader.download(
            "/tmp", states=["ZZ"], categories=["USO"]
        )  # ZZ is not a valid state


@patch("scripts.fbds.fbds.FBDSDownloader._get_file_urls_by_state_cat")
def test_download_invalid_category(mock_get_urls):
    downloader = FBDSDownloader()
    with pytest.raises(ValueError):
        downloader.download("/tmp", states=["AC"], categories=["INVALID"])
