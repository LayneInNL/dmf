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
from collections import defaultdict, deque
from typing import List, Tuple, Dict, NewType, Optional, Set, DefaultDict, Deque, Union

from .state.space import (
    DataStack,
    Store,
    CallStack,
    Context,
    Obj,
    Address,
    FuncTable,
    HContext,
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
from ..py2flows.py2flows.cfg.flows import BasicBlock, CFG, CallAndAssignBlock

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


# def condense_flows(flows: Set[Tuple[int, int]]) -> DefaultDict[int, Set[int]]:
#     condensed_flows: DefaultDict[int, Set[int]] = defaultdict(set)
#     for fst, snd in flows:
#         condensed_flows[fst].add(snd)
#
#     return condensed_flows


def extend_inter_flows(inter_flows):
    new_inter_flows = {}
    for a, b, c in inter_flows:
        temp = [a, b, c]
        new_inter_flows[a] = temp
        new_inter_flows[c] = temp
    return new_inter_flows


class PointsToAnalysis:
    def __init__(self, cfg: CFG):

        self.flows: Set[Tuple[int, int]] = cfg.flows
        self.inter_flows: Dict[int, List[int, Optional[int], int]] = extend_inter_flows(
            cfg.inter_flows
        )

        # self.flows_mapping: DefaultDict[int, Set[int]] = condense_flows(self.flows)
        self.labels: Set[int] = cfg.labels
        self.extremal_labels: Set[int] = {cfg.start.bid}
        # Note: passed by address
        self.extremal_value: Lattice = defaultdict(VarLattice)
        # Use None as Bottom
        self.bot: None = None

        # used for iteration
        self.work_list: Optional[Deque[Tuple[int, int]]] = None
        self.analysis_list: Optional[Dict[int, Lattice]] = None

        # used for final result
        self.mfp_content: Optional[Dict[int, Lattice]] = None
        self.mfp_effect: Optional[Dict[int, Lattice]] = None

        # used for computing
        self.blocks: Dict[int, BasicBlock] = cfg.blocks
        self.func_cfgs: Dict[str, (List[str, ast.AST], CFG)] = cfg.func_cfgs
        self.class_cfgs: Dict[str, (List[str, ast.AST], CFG)] = cfg.class_cfgs

        # Control flow graph, it contains program points and ast nodes.
        self.curr_label = cfg.start.bid
        self.data_stack: DataStack = DataStack()
        self.store: Store = Store()
        self.call_stack: CallStack = CallStack()
        self.context: Context = Context(())
        self.func_table: FuncTable = FuncTable()

        self.added_flows = set()
        self.added_labels = set()
        self.added_blocks = {}

        self.all_labels = None

    def compute_fixed_point(self) -> None:
        self.initialize()
        self.iterate()
        self.present()

    def initialize(self) -> None:
        # WorkList W
        self.work_list = deque(self.flows)
        logging.debug("work_list: {}".format(self.work_list))

        # Analysis list
        self.analysis_list = defaultdict(lambda: self.bot)
        for label in self.extremal_labels:
            # We use None to represent BOTTOM in analysis lattice
            self.analysis_list[label] = self.extremal_value
        logging.debug("analysis_list: {}".format(self.analysis_list))

    def iterate(self) -> None:
        while self.work_list:
            fst_label, snd_label = self.work_list.popleft()
            logging.debug("Current flow({}, {})".format(fst_label, snd_label))
            self.curr_label = fst_label

            # since the result of points-to analysis is incremental, we just use the transferred result
            transferred_lattice: Lattice = self.transfer(fst_label)
            snd_label_lattice: Lattice = self.analysis_list[snd_label]

            if not self.is_subset(transferred_lattice, snd_label_lattice):
                self.analysis_list[snd_label] = self.union_two_lattices_in_iterate(
                    self.analysis_list[snd_label], transferred_lattice
                )

                # it is eiter call label or exit_return label
                if snd_label in self.inter_flows:
                    # call label
                    if self.inter_flows[snd_label][0] == snd_label:
                        stmt: ast.Assign = self.blocks[snd_label].stmt[0]
                        # function name
                        name: str = stmt.value.func.id
                        entry_label, exit_label = self.func_table.st(name)
                        # on-the-fly edge from call to entry of the function
                        self.inter_flows[snd_label][1] = entry_label
                        call2entry = (snd_label, entry_label)
                        self.flows.add(call2entry)
                        exit2return = (exit_label, self.inter_flows[snd_label][-1])
                        self.flows.add(exit2return)
                        self.added_flows.add(call2entry)
                        self.added_flows.add(exit2return)
                        logging.debug("Add flow {}".format(call2entry))
                        self.flows.update(self.func_cfgs[name][1].flows)
                        self.added_flows.update(self.func_cfgs[name][1].flows)
                        logging.debug(
                            "Add flows {}".format(self.func_cfgs[name][1].flows)
                        )
                        self.blocks.update(self.func_cfgs[name][1].blocks)
                        self.added_blocks.update(self.func_cfgs[name][1].blocks)
                        logging.debug(
                            "add blocks {}".format(self.func_cfgs[name][1].blocks)
                        )
                        # add function flows to self.flows

                        # self.work_list.appendleft((snd_label, entry_label))
                        # self.work_list.extendleft(self.func_cfgs[name][1].flows)
                        # self.work_list.appendleft(
                        #     (exit_label, self.inter_flows[snd_label][3])
                        # )
                    # exit_return label
                    elif self.inter_flows[snd_label][-1] == snd_label:
                        # return
                        pass
                added_flows = [(l2, l3) for l2, l3 in self.flows if l2 == snd_label]
                self.work_list.extendleft(added_flows)

    def present(self) -> None:
        self.all_labels = set()
        for flow in self.flows:
            self.all_labels.update(flow)

        self.mfp_content = {}
        self.mfp_effect = {}
        for label in self.all_labels:
            self.mfp_content[label] = self.analysis_list[label]
            # self.mfp_effect[label] = self.transfer(label)

    def pprint(self):
        logging.debug("data stack:\n{}".format(self.data_stack))
        logging.debug("store:\n{}".format(self.store))
        for label in self.all_labels:
            logging.debug(
                "content label: {}, value:\n {}".format(label, self.mfp_content[label])
            )
            # logging.debug(
            #     "effect label: {}, value:\n {}".format(label, self.mfp_effect[label])
            # )

    def is_subset(self, left: Optional[Lattice], right: Optional[Lattice]):
        # (None, None), (None, ?)
        if left == self.bot:
            return True

        # (?, None)
        if right == self.bot:
            return False

        left_vars = set(left)
        right_vars = set(right)
        if left_vars.issubset(right_vars):
            for var in left_vars:
                if not left[var].is_subset(right[var]):
                    return False
            return True

        return False

    def union_two_lattices_in_transfer(self, old: Lattice, new: Lattice) -> Lattice:
        # if old is self.bot, we can't get any new info from it. So old can't be self.bot
        diff_old_new = set(old).difference(new)
        for var in diff_old_new:
            new[var] = old[var]

        return new

    def union_two_lattices_in_iterate(self, old: Lattice, new: Lattice) -> Lattice:
        if old == self.bot:
            return new
        diff_old_new = set(old).difference(new)
        for var in diff_old_new:
            new[var] = old[var]

        return new

    def st(self, var: str, context: Optional[Context]) -> Address:
        return self.data_stack.st(var, context)

    def sigma(self, address: Address) -> Set[Obj]:
        return self.store.get(address)

    def update_points_to(self, address: Address, objs: Union[Set[Obj], Obj]):
        if isinstance(objs, Set):
            self.store.insert_many(address, objs)
        else:
            self.store.insert_many(address, {objs})

    def transfer(self, label: int) -> Lattice:
        if self.analysis_list[label] == self.bot:
            return self.bot

            # We would like to refactor the code with the strategy in ast.NodeVisitor

        transferred: UpdatedAnalysisInfo = self.visit(label)
        logging.debug("transferred {}".format(transferred))
        new_fst_lattice: Lattice = transform(transferred)
        logging.debug("transferred lattice {}".format(new_fst_lattice))
        old_fst_lattice = self.analysis_list[label]
        new_fst_lattice = self.union_two_lattices_in_transfer(
            old_fst_lattice, new_fst_lattice
        )
        return new_fst_lattice

    # stmt #

    def is_call_label(self, label: int) -> bool:
        if label in self.inter_flows and label == self.inter_flows[label][0]:
            return True
        else:
            return False

    def is_exit_return_label(self, label: int) -> bool:
        if label in self.inter_flows and label == self.inter_flows[label][-1]:
            return True
        else:
            return False

    def visit(self, label: int) -> UpdatedAnalysisInfo:

        print(self.work_list)
        print(label)
        stmt = self.blocks[label].stmt[0]
        if self.is_call_label(label):
            return self.handle_call_label(label)
        elif isinstance(stmt, ast.Return):
            return self.handle_exit_return_label(label)
        elif self.is_exit_return_label(label):
            return self.handle_return_label(label)
        # method = "handle_" + stmt.__class__.__name__
        # handler = getattr(self, method)
        if isinstance(stmt, ast.FunctionDef):
            return self.handle_FunctionDef(stmt)
        # return handler(stmt)
        elif isinstance(stmt, ast.Assign):
            return self.handle_Assign(stmt)
        elif isinstance(stmt, ast.Pass):
            return self.handle_Pass(stmt)

    def merge(
        self, curr_label: int, heap_context: Optional[HContext], context: Context
    ) -> Tuple:
        if heap_context is None:
            return context[-1:] + (curr_label,)
        else:
            pass

    def handle_call_label(self, label: int) -> UpdatedAnalysisInfo:

        stmt: ast.Assign = self.blocks[label].stmt[0]

        new_context = self.merge(label, None, self.context)
        logging.debug("New context after merge is: {}".format(new_context))
        next_label = self.inter_flows[label][-1]
        call_stack_frame = (
            next_label,
            self.context,
            self.st(stmt.targets[0].id, self.context),
        )
        logging.debug("Next label is: {}".format(call_stack_frame))
        self.data_stack.new_and_push_frame()
        self.call_stack.push(call_stack_frame)
        self.context = new_context

        return UpdatedAnalysisInfo([])

    def handle_exit_return_label(self, return_label: int) -> UpdatedAnalysisInfo:
        return_label_content: Lattice = self.analysis_list[return_label]
        next_label, context, address = self.call_stack.top()
        self.call_stack.pop()

        stmt: ast.Return = self.blocks[return_label].stmt[0]
        self.update_points_to(address, self.get_objs(stmt.value))
        return [(address[0], self.sigma(address))]

    def handle_return_label(self, return_label: int) -> UpdatedAnalysisInfo:
        return []

    # FIXME: at one time, only one name is visible.
    #  But in flows, we need to consider the situation that later declaration rewrites previous declaration
    def handle_FunctionDef(self, stmt: ast.FunctionDef) -> UpdatedAnalysisInfo:
        updated: UpdatedAnalysisInfo = UpdatedAnalysisInfo([])
        name: str = stmt.name
        self.func_table.insert_func(
            name,
            self.func_cfgs[name][1].start_block.bid,
            self.func_cfgs[name][1].final_block.bid,
        )
        logging.debug(
            "Add ({} {} {}) to function table".format(
                name,
                self.func_cfgs[name][1].start_block.bid,
                self.func_cfgs[name][1].final_block.bid,
            )
        )

        address: Address = self.st(name, self.context)
        self.update_points_to(address, {FuncObjectInfo.obj})

        updated.append((name, {FuncObjectInfo.obj}))

        return updated

    # TODO: it's better to let return always return variable names
    # TODO: better to add labels to points-to rather than dmf
    # def handle_Return(self, stmt: ast.Return) -> UpdatedAnalysisInfo:
    #     updated: UpdatedAnalysisInfo = UpdatedAnalysisInfo([])
    #
    #     value: ast.Name = stmt.value
    #     # get variable name
    #     name: str = value.id
    #
    #     # update analysis components
    #     next_label, next_store, next_address = self.call_stack.top()
    #     self.update_points_to(next_address, self.sigma(self.st(name, self.context)))
    #
    #     self.next_label = next_label
    #     self.call_stack.pop()
    #     self.store = next_store
    #
    #     updated.append(
    #         (next_address[0], self.sigma(self.st(next_address, self.context)))
    #     )
    #
    #     return updated

    def handle_Assign(self, stmt: ast.Assign) -> UpdatedAnalysisInfo:
        updated: UpdatedAnalysisInfo = UpdatedAnalysisInfo([])

        right_objs = self.get_objs(stmt.value)

        # FIXME: Now we assume left has only one var.
        left_name: str = stmt.targets[0].id
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

        entry_id, exit_id = self.func_table.st(func.id)
        self.inter_flows[self.curr_label][1] = entry_id
        self.inter_flows[self.curr_label][2] = exit_id

        args: List[ast.expr] = expr.args
        keywords: List[ast.keyword] = expr.keywords

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
        return self.sigma(self.st(str(expr.id), self.context))

    def get_objs_of_List(self, expr: ast.List) -> Set[Obj]:
        return {ListObjectInfo.obj}

    def get_objs_of_Tuple(self, expr: ast.Tuple) -> Set[Obj]:
        return {TupleObjectInfo.obj}

    def handle_Pass(self, stmt: ast.Pass = None) -> UpdatedAnalysisInfo:
        return UpdatedAnalysisInfo([])
