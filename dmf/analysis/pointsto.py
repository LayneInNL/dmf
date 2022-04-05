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

import ast
import logging
from collections import defaultdict
from typing import List, Tuple, Dict, NewType, Optional, Set

from .state.space import DataStack, Store, CallStack, Context, Obj, Address
from .state.types import (
    BoolFalseObjectAddress,
    BoolTrueObjectAddress,
    NoneObjectAddress,
    NumPosObjectAddress,
    NumZeroObjectAddress,
    StrEmptyObjectAddress,
    StrNonEmptyObjectAddress,
)
from .varlattice import VarLattice

Lattice = NewType("Lattice", Dict[str, VarLattice])


def transform(store: List[Tuple[str, Obj]]) -> Dict[str, VarLattice]:
    transferred_lattice = defaultdict(VarLattice)
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


class PointsToAnalysis:
    def __init__(self, blocks):
        self.blocks = blocks
        # Control flow graph, it contains program points and ast nodes.
        self.data_stack: DataStack = DataStack()
        self.store: Store = Store()
        self.call_stack: CallStack = CallStack()
        self.context: Context = Context(())

        self.analysis_list: Optional[Dict[int, Lattice]] = None

    def link_analysis_list(self, analysis_list: Dict[int, Lattice]):
        self.analysis_list = analysis_list

    def transfer(self, label: int) -> Dict[str, VarLattice]:
        # We would like to refactor the code with the strategy in ast.NodeVisitor
        stmt = self.blocks[label].stmt[0]

        method = "handle_" + stmt.__class__.__name__
        handler = getattr(self, method)
        transferred = handler(stmt)
        logging.debug("transferred {}".format(transferred))

        new_lattice = transform(transferred)
        if not new_lattice:
            new_lattice = self.analysis_list[label]
        logging.debug("transferred lattice {}".format(new_lattice))

        return new_lattice

    def handle_Assign(self, stmt: ast.Assign) -> List[Tuple[str, Obj]]:
        type_of_value = type(stmt.value)
        right_address = None
        if type_of_value == ast.NameConstant:
            right_address = self.handle_NameConstant(stmt.value)
        elif type_of_value == ast.Name:
            right_address = self.data_stack.st(stmt.value.id, self.context)
        elif type_of_value == ast.Num:
            right_address = self.handle_Num(stmt.value)
        elif type_of_value == ast.Str:
            right_address = self.handle_Str(stmt.value)
        assert right_address is not None
        right_obj = self.store.get(right_address)
        left_name = stmt.targets[0].id
        left_address = self.data_stack.st(left_name, self.context)
        self.store.insert_one(left_address, right_obj)
        return [(left_name, self.store.get(left_address))]

    def handle_NameConstant(self, expr) -> Address:
        right_address = None
        if expr.value is None:
            right_address = self.data_stack.st(NoneObjectAddress.name, None)
        if type(expr.value) == bool:
            if expr.value:
                right_address = self.data_stack.st(BoolTrueObjectAddress.name, None)
            elif not expr.value:
                right_address = self.data_stack.st(BoolFalseObjectAddress.name, None)
        assert right_address is not None
        return right_address

    def handle_Num(self, expr: ast.Num) -> Address:
        right_address = None

        if expr.n == 0:
            right_address = self.data_stack.st(NumZeroObjectAddress.name, None)
        else:
            right_address = self.data_stack.st(NumPosObjectAddress.name, None)

        assert right_address is not None
        return right_address

    def handle_Str(self, expr: ast.Str) -> Address:
        right_address = None
        if not expr.s:
            right_address = self.data_stack.st(StrEmptyObjectAddress.name, None)
        else:
            right_address = self.data_stack.st(StrNonEmptyObjectAddress.name, None)

        assert right_address is not None
        return right_address

    def handle_Pass(self, stmt: ast.Pass = None) -> List:
        return []
