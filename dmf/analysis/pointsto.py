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

from .state.space import DataStack, Store, CallStack, Context, Obj, Address, Var
from .state.types import (
    BoolFalseObjectAddress,
    BoolTrueObjectAddress,
    NoneObjectAddress,
    NumPosObjectAddress,
    NumZeroObjectAddress,
    NumPosZeroNegObjectAddress,
    NumNegZeroObjectAddress,
    NumNegObjectAddress,
    NumPosZeroObjectAddress,
    StrEmptyObjectAddress,
    StrNonEmptyObjectAddress,
    ZERO_OBJECTS,
    BOOL_OBJS,
    NUM_OBJS,
    get_num_type,
)
from .varlattice import VarLattice

Lattice = NewType("Lattice", Dict[str, VarLattice])
UpdatedAnalysisInfo = NewType("UpdatedAnalysisInfo", List[Tuple[str, Obj]])


def transform(store: UpdatedAnalysisInfo) -> Lattice:
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

    def st(self, var: Var, context: Optional[Context]) -> Address:
        return self.data_stack.st(var, context)

    def sigma(self, address: Address) -> Obj:
        return self.store.get(address)

    def insert(self, address: Address, obj: Obj):
        self.store.insert_one(address, obj)

    def transfer(self, label: int) -> Lattice:
        # We would like to refactor the code with the strategy in ast.NodeVisitor
        stmt = self.blocks[label].stmt[0]

        transferred = self.visit(stmt)
        logging.debug("transferred {}".format(transferred))

        new_lattice = transform(transferred)
        if not new_lattice:
            new_lattice = self.analysis_list[label]
        logging.debug("transferred lattice {}".format(new_lattice))

        return new_lattice

    def visit(self, stmt) -> UpdatedAnalysisInfo:
        method = "handle_" + stmt.__class__.__name__
        handler = getattr(self, method)
        return handler(stmt)

    def get_obj(self, expr: ast.expr) -> Obj:
        method = "get_obj_of_" + expr.__class__.__name__
        handler = getattr(self, method)
        return handler(expr)

    def handle_Assign(self, stmt: ast.Assign) -> UpdatedAnalysisInfo:
        updated: UpdatedAnalysisInfo = UpdatedAnalysisInfo([])
        right_obj = self.get_obj(stmt.value)

        left_name = stmt.targets[0].id
        left_address = self.st(left_name, self.context)
        self.insert(left_address, right_obj)
        updated.append((left_name, self.sigma(left_address)))
        return updated

    # expr #

    # In a CFG, we make sure it has the form of left op right
    # TODO
    def get_obj_of_BoolOp(self, expr: ast.BoolOp) -> Obj:
        op: ast.boolop = expr.op
        values: List[ast.expr] = expr.values
        left: Obj = self.get_obj(values[0])
        right: Obj = self.get_obj(values[1])
        if type(op) == ast.And:
            if left in ZERO_OBJECTS:
                return left
            else:
                return right
        elif type(op) == ast.Or:
            if left in ZERO_OBJECTS:
                return right
            else:
                return left

    def get_obj_of_BinOp(self, expr: ast.BinOp) -> Obj:
        op: ast.operator = expr.op

        left: ast.expr = expr.left
        left_obj: Obj = self.get_obj(left)
        if type(left) == bool:
            left_obj = BOOL_OBJS[left_obj]
        right: ast.expr = expr.right
        right_obj: Obj = self.get_obj(right)
        if type(right) == bool:
            right_obj = BOOL_OBJS[right_obj]

        if left_obj in NUM_OBJS and right_obj in NUM_OBJS:
            return get_num_type(left_obj, right_obj, op)

    def get_obj_of_UnaryOp(self, expr: ast.UnaryOp):
        if isinstance(expr.op, ast.UAdd):
            return self.get_obj(expr.operand)

    def get_obj_of_Num(self, expr: ast.Num) -> Obj:
        if expr.n == 0:
            return self.sigma(self.st(NumZeroObjectAddress.name, None))
        else:
            return self.sigma(self.st(NumPosObjectAddress.name, None))

    def get_obj_of_Str(self, expr: ast.Str) -> Obj:
        if not expr.s:
            return self.sigma(self.st(StrEmptyObjectAddress.name, None))
        else:
            return self.sigma(self.st(StrNonEmptyObjectAddress.name, None))

    def get_obj_of_NameConstant(self, expr: ast.NameConstant) -> Obj:
        if expr.value is None:
            return self.sigma(self.st(NoneObjectAddress.name, None))
        elif expr.value:
            return self.sigma(self.st(BoolTrueObjectAddress.name, None))
        else:
            return self.sigma(self.st(BoolFalseObjectAddress.name, None))

    def get_obj_of_Name(self, expr: ast.Name) -> Obj:
        return self.sigma(self.st(Var(expr.id), self.context))

    def handle_Pass(self, stmt: ast.Pass = None) -> UpdatedAnalysisInfo:
        return []
