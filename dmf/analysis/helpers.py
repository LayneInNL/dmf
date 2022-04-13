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

from collections import defaultdict
from typing import List, Tuple, Set, DefaultDict, Dict, Optional

from dmf.analysis.state.space import Obj, HContext, Context
from dmf.analysis.varlattice import VarLattice, Lattice


def transform(store: List[Tuple[str, Set[Obj]]]) -> Lattice:
    transferred_lattice: DefaultDict[str, VarLattice] = defaultdict(VarLattice)
    for name, objects in store:
        transferred_lattice[name].transform(objects)

    return transferred_lattice


def merge(
    original_lattice: Dict[str, VarLattice], added_lattice: Dict[str, VarLattice]
) -> Dict[str, VarLattice]:
    in_original: Set[str] = set(original_lattice.keys())
    in_added: Set[str] = set(added_lattice.keys())
    mixed: Set[str] = in_original | in_added

    for key in mixed:
        if key in in_original:
            added_lattice[key].merge(original_lattice[key])

    return added_lattice


def merge_dynamic(
    curr_label: int, heap_context: Optional[HContext], context: Context
) -> Tuple:
    if heap_context is None:
        return context[-1:] + (curr_label,)
    else:
        pass


def extend_inter_flows(inter_flows):
    new_inter_flows = {}
    for a, b, c in inter_flows:
        temp = [a, b, c]
        new_inter_flows[a] = temp
        new_inter_flows[c] = temp
    return new_inter_flows


def union_two_lattices_in_transfer(old: Lattice, new: Lattice) -> Lattice:
    # if old is self.bot, we can't get any new info from it. So old can't be self.bot
    diff_old_new = set(old).difference(new)
    for var in diff_old_new:
        new[var] = old[var]

    return new


def union_two_lattices_in_iterate(old: Lattice, new: Lattice) -> Lattice:
    if old is None:
        return new
    diff_old_new = set(old).difference(new)
    for var in diff_old_new:
        new[var] = old[var]

    return new


def is_call_label(inter_flows, label: int) -> bool:
    if label in inter_flows and label == inter_flows[label][0]:
        return True
    else:
        return False


def is_exit_return_label(inter_flows, label: int) -> bool:
    if label in inter_flows and label == inter_flows[label][-1]:
        return True
    else:
        return False


def is_subset(left: Optional[Lattice], right: Optional[Lattice]):
    # (None, None), (None, ?)
    if left is None:
        return True

    # (?, None)
    if right is None:
        return False

    left_vars = set(left)
    right_vars = set(right)
    if left_vars.issubset(right_vars):
        for var in left_vars:
            if not left[var].is_subset(right[var]):
                return False
        return True

    return False
