import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


class FBDSDownloader:
    def __init__(self):
        self.__root_url = "https://geo.fbds.org.br"
        self.__workers = min(cpu_count(), 4) # WARNING: keep this number LOW
        self.themes = {
            "APP": "APP",
            "APP_USO": "APP",
            "NASCENTES": "HIDROGRAFIA",
            "MASSAS_DAGUA": "HIDROGRAFIA",
            "RIOS_DUPLOS": "HIDROGRAFIA",
            "RIOS_SIMPLES": "HIDROGRAFIA",
            "USO": "USO",
        }

    def download(
        self,
        download_path: str = None,
        themes: list = None,
        state_codes: list = None,
    ):
        download_path = (
            Path(download_path) if download_path else Path.cwd() / "data"
        )

        sel_municipality_urls = self.get_municipality_urls(state_codes)

        if themes:
            for theme in themes:
                if theme not in self.themes.keys():
                    raise Exception(
                        f"Invalid theme. Valid options: {', '.join(self.get_themes())}"
                    )

            sel_themes = themes
        else:
            sel_themes = self.get_themes()

        unique_dirs = set([self.themes.get(theme) for theme in sel_themes])

        municipality_dir_urls = [
            urljoin(sel_municipality, unique_dir)
            for sel_municipality in sel_municipality_urls # [:1]  # DEBUG
            for unique_dir in unique_dirs
        ]

        file_urls = list()

        with ThreadPoolExecutor(self.__workers) as executor:
            futures = [
                executor.submit(
                    self._get_file_url, municipality_dir_url, sel_themes
                )
                for municipality_dir_url in municipality_dir_urls
            ]

            for future in as_completed(futures):
                file_urls.append(future.result())

        file_urls = [url for urls in file_urls for url in urls]
        downloaded_files = list()

        with ThreadPoolExecutor(self.__workers) as executor:
            futures = [
                executor.submit(self._download_file, file_url, download_path)
                for file_url in file_urls
            ]

            with tqdm(
                total=len(futures),
                desc="Downloading files",
                unit="",
                leave=False,
            ) as pbar:
                for future in as_completed(futures):
                    downloaded_files.append(future.result())
                    pbar.update()

        return downloaded_files

    def get_municipality_urls(self, state_codes: list = None) -> list:
        municipality_urls = list()

        if not state_codes:
            state_codes = [
                state_code[-3:-1] for state_code in self.get_state_urls()
            ]

        with ThreadPoolExecutor(self.__workers) as executor:
            for result in executor.map(
                self._get_municipality_urls, state_codes
            ):
                municipality_urls.append(result)

        return [item for sublist in municipality_urls for item in sublist]

    def get_state_urls(self) -> list:
        state_urls = list()
        state_a_elements = self._get_a_page_elements(self.__root_url)
        state_urls = [
            self._build_url(url["href"])
            for url in state_a_elements
            if re.match(r"^/.*/$", url["href"])
        ]

        return state_urls

    def get_themes(self) -> list:
        return list(self.themes.keys())

    def _build_url(self, url_part: str):
        return urljoin(self.__root_url, url_part)

    def _download_file(self, url: str, download_path: Path) -> Path:
        result = requests.get(url, stream=True)

        file_path = download_path / url.removeprefix(f"{self.__root_url}/")
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "wb") as f:
            for chunk in result.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)

        return file_path

    def _get_a_page_elements(self, url: str) -> list:
        a_elements = list()

        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(e)
            else:
                raise

        soup = BeautifulSoup(response.content, "html.parser")
        a_elements = soup.find_all("a")

        return a_elements

    def _get_file_url(
        self, municipality_dir_url: str, sel_themes: list
    ) -> list:
        file_urls = list()

        dir_a_elements = self._get_a_page_elements(municipality_dir_url)
        file_urls = [
            self._build_url(a["href"])
            for a in dir_a_elements
            if any(f"{substring}." in a["href"] for substring in sel_themes)
        ]

        return file_urls

    def _get_municipality_urls(self, state_code: str) -> list:
        municipality_a_elements = self._get_a_page_elements(
            self._build_url(state_code)
        )
        municipality_urls = [
            self._build_url(url["href"])
            for url in municipality_a_elements
            if re.match(r"^/.*/$", url["href"])
        ]

        return municipality_urls
