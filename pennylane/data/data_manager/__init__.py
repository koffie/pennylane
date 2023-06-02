# Copyright 2018-2023 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Contains functions for querying available datasets and downloading
them.
"""

import typing
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
from functools import lru_cache
from pathlib import Path
from time import sleep
from typing import List, Optional, Union

import fsspec
import requests

from pennylane.data.base import Dataset
from pennylane.data.base._hdf5 import h5py

from ._params import DEFAULT, FULL, resolve_params
from .types import DataPath, FolderMapView, ParamArg

S3_URL = "https://datasets.cloud.pennylane.ai/datasets/h5"
FOLDERMAP_URL = f"{S3_URL}/foldermap.json"
DATA_STRUCT_URL = f"{S3_URL}/data_struct.json"


@lru_cache(maxsize=1)
def _get_foldermap():
    """Fetch the foldermap from S3."""
    response = requests.get(FOLDERMAP_URL, timeout=5.0)
    response.raise_for_status()

    return FolderMapView(response.json())


@lru_cache(maxsize=1)
def _get_data_struct():
    """Fetch the data struct from S3."""
    response = requests.get(DATA_STRUCT_URL, timeout=5.0)
    response.raise_for_status()

    return response.json()


def _download_partial(
    s3_path: str, dest: Path, attributes: typing.Iterable[str], cache_dir: Optional[Path]
) -> None:
    """Download only the requested attributes of the Dataset at ``s3_path``."""
    if cache_dir is not None:
        fs = fsspec.open(f"blockcache::{s3_path}", blockcache={"cache_storage": str(cache_dir)})
    else:
        fs = fsspec.open(s3_path)

    with h5py.File(fs.open()) as f:
        remote_dataset = Dataset(f)
        remote_dataset.write(dest, "w", attributes)


def _download_dataset(
    data_path: DataPath,
    dest: Path,
    attributes: Optional[typing.Iterable[str]],
    cache_dir: Optional[Path],
) -> None:
    """Downloads the dataset at ``data_path`` to ``dest``, optionally downloading
    only requested attributes."""
    s3_path = f"{S3_URL}/{data_path}"

    if attributes is not None:
        return _download_partial(s3_path, dest, attributes, cache_dir)

    with open(dest, "wb") as f:
        resp = requests.get(s3_path, timeout=5.0)
        resp.raise_for_status()

        f.write(resp.content)


def load(  # pylint: ignore=too-many-arguments
    data_name: str,
    attributes: Optional[typing.Iterable[str]] = None,
    folder_path: Path = Path("./datasets/"),
    force: bool = False,
    num_threads: int = 50,
    cache_dir: Optional[Path] = Path(".cache"),
    **params: Union[ParamArg, str, List[str]],
):
    r"""Downloads the data if it is not already present in the directory and return it to user as a
    :class:`~pennylane.data.Dataset` object. For the full list of available datasets, please see the
    `datasets website <https://pennylane.ai/qml/datasets.html>`_.

    Args:
        data_name (str)   : A string representing the type of data required such as `qchem`, `qpsin`, etc.
        attributes (list[str]) : An optional list to specify individual data element that are required
        download_dir (str) : Path to the directory used for saving datasets
        params (kwargs)   : Keyword arguments exactly matching the parameters required for the data type.
            Note that these are not optional

    Returns:
        list[:class:`~pennylane.data.Dataset`]
    """

    folder_path = Path(folder_path)
    if cache_dir is not None and not Path(cache_dir).is_absolute():
        cache_dir = folder_path / cache_dir

    foldermap = _get_foldermap()
    data_struct = _get_data_struct()

    data_paths = [
        data_path for _, data_path in resolve_params(data_struct, foldermap, data_name, **params)
    ]
    dest_paths = [
        local_path
        for local_path in (folder_path / data_path for data_path in data_paths)
        if force or not local_path.exists()
    ]
    if not data_paths:
        return []

    for path_parents in set(path.parent for path in dest_paths):
        path_parents.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(min(num_threads, len(dest_paths))) as pool:
        futures = [
            pool.submit(_download_dataset, data_path, dest_path, attributes, cache_dir)
            for data_path, dest_path in zip(data_paths, dest_paths)
        ]
        results = wait(futures, return_when=FIRST_EXCEPTION)
        for result in results.done:
            if result.exception():
                raise result.exception()

    return [Dataset.open(dest_path, "r") for dest_path in dest_paths]


def list_datasets():
    r"""Returns a dictionary of the available datasets.

    Return:
        dict: Nested dictionary representing the directory structure of the hosted datasets.

    **Example:**

    Note that the results of calling this function may differ from this example as more datasets
    are added. For updates on available data see the `datasets website <https://pennylane.ai/qml/datasets.html>`_.

    .. code-block :: pycon

        >>> qml.data.list_datasets()
        {'qchem': {'H2': {'6-31G': ['0.5', '0.54', '0.58', ... '2.02', '2.06', '2.1'],
                          'STO-3G': ['0.5', '0.54', '0.58', ... '2.02', '2.06', '2.1']},
                   'HeH+': {'6-31G': ['0.5', '0.54', '0.58', ... '2.02', '2.06', '2.1'],
                            'STO-3G': ['0.5', '0.54', '0.58', ... '2.02', '2.06', '2.1']},
                   'LiH': {'STO-3G': ['0.5', '0.54', '0.58', ... '2.02', '2.06', '2.1']},
                   'OH-': {'STO-3G': ['0.5', '0.54', '0.58', ... '0.94', '0.98', '1.02']}},
        'qspin': {'Heisenberg': {'closed': {'chain': ['1x16', '1x4', '1x8'],
                                            'rectangular': ['2x2', '2x4', '2x8', '4x4']},
                                 'open': {'chain': ['1x16', '1x4', '1x8'],
                                        'rectangular': ['2x2', '2x4', '2x8', '4x4']}},
                  'Ising': {'closed': {'chain': ['1x16', '1x4', '1x8'],
                                        'rectangular': ['2x2', '2x4', '2x8', '4x4']},
                            'open': {'chain': ['1x16', '1x4', '1x8'],
                                    'rectangular': ['2x2', '2x4', '2x8', '4x4']}}}}
    """

    return _get_foldermap()


def list_attributes(data_name):
    r"""List the attributes that exist for a specific ``data_name``.

    Args:
        data_name (str): The type of the desired data

    Returns:
        list (str): A list of accepted attributes for a given data name
    """
    data_struct = _get_data_struct()
    if data_name not in data_struct:
        raise ValueError(
            f"Currently the hosted datasets are of types: {list(data_struct)}, but got {data_name}."
        )
    return data_struct[data_name]["attributes"]


def _interactive_request_attributes(options):
    """Prompt the user to select a list of attributes."""
    prompt = "Please select attributes:"
    for i, option in enumerate(options):
        if option == "full":
            option = "full (all attributes)"
        prompt += f"\n\t{i+1}) {option}"
    print(prompt)
    choices = input(f"Choice (comma-separated list of options) [1-{len(options)}]: ").split(",")
    try:
        choices = list(map(int, choices))
    except ValueError as e:
        raise ValueError(f"Must enter a list of integers between 1 and {len(options)}") from e
    if any(choice < 1 or choice > len(options) for choice in choices):
        raise ValueError(f"Must enter a list of integers between 1 and {len(options)}")
    return [options[choice - 1] for choice in choices]


def _interactive_request_single(node, param):
    """Prompt the user to select a single option from a list."""
    options = list(node)
    if len(options) == 1:
        print(f"Using {options[0]} as it is the only {param} available.")
        sleep(1)
        return options[0]
    print(f"Please select a {param}:")
    print("\n".join(f"\t{i+1}) {option}" for i, option in enumerate(options)))
    try:
        choice = int(input(f"Choice [1-{len(options)}]: "))
    except ValueError as e:
        raise ValueError(f"Must enter an integer between 1 and {len(options)}") from e
    if choice < 1 or choice > len(options):
        raise ValueError(f"Must enter an integer between 1 and {len(options)}")
    return options[choice - 1]


def load_interactive():
    r"""Download a dataset using an interactive load prompt.

    Returns:
        :class:`~pennylane.data.Dataset`

    **Example**

    .. code-block :: pycon

        >>> qml.data.load_interactive()
        Please select a data name:
            1) qspin
            2) qchem
        Choice [1-2]: 1
        Please select a sysname:
            ...
        Please select a periodicity:
            ...
        Please select a lattice:
            ...
        Please select a layout:
            ...
        Please select attributes:
            ...
        Force download files? (Default is no) [y/N]: N
        Folder to download to? (Default is pwd, will download to /datasets subdirectory):

        Please confirm your choices:
        dataset: qspin/Ising/open/rectangular/4x4
        attributes: ['parameters', 'ground_states']
        force: False
        dest folder: /Users/jovyan/Downloads/datasets
        Would you like to continue? (Default is yes) [Y/n]:
        <Dataset = description: qspin/Ising/open/rectangular/4x4, attributes: ['parameters', 'ground_states']>
    """

    foldermap = _get_foldermap()
    data_struct = _get_data_struct()

    node = foldermap
    data_name = _interactive_request_single(node, "data name")

    description = {}
    value = data_name

    params = data_struct[data_name]["params"]
    for param in params:
        node = node[value]
        value = _interactive_request_single(node, param)
        description[param] = value

    attributes = _interactive_request_attributes(data_struct[data_name]["attributes"])
    force = input("Force download files? (Default is no) [y/N]: ") in ["y", "Y"]
    dest_folder = Path(
        input("Folder to download to? (Default is pwd, will download to /datasets subdirectory): ")
    )

    print("\nPlease confirm your choices:")
    print("dataset:", "/".join([data_name] + [description[param] for param in params]))
    print("attributes:", attributes)
    print("force:", force)
    print("dest folder:", dest_folder / "datasets")

    approve = input("Would you like to continue? (Default is yes) [Y/n]: ")
    if approve not in ["Y", "", "y"]:
        print("Aborting and not downloading!")
        return None
    return load(
        data_name, attributes=attributes, folder_path=dest_folder, force=force, **description
    )[0]


__all__ = (
    "load",
    "load_interactive",
    "list_datasets",
    "list_attributes",
    "FULL",
    "DEFAULT",
    "ParamArg",
)
