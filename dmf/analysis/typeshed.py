#  Copyright 2022 Layne Liu
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple, Tuple, Optional, Dict

import dmf.resources


class SearchContext(NamedTuple):
    typeshed: Path
    version: Tuple[int, int]
    platform: str


def init_search_context():
    version = sys.version_info[:2]
    if sys.platform == "win32":
        typeshed = os.path.join(dmf.resources.__path__[0], "typeshed/stdlib")
    else:
        paths = list(dmf.resources.__path__)
        typeshed = os.path.join(paths[0], "typeshed/stdlib")
    abs_typeshed = os.path.abspath(typeshed)
    platform = sys.platform
    return SearchContext(
        typeshed=Path(abs_typeshed), version=version, platform=platform
    )


default_search_context: SearchContext = init_search_context()


def get_stub_file(module_name: str) -> Optional[Path]:
    return get_stub_file_name(tuple(module_name.split(".")))


def get_stub_file_name(module_name: Tuple[str, ...]) -> Optional[Path]:
    # https://www.python.org/dev/peps/pep-0561/#type-checker-module-resolution-order
    # typeshed_client doesn't support 1 (MYPYPATH equivalent) and 2 (user code)
    top_level_name, *rest = module_name

    versions = get_typeshed_versions(default_search_context.typeshed)
    version = versions[top_level_name]
    if default_search_context.version < version.min:
        raise NotImplementedError
    if version.max is not None and default_search_context.version > version.max:
        raise NotImplementedError

    return _find_stub_in_dir(default_search_context.typeshed, module_name)


def _find_stub_in_dir(stub_dir: Path, module_name: Tuple[str, ...]) -> Optional[Path]:
    if not module_name:
        init_name = stub_dir / "__init__.pyi"
        if init_name.exists():
            return init_name
        raise FileNotFoundError(module_name)
    if len(module_name) == 1:
        stub_name = stub_dir / f"{module_name[0]}.pyi"
        if stub_name.exists():
            return stub_name
    next_name, *rest = module_name
    next_dir = stub_dir / next_name
    if next_dir.exists():
        return _find_stub_in_dir(next_dir, rest)
    raise FileNotFoundError(module_name)


class _VersionData(NamedTuple):
    min: Tuple[int, int]
    max: Optional[Tuple[int, int]]


@lru_cache()
def get_typeshed_versions(typeshed: Path) -> Dict[str, _VersionData]:
    versions = {}
    with (typeshed / "VERSIONS").open() as f:
        for line in f:
            line = line.split("#")[0].strip()
            if not line:
                continue
            module, version = line.split(": ")
            if "-" in version:
                min_version_str, max_version_str = version.split("-")
            else:
                min_version_str = version
                max_version_str = None
            if max_version_str:
                max_version = _parse_version(max_version_str)
            else:
                max_version = None
            min_version = _parse_version(min_version_str)
            versions[module] = _VersionData(min_version, max_version)
    return versions


def _parse_version(version: str) -> Tuple[int, int]:
    major, minor = version.split(".")
    return int(major), int(minor)
