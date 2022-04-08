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
from typing import List, Tuple, Dict, NewType, Optional, Set, DefaultDict

from .state.space import DataStack, Store, CallStack, Context, Obj, Address, Var
from .state.types import (
    BoolObjectInfo,
    NoneObjectInfo,
    StrObjectInfo,
    NumObjectInfo,
)
from .varlattice import VarLattice

Lattice = NewType("Lattice", Dict[str, VarLattice])
UpdatedAnalysisInfo = NewType("UpdatedAnalysisInfo", List[Tuple[str, Obj]])


def transform(store: UpdatedAnalysisInfo) -> Lattice:
    transferred_lattice: DefaultDict[VarLattice] = defaultdict(VarLattice)
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
        stmt: ast.AST = self.blocks[label].stmt[0]

        transferred: UpdatedAnalysisInfo = self.visit(stmt)
        logging.debug("transferred {}".format(transferred))

        new_lattice: Lattice = transform(transferred)
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

        left_name: Var = stmt.targets[0].id
        left_address: Address = self.st(left_name, self.context)
        self.insert(left_address, right_obj)
        updated.append((left_name, self.sigma(left_address)))
        return updated

    # expr #
    # FIXME: In python, BoolOp doesn't return True or False. It returns the
    #  corresponding object. But it's hard to do this in static analysis.
    #  So we use subtyping to translate it to Bool.
    def get_obj_of_BoolOp(self, expr: ast.BoolOp) -> Obj:
        return BoolObjectInfo.obj

    def get_obj_of_BinOp(self, expr: ast.BinOp) -> Obj:
        op: ast.operator = expr.op

        left: ast.expr = expr.left
        right: ast.expr = expr.right
        left_obj: Obj = self.get_obj(left)
        right_obj: Obj = self.get_obj(right)

        if left_obj == StrObjectInfo.obj or right_obj == StrObjectInfo.obj:
            return StrObjectInfo.obj

        if left_obj == BoolObjectInfo.obj:
            left_obj = NumObjectInfo.obj
        if right_obj == BoolObjectInfo.obj:
            right_obj = NumObjectInfo.obj

        if left_obj == NumObjectInfo.obj and right_obj == NumObjectInfo.obj:
            return NumObjectInfo.obj

    def get_obj_of_UnaryOp(self, expr: ast.UnaryOp) -> Obj:
        if isinstance(expr.op, ast.Invert):
            return NumObjectInfo.obj
        elif isinstance(expr.op, ast.Not):
            return BoolObjectInfo.obj
        elif isinstance(expr.op, ast.UAdd):
            return NumObjectInfo.obj
        elif isinstance(expr.op, ast.USub):
            return NumObjectInfo.obj

    def get_obj_of_Num(self, expr: ast.Num) -> Obj:
        return NumObjectInfo.obj

    def get_obj_of_Str(self, expr: ast.Str) -> Obj:
        return StrObjectInfo.obj

    def get_obj_of_FormattedValue(self, expr: ast.FormattedValue) -> Obj:
        assert False, "FormattedValue is encountered."
        return StrObjectInfo.obj

    def get_obj_of_JoinedStr(self, expr: ast.JoinedStr) -> Obj:
        return StrObjectInfo.obj

    def get_obj_of_Bytes(self, expr: ast.Bytes) -> Obj:
        return StrObjectInfo.obj

    def get_obj_of_NameConstant(self, expr: ast.NameConstant) -> Obj:
        if expr.value is None:
            return NoneObjectInfo.obj
        else:
            return BoolObjectInfo.obj

    def get_obj_of_Name(self, expr: ast.Name) -> Obj:
        return self.sigma(self.st(Var(expr.id), self.context))

    def handle_Pass(self, stmt: ast.Pass = None) -> UpdatedAnalysisInfo:
        return UpdatedAnalysisInfo([])
