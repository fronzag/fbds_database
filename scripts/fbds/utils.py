import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm


def compress_files(dir_path: str) -> None:
    file_path_patterns = __get_file_path_patterns(dir_path)

    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(__compress_files, file_path_pattern)
            for file_path_pattern in file_path_patterns
        ]

        with tqdm(
            total=len(futures), desc="Compressing files", unit="", leave=False
        ) as pbar:
            for _ in as_completed(futures):
                pbar.update()


def __compress_files(file_path_pattern: str) -> Path:
    file_path_pattern = Path(file_path_pattern)
    compressed_file = file_path_pattern.with_suffix(".zip")
    compressed_file.unlink(missing_ok=True)
    file_paths = [
        file_path
        for file_path in file_path_pattern.parent.glob(
            f"{file_path_pattern.stem}.*"
        )
        if file_path.suffix != ".zip"
    ]

    try:
        with zipfile.ZipFile(compressed_file, "a", compresslevel=9) as zf:
            for file_path in file_paths:
                zf.write(file_path, arcname=file_path.name)
    except Exception as e:
        print(e)
    else:
        [file_path.unlink(missing_ok=True) for file_path in file_paths]

    return compressed_file


def __get_file_path_patterns(dir_path: str) -> set:
    dir_path = Path(dir_path)
    file_path_patterns = set()

    [
        file_path_patterns.add(str(path).partition(".")[0])
        for path in dir_path.rglob("*")
        if path.is_file()
    ]

    return file_path_patterns
