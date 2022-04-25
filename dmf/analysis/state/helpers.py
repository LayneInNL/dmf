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

from collections import defaultdict
from typing import Tuple, Set, Optional


# def transform(abstract_values):
#
#     transferred_lattice: DefaultDict[
#         str,
#     ] = defaultdict()
#     for (name, context), objects in store.items():
#         transferred_lattice[name].transform(objects)
#
#     return transferred_lattice


def merge(original_lattice, added_lattice):
    in_original: Set[str] = set(original_lattice.keys())
    in_added: Set[str] = set(added_lattice.keys())
    mixed: Set[str] = in_original | in_added

    for key in mixed:
        if key in in_original:
            added_lattice[key].merge(original_lattice[key])

    return added_lattice


def merge_dynamic(curr_label: int, heap_context, context) -> Tuple:
    if heap_context is None:
        return context[-1:] + (curr_label,)
    else:
        pass


def extend_inter_flows(inter_flows: Set[Tuple[int, Optional[int], Optional[int], int]]):
    new_inter_flows = {}
    for a, b, c, d in inter_flows:
        temp = [a, b, c, d]
        new_inter_flows[a] = temp
        new_inter_flows[d] = temp
    return new_inter_flows


def union_two_lattices_in_transfer(old, new):
    # if old is self.bot, we can't get any new info from it. So old can't be self.bot
    diff_old_new = set(old).difference(new)
    for var in diff_old_new:
        new[var] = old[var]

    return new


def union_values(old, new):
    if old is None:
        return new

    intersection_old_new = set(old).intersection(new)
    for var in intersection_old_new:
        new[var].union(old[var])
    diff_old_new = set(old).difference(new)
    for var in diff_old_new:
        new[var] = old[var]

    return new


def union_analyses(original, transferred):
    if original is None:
        return transferred

    for context, analysis in original.items():
        transferred[context] = union_values(original[context], transferred[context])

    return transferred


def is_call_label(inter_flows, label: int) -> bool:
    if label in inter_flows and label == inter_flows[label][0]:
        return True
    else:
        return False


def is_entry_label(inter_flows, label: int) -> bool:
    if label in inter_flows and label == inter_flows[label][1]:
        return True
    else:
        return False


def is_exit_label(inter_flows, label: int) -> bool:
    if label in inter_flows and label == inter_flows[label][-2]:
        return True
    else:
        return False


def is_return_label(inter_flows, label: int) -> bool:
    if label in inter_flows and label == inter_flows[label][-1]:
        return True
    else:
        return False


def issubset(transferred, original):
    # (None, None) and (None, ?)
    if transferred is None:
        return True

    # (?, None)
    if original is None:
        return False

    # (Dict[Tuple, Dict[str, AbstractValue]], Dict[Tuple, Dict[str, AbstractValue]])
    transferred_contexts = set(transferred)
    original_contexts = set(original)
    if transferred_contexts.issubset(original_contexts):
        for context in transferred_contexts:
            transferred_vars = set(transferred[context])
            original_vars = set(original[context])
            if transferred_vars.issubset(original_vars):
                for var in transferred_vars:
                    if not transferred[context][var].issubset(original[context][var]):
                        return False
            return False
    return False


class PrettyDefaultDict(defaultdict):
    __repr__ = dict.__repr__
