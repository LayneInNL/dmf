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
from typing import Dict, Any


def subset(lattice1, lattice2):
    if lattice1 is None:
        return True

    if lattice2 is None:
        return False

    return lattice1 <= lattice2


# check if dict1 is a subset of dict2
def issubset(dict1: Dict, dict2: Dict):
    for key in dict1:
        if key not in dict2:
            return False
        elif not dict1[key] <= dict2[key]:
            return False

    return True


def issubset_twodict(dict1: Dict[Any, Dict], dict2: Dict[Any, Dict]):
    for key in dict1:
        if key not in dict2:
            return False
        if not issubset(dict1[key], dict2[key]):
            return False

    return True


# update dict1 based on dict2.
# union two lattices.
def update(dict1: Dict, dict2: Dict):
    for key in dict2:
        if key not in dict1:
            dict1[key] = dict2[key]
        else:
            dict1[key] += dict2[key]


def update_twodict(dict1: Dict[Any, Dict], dict2: Dict[Any, Dict]):
    for key in dict2:
        if key not in dict1:
            dict1[key] = dict2[key]
        else:
            dict1[key].update(dict2[key])
