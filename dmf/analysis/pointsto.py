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

from .state.space import (
    DataStack,
    Store,
    CallStack,
    Context,
    Obj,
    Address,
    Var,
    FuncTable,
)
from .state.types import (
    BoolObjectInfo,
    NoneObjectInfo,
    StrObjectInfo,
    NumObjectInfo,
    DictObjectInfo,
    SetObjectInfo,
    ListObjectInfo,
    TupleObjectInfo,
    FuncObjectInfo,
)
from .varlattice import VarLattice
from ..py2flows.py2flows.cfg.flows import BasicBlock, CallAndAssignBlock, CFG

Lattice = NewType("Lattice", Dict[str, VarLattice])
UpdatedAnalysisInfo = NewType("UpdatedAnalysisInfo", List[Tuple[str, Set[Obj]]])


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
    def __init__(self, blocks, func_cfgs, class_cfgs):
        self.blocks: Dict[int, BasicBlock] = blocks
        self.func_cfgs: Dict[str, CFG] = func_cfgs
        self.class_cfgs: Dict[str, CFG] = class_cfgs
        # Control flow graph, it contains program points and ast nodes.
        self.next_label: int = 0
        self.data_stack: DataStack = DataStack()
        self.store: Store = Store()
        self.call_stack: CallStack = CallStack()
        self.context: Context = Context(())
        self.func_table: FuncTable = FuncTable()

        self.analysis_list: Optional[Dict[int, Lattice]] = None

    def link_analysis_list(self, analysis_list: Dict[int, Lattice]):
        self.analysis_list = analysis_list

    def st(self, var: Var, context: Optional[Context]) -> Address:
        return self.data_stack.st(var, context)

    def sigma(self, address: Address) -> Set[Obj]:
        return self.store.get(address)

    def insert_one(self, address: Address, obj: Obj):
        self.store.insert_one(address, obj)

    def update_points_to(self, address: Address, objs: Set[Obj]):
        self.store.insert_many(address, objs)

    def transfer(self, label: int) -> Lattice:
        # We would like to refactor the code with the strategy in ast.NodeVisitor

        transferred: UpdatedAnalysisInfo = self.visit(label)
        logging.debug("transferred {}".format(transferred))

        new_lattice: Lattice = transform(transferred)
        if not new_lattice:
            new_lattice = self.analysis_list[label]
        logging.debug("transferred lattice {}".format(new_lattice))

        return new_lattice

    # stmt #

    def visit(self, label: int) -> UpdatedAnalysisInfo:
        stmt = self.blocks[label].stmt[0]
        # method = "handle_" + stmt.__class__.__name__
        # handler = getattr(self, method)
        if isinstance(stmt, ast.FunctionDef):
            return self.handle_FunctionDef(stmt)
        # return handler(stmt)
        elif isinstance(stmt, ast.Assign):
            return self.handle_Assign(stmt)
        elif isinstance(stmt, ast.Pass):
            return self.handle_Pass(stmt)

    # FIXME: at one time, only one name is visible.
    #  But in flows, we need to consider the situation that later declaration rewrites previous declaration
    def handle_FunctionDef(self, stmt: ast.FunctionDef) -> UpdatedAnalysisInfo:
        updated: UpdatedAnalysisInfo = UpdatedAnalysisInfo([])
        name: Var = stmt.name
        self.func_table.insert_func(
            name,
            self.func_cfgs[name][1].start_block.bid,
            self.func_cfgs[name][1].final_block.bid,
        )

        address: Address = self.st(name, self.context)
        self.update_points_to(address, {FuncObjectInfo.obj})

        args = stmt.args
        body = stmt.body
        decorator_list = stmt.decorator_list
        returns = stmt.returns

        updated.append((name, {FuncObjectInfo.obj}))

        return updated

    # TODO: it's better to let return always return variable names
    # TODO: better to add labels to points-to rather than dmf
    def handle_Return(self, stmt: ast.Return) -> UpdatedAnalysisInfo:
        updated: UpdatedAnalysisInfo = UpdatedAnalysisInfo([])

        # get variable name
        name: str = stmt.value.id

        # update analysis components
        next_label, next_store, next_address = self.call_stack.top()
        self.update_points_to(next_address, self.sigma(self.st(name, self.context)))

        self.next_label = next_label
        self.call_stack.pop()
        self.store = next_store

        updated.append(
            (next_address[0], self.sigma(self.st(next_address, self.context)))
        )

        return updated

    def handle_Assign(self, stmt: ast.Assign) -> UpdatedAnalysisInfo:
        updated: UpdatedAnalysisInfo = UpdatedAnalysisInfo([])
        right_objs = self.get_objs(stmt.value)

        # FIXME: Now we assume left has only one var.
        left_name: Var = stmt.targets[0].id
        left_address: Address = self.st(left_name, self.context)
        self.update_points_to(left_address, right_objs)
        updated.append((left_name, self.sigma(left_address)))
        return updated

    # expr #
    def get_objs(self, expr: ast.expr) -> Set[Obj]:
        method = "get_objs_of_" + expr.__class__.__name__
        handler = getattr(self, method)
        return handler(expr)

    # FIXME: In python, BoolOp doesn't return True or False. It returns the
    #  corresponding object. But it's hard to do this in static analysis.
    #  So we use subtyping to translate it to Bool.
    def get_objs_of_BoolOp(self, expr: ast.BoolOp) -> Set[Obj]:
        return {BoolObjectInfo.obj}

    def get_objs_of_BinOp(self, expr: ast.BinOp) -> Set[Obj]:

        left: ast.expr = expr.left
        right: ast.expr = expr.right
        left_objs: Set[Obj] = self.get_objs(left)
        right_objs: Set[Obj] = self.get_objs(right)

        if StrObjectInfo.obj in left_objs or StrObjectInfo.obj in right_objs:
            return {StrObjectInfo.obj}

        return {NumObjectInfo.obj}

    def get_objs_of_UnaryOp(self, expr: ast.UnaryOp) -> Set[Obj]:
        if isinstance(expr.op, (ast.Invert, ast.UAdd, ast.USub)):
            return {NumObjectInfo.obj}
        elif isinstance(expr.op, ast.Not):
            return {BoolObjectInfo.obj}

    def get_objs_of_Lambda(self, expr: ast.Lambda) -> Set[Obj]:
        assert False, "Lambda is encountered."

    # TODO
    def get_objs_of_IfExp(self, expr: ast.IfExp) -> Set[Obj]:
        body_objs: Set[Obj] = self.get_objs(expr.body)
        orelse_objs: Set[Obj] = self.get_objs(expr.orelse)
        return body_objs | orelse_objs

    def get_objs_of_Dict(self, expr: ast.Dict) -> Set[Obj]:
        return {DictObjectInfo.obj}

    def get_objs_of_Set(self, expr: ast.Set) -> Set[Obj]:
        return {SetObjectInfo.obj}

    def get_objs_of_ListComp(self, expr: ast.ListComp) -> Set[Obj]:
        assert False

    def get_objs_of_SetComp(self, expr: ast.SetComp) -> Set[Obj]:
        assert False

    def get_objs_of_DictComp(self, expr: ast.DictComp) -> Set[Obj]:
        assert False

    def get_objs_of_GeneratorExpr(self, expr: ast.GeneratorExp) -> Set[Obj]:
        assert False

    def get_objs_of_Await(self, expr: ast.Await) -> Set[Obj]:
        return self.get_objs(expr.value)

    # I remember we transform yield (empty) into yield None
    def get_objs_of_Yield(self, expr: ast.Yield) -> Set[Obj]:
        return self.get_objs(expr.value)

    def get_objs_of_YieldFrom(self, expr: ast.YieldFrom) -> Set[Obj]:
        return self.get_objs(expr.value)

    def get_objs_of_Compare(self, expr: ast.Expr) -> Set[Obj]:
        return {BoolObjectInfo.obj}

    def get_objs_of_Call(self, expr: ast.Call) -> Set[Obj]:
        func: ast.expr = expr.func
        assert isinstance(func, ast.Name)
        args: List[ast.expr] = expr.args
        keywords: List[ast.keyword] = expr.keywords

        self.data_stack.new_and_push_frame()
        self.store = self.store
        self.call_stack.emplace(self.next_label, self.context, self.call_stack)
        self.next_label = None

        return {NoneObjectInfo.obj}

    def get_objs_of_Num(self, expr: ast.Num) -> Set[Obj]:
        return {NumObjectInfo.obj}

    def get_objs_of_Str(self, expr: ast.Str) -> Set[Obj]:
        return {StrObjectInfo.obj}

    def get_objs_of_FormattedValue(self, expr: ast.FormattedValue) -> Set[Obj]:
        assert False, "FormattedValue is encountered."

    def get_objs_of_JoinedStr(self, expr: ast.JoinedStr) -> Set[Obj]:
        return {StrObjectInfo.obj}

    def get_objs_of_Bytes(self, expr: ast.Bytes) -> Set[Obj]:
        return {StrObjectInfo.obj}

    def get_objs_of_NameConstant(self, expr: ast.NameConstant) -> Set[Obj]:
        if expr.value is None:
            return {NoneObjectInfo.obj}
        else:
            return {BoolObjectInfo.obj}

    def get_objs_of_Ellipsis(self, expr: ast.Ellipsis) -> Set[Obj]:
        assert False

    def get_objs_of_Constant(self, expr: ast.Constant) -> Set[Obj]:
        assert False

    def get_objs_of_Attribute(self, expr: ast.Attribute) -> Set[Obj]:
        value: ast.expr = expr.value
        attr = expr.attr
        value_objs = self.get_objs(value)
        assert False

    def get_objs_of_Subscript(self, expr: ast.Subscript) -> Set[Obj]:
        value: ast.expr = expr.value
        assert False

    def get_objs_of_Starred(self, expr: ast.Starred) -> Set[Obj]:
        value: ast.expr = expr.value
        assert False

    def get_objs_of_Name(self, expr: ast.Name) -> Set[Obj]:
        return self.sigma(self.st(Var(expr.id), self.context))

    def get_objs_of_List(self, expr: ast.List) -> Set[Obj]:
        return {ListObjectInfo.obj}

    def get_objs_of_Tuple(self, expr: ast.Tuple) -> Set[Obj]:
        return {TupleObjectInfo.obj}

    def handle_Pass(self, stmt: ast.Pass = None) -> UpdatedAnalysisInfo:
        return UpdatedAnalysisInfo([])
