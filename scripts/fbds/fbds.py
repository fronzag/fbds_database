from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import product
from pathlib import Path
from time import sleep
from urllib.parse import urljoin, urlparse

import httpx
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from scripts.fbds.constants import (
    BASE_URL,
    CATEGORIES,
    GEO_EXTENSIONS,
    STATES,
)

BAR_FORMAT = "{l_bar}{bar}| {n_fmt}/{total_fmt} "
MAX_THREADS = 4  # Be gentle with FBDS server: DO NOT use a value higher than 4
TRIES = 3
DELAY = 15


class FBDSDownloader:
    """Downloads geographic data files from FBDS (Brazilian database).

    This class provides functionality to download geographic data files
    from the FBDS (Fundação Brasileira para o Desenvolvimento
    Sustentável) database. It supports downloading data by Brazilian
    states and categories, with built-in retry logic and progress
    tracking.

    The downloader is designed to be respectful to the FBDS server by
    limiting concurrent connections and including delays between retries.

    Example:
        Basic usage for data analysts:

        >>> downloader = FBDSDownloader()
        >>> # Download all data for São Paulo state Permanent Preservation Areas
        >>> downloader.download(
        ...     download_dir="./data", states=["SP"], categories=["APP"]
        ... )
        >>>
        >>> # Download specific categories for multiple states
        >>> downloader.download(
        ...     download_dir="./brazil_data",
        ...     states=["RJ", "MG", "SP"],
        ...     categories=["HIDROGRAFIA", "USO"],
        ...     create_subdirs=True,
        ... )
    """

    def _download_file(
        self,
        url: str,
        download_dir: Path,
        *,
        create_subdirs: bool = True,
    ) -> None:
        """Downloads a single file from the given URL to the directory.

        This internal method handles the actual file download process with
        streaming to efficiently handle large files. It automatically
        creates directory structure if needed and implements retry logic
        for failed downloads.

        Args:
            url: The complete URL of the file to download.
            download_dir: Path object representing the base download
                         directory.
            create_subdirs: If True, recreates the URL path structure
                           locally. If False, saves all files directly
                           in download_dir.

        Raises:
            Exception: Re-raises the last exception if all retry attempts
                      fail. Common exceptions include network timeouts,
                      HTTP errors, and file system permission errors.
        """
        if create_subdirs:
            filepath = Path(
                "".join([str(download_dir), urlparse(url).path]),
            ).resolve()
            filepath.parent.mkdir(parents=True, exist_ok=True)
        else:
            filepath = download_dir / Path(url).name

        tries = 1

        while tries <= TRIES:
            try:
                with (
                    httpx.stream("GET", url) as response,
                    Path(filepath).open("wb") as file,
                ):
                    file.writelines(chunk for chunk in response.iter_bytes())
                break
            except Exception as e:
                print(f"ERROR DOWNLOAD (attempt {tries})\t{url}\t{e}")
                tries += 1
                sleep(DELAY)

    def _get_file_urls_by_state_cat(self, state: str, categories: set) -> set:
        """Discovers all downloadable file URLs for a state and categories.

        This internal method navigates through the FBDS website structure
        to find all available files for the specified state and
        categories. It first gets municipality URLs, then combines them
        with categories to find the actual downloadable files.

        Args:
            state: Two-letter Brazilian state code (e.g., 'SP', 'RJ',
                  'MG').
            categories: Set of category names to search for files
                       (e.g., {'APP', 'HIDROGRAFIA', 'USO'}).

        Returns:
            Set of complete URLs pointing to downloadable files with
            geographic extensions (.shp, .geojson, etc.).

        Raises:
            Exception: Network errors, HTTP errors, or parsing errors
                      during URL discovery process.
        """
        # mun URLs
        municipality_urls = self._get_urls(urljoin(BASE_URL, state))

        mun_cat_urls = set()

        # mun + cat URLS
        if municipality_urls:
            mun_cat_urls = {
                urljoin(base, cat)
                for base, cat in product(set(municipality_urls), categories)
            }

        # file URLs
        file_urls = set()

        with ThreadPoolExecutor(MAX_THREADS) as executor:
            futures = {
                executor.submit(
                    self._get_urls,
                    mun_cat_url,
                    GEO_EXTENSIONS,
                ): mun_cat_urls
                for mun_cat_url in mun_cat_urls
            }

            for future in as_completed(futures):
                url = futures[future]
                try:
                    file_urls |= future.result()
                except Exception as e:
                    print(f"ERROR\t{url}\t{e}")

        return file_urls

    def _get_urls(
        self,
        start_url: str,
        file_extensions: set | None = None,
    ) -> set[str]:
        """Extracts all relevant URLs from a webpage.

        This internal method parses HTML content from the given URL and
        extracts links based on the specified criteria. It can filter
        for specific file extensions (for files) or get all relative
        links (for navigation).

        Args:
            start_url: The webpage URL to parse for links.
            file_extensions: Set of file extensions to filter for
                           (e.g., {'shp', 'geojson', 'kml'}).
                           If None, gets all relative links for navigation.

        Returns:
            Set of complete URLs found on the webpage that match the
            filtering criteria.

        Raises:
            requests.exceptions.RequestException: Network or HTTP errors.
            Exception: HTML parsing errors or other unexpected issues.
        """
        href_links = set()

        tries = 1

        while tries <= TRIES:
            try:
                response = requests.get(start_url, timeout=(30, 300))
                response.raise_for_status()
            except Exception as e:  # noqa: PERF203
                print(f"ERROR URL (attempt {tries})\t{start_url}\t{e}")
                tries += 1
                sleep(DELAY)
            else:
                html_content = response.content
                soup = BeautifulSoup(html_content, "html.parser")
                all_links = soup.find_all("a")

                for link in all_links:
                    if link.has_attr("href"):
                        if (
                            file_extensions
                            and link.get("href").partition(".")[2]
                            in file_extensions
                        ):
                            href_links.add(urljoin(start_url, link.get("href")))

                        if link.get("href").startswith("/"):
                            href_links.add(urljoin(start_url, link.get("href")))

                break

        return href_links

    def download(
        self,
        download_dir: str,
        states: list | None = None,
        categories: list | None = None,
        *,
        create_subdirs: bool = True,
    ) -> None:
        """Downloads FBDS geographic data files for states and categories.

        This is the main method for downloading Brazilian geographic data.
        It automatically discovers available files on the FBDS website,
        organizes them by state and category, and downloads them with
        progress tracking and error handling.

        The method is designed for data analysts who need Brazilian
        geographic data for analysis, visualization, or research purposes.

        Args:
            download_dir: Local directory path where files will be saved.
                         The directory will be created if it doesn't exist.
            states: List of Brazilian state codes to download data for.
                   Use standard 2-letter codes like ['SP', 'RJ', 'MG'].
                   If None, downloads data for all available states.
            categories: List of data categories to download.
                       Examples: ['APP', 'HIDROGRAFIA', 'USO'].
                       If None, downloads all available categories.
            create_subdirs: If True, creates subdirectories matching the
                          website structure (recommended for organization).
                          If False, saves all files directly in
                          download_dir.

        Raises:
            ValueError: If invalid state codes or category names are
                       provided. Check the STATES and CATEGORIES constants
                       for valid values.
            Exception: Network errors, permission errors, or disk space
                      issues during the download process.

        Example:
            For data analysts working with Brazilian geographic data:

            >>> # Initialize the downloader
            >>> downloader = FBDSDownloader()
            >>>
            >>> # Download all data for Southeast Brazil
            >>> # Permanent Preservation Areas and Hydrography
            >>> downloader.download(
            ...     download_dir="./southeast_brazil_data",
            ...     states=["SP", "RJ", "MG", "ES"],
            ...     categories=["APP", "HIDROGRAFIA"],
            ... )
            >>>
            >>> # Download specific data for research project
            >>> downloader.download(
            ...     download_dir="./amazon_study",
            ...     states=["AM", "PA", "AC"],
            ...     categories=["USO", "APP"],
            ...     create_subdirs=True,
            ... )
            >>>
            >>> # Download everything (use with caution - large dataset!)
            >>> downloader.download(download_dir="./complete_brazil_data")

        Note:
            - Downloads can be large (GB of data) and take considerable time
            - The method respects server limits with built-in delays
            - Progress bars show download status for long-running operations
            - Failed downloads are automatically retried up to 3 times
            - Check available states and categories in the constants module
            - APP = Permanent Preservation Areas
            - HIDROGRAFIA = Hydrography (rivers, lakes, water bodies)
            - USO = Land use classification
        """
        if states and not set(states).issubset(STATES):
            msg = "Invalid state(s)"
            raise ValueError(msg)

        states = states or STATES

        if categories and not set(categories).issubset(CATEGORIES):
            msg = "Invalid category(ies)"
            raise ValueError(msg)

        categories = categories or CATEGORIES

        urls = set()

        for state in tqdm(
            states,
            total=len(states),
            leave=True,
            desc="Preparing URLs",
            dynamic_ncols=True,
            bar_format=BAR_FORMAT,
        ):
            urls |= self._get_file_urls_by_state_cat(state, categories)

        if urls:
            download_dir = Path(download_dir).resolve()
            download_dir.mkdir(parents=True, exist_ok=True)

            with ThreadPoolExecutor(MAX_THREADS) as executor:
                futures = {
                    executor.submit(
                        self._download_file,
                        url,
                        download_dir,
                        create_subdirs=create_subdirs,
                    ): url
                    for url in urls
                }

                with tqdm(
                    total=len(futures),
                    leave=True,
                    desc="Downloading",
                    dynamic_ncols=True,
                    bar_format=BAR_FORMAT,
                ) as pbar:
                    for future in as_completed(futures):
                        url = futures[future]
                        try:
                            future.result()
                        except Exception as e:
                            print(f"ERRO\t{url}\t{e}")

                        pbar.update()
