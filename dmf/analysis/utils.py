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
from __future__ import annotations
from collections import defaultdict
from typing import Dict, Any


class LatticeDict(defaultdict):
    def __repr__(self):
        return dict.__repr__(self)


def subset(state1, state2):
    if state1 is None:
        return True

    if state2 is None:
        return False

    return state1 <= state2


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
