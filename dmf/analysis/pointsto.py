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
from typing import List, Tuple, Dict, NewType, Optional, Set, Deque, Union

from .helpers import (
    extend_inter_flows,
    transform,
    union_two_lattices_in_transfer,
    union_two_lattices_in_iterate,
    is_subset,
    is_call_label,
    is_return_label,
    merge_dynamic,
    is_exit_label,
    is_entry_label,
)
from .state.space import (
    DataStack,
    Store,
    CallStack,
    Context,
    Obj,
    Address,
    FuncTable,
    ClassTable,
    DataStackFrame,
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
    ClassObjectInfo,
)
from .varlattice import VarLattice, Lattice, new_empty_lattice
from ..py2flows.py2flows.cfg.flows import BasicBlock, CFG

UpdatedAnalysisInfo = NewType("UpdatedAnalysisInfo", List[Tuple[str, Set[Obj]]])


class PointsToComponents:
    # Control flow graph, it contains program points and ast nodes.
    def __init__(self):
        self.data_stack: DataStack = DataStack()
        self.store: Store = Store()
        self.call_stack: CallStack = CallStack()
        self.context: Context = Context(())
        self.func_table: FuncTable = FuncTable()
        self.class_table: ClassTable = ClassTable()

    def st(self, var: str, context: Optional[Context]) -> Address:
        return self.data_stack.st(var, context)

    def sigma(self, address: Address) -> Set[Obj]:
        return self.store.get(address)

    def update_points_to(self, address: Address, objs: Set[Obj]):
        self.store.insert_many(address, objs)


class PointsToAnalysis(PointsToComponents):
    def __init__(self, cfg: CFG):
        super().__init__()

        self.flows: Set[Tuple[int, int]] = cfg.flows
        self.inter_flows: Dict[
            int, List[int, Optional[int], Optional[int], int]
        ] = extend_inter_flows(cfg.inter_flows)
        self.vars: Set[str] = cfg.vars

        # self.flows_mapping: DefaultDict[int, Set[int]] = condense_flows(self.flows)
        self.labels: Set[int] = cfg.labels
        self.extremal_labels: Set[int] = {cfg.start.bid}
        # Note: passed by address
        self.extremal_value: Lattice = defaultdict(lambda: VarLattice(maximal=True))
        # Use None as Bottom
        self.bot: None = None

        # used for computing
        self.blocks: Dict[int, BasicBlock] = cfg.blocks
        self.func_cfgs: Dict[Tuple[str, int], (List[str, ast.AST], CFG)] = cfg.func_cfgs
        self.class_cfgs: Dict[Tuple[str, int], CFG] = cfg.class_cfgs

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
            self.analysis_list[label] = self.extremal_value
        logging.debug("analysis_list: {}".format(self.analysis_list))

    def iterate(self) -> None:
        while self.work_list:
            fst_label, snd_label = self.work_list.popleft()
            logging.debug("Current flow({}, {})".format(fst_label, snd_label))

            transferred_lattice: Lattice = self.type_analysis_transfer(fst_label)
            logging.debug("Transferred lattice: {}".format(transferred_lattice))

            self.points_to_transfer(fst_label)

            if not is_subset(transferred_lattice, self.analysis_list[snd_label]):
                self.analysis_list[snd_label] = union_two_lattices_in_iterate(
                    self.analysis_list[snd_label], transferred_lattice
                )

                # it is either call label or return label
                if snd_label in self.inter_flows:
                    # call label
                    if self.inter_flows[snd_label][0] == snd_label:
                        stmt = self.blocks[snd_label].stmt[0]
                        if isinstance(stmt, ast.Assign):
                            # function name
                            name: str = stmt.value.func.id
                            entry_label, exit_label = self.func_table.st(name)

                            self.modify_inter_flows(snd_label, entry_label, exit_label)

                            additional_flows = self.on_the_fly_flows(
                                snd_label, entry_label, exit_label
                            )
                            self.flows.update(additional_flows)
                            logging.debug("Add flows {}".format(additional_flows))

                            additional_blocks = self.on_the_fly_blocks(snd_label)
                            self.blocks.update(additional_blocks)
                            logging.debug("Add blocks {}".format(additional_blocks))
                        elif isinstance(stmt, ast.ClassDef):
                            class_name: str = stmt.name
                            name_label = (class_name, snd_label)
                            class_cfg: CFG = self.class_cfgs[name_label]
                            entry_label: int = class_cfg.start_block.bid
                            exit_label: int = class_cfg.final_block.bid
                            self.class_table.insert_class(
                                class_name, entry_label, exit_label
                            )
                            entry_label, exit_label = self.class_table.st(class_name)
                            self.modify_inter_flows(snd_label, entry_label, exit_label)

                            additional_flows = self.on_the_fly_flows(
                                snd_label, entry_label, exit_label
                            )
                            self.flows.update(additional_flows)
                            logging.debug("Add flows {}".format(additional_flows))

                            additional_blocks = self.on_the_fly_blocks(snd_label)
                            self.blocks.update(additional_blocks)
                            logging.debug("Add blocks {}".format(additional_blocks))

                # add related flows to work_list
                added_flows = [(l2, l3) for l2, l3 in self.flows if l2 == snd_label]
                print(added_flows)
                self.work_list.extendleft(added_flows)
                print(self.work_list)

    def present(self) -> None:
        all_labels: Set[int] = set()
        for flow in self.flows:
            all_labels.update(flow)

        mfp_content = {}
        mfp_effect = {}
        for label in all_labels:
            mfp_content[label] = self.analysis_list[label]
            mfp_effect[label] = self.type_analysis_transfer(label)

        for label in all_labels:
            logging.debug(
                "content label: {}, value:\n {}".format(label, mfp_content[label])
            )
            logging.debug(
                "effect label: {}, value:\n {}".format(label, mfp_effect[label])
            )

    # modify inter flows
    def modify_inter_flows(self, call_label: int, entry_label: int, exit_label: int):
        # on-the-fly edge from call to entry of the function
        # we let call, entry, exit, return label point to the same object.
        self.inter_flows[call_label][1] = entry_label
        self.inter_flows[call_label][2] = exit_label
        self.inter_flows[entry_label] = self.inter_flows[call_label]
        self.inter_flows[exit_label] = self.inter_flows[call_label]

    # add flows to pointer analysis
    def on_the_fly_flows(
        self, call_label: int, entry_label: int, exit_label: int
    ) -> Set:
        call2entry = (call_label, entry_label)
        exit2return = (exit_label, self.inter_flows[call_label][-1])
        stmt = self.blocks[call_label].stmt[0]
        flows = {call2entry, exit2return}
        if isinstance(stmt, ast.Assign):
            name: str = stmt.value.func.id
            func_objs: Set[Obj] = self.sigma(self.st(name, self.context))
            assert len(func_objs) == 1
            for obj in func_objs:
                name_label_pair = (name, obj[0])
                flows.update(self.func_cfgs[name_label_pair][1].flows)
        elif isinstance(stmt, ast.ClassDef):
            name: str = stmt.name
            name_label = (name, call_label)
            flows.update(self.class_cfgs[name_label].flows)
        return flows

    def on_the_fly_blocks(self, call_label: int):

        stmt = self.blocks[call_label].stmt[0]
        blocks = {}
        if isinstance(stmt, ast.Assign):
            name: str = stmt.value.func.id
            func_objs: Set[Obj] = self.sigma(self.st(name, self.context))
            assert len(func_objs) == 1
            for obj in func_objs:
                name_label = (name, obj[0])
                blocks.update(self.func_cfgs[name_label][1].blocks)
        elif isinstance(stmt, ast.ClassDef):
            name: str = stmt.name
            name_label = (name, call_label)
            blocks.update(self.class_cfgs[name_label].blocks)

        return blocks

    def type_analysis_transfer(self, label: int):
        if self.analysis_list[label] == self.bot:
            return self.bot

        stmt: ast.stmt = self.blocks[label].stmt[0]
        if label in self.inter_flows:
            if is_call_label(self.inter_flows, label):
                if isinstance(stmt, ast.Assign):
                    return self.type_function_call(label)
                elif isinstance(stmt, ast.ClassDef):
                    return self.type_class_call(label)
            elif is_entry_label(self.inter_flows, label):
                pass
            elif is_exit_label(self.inter_flows, label):
                if isinstance(stmt, ast.Return):
                    return self.type_Return(label)
                else:
                    return self.type_class_exit(label)
            elif is_return_label(self.inter_flows, label):
                if isinstance(stmt, ast.Assign):
                    return self.type_function_return(label)
                elif isinstance(stmt, ast.ClassDef):
                    return self.type_class_return(label)

        method = "type_" + stmt.__class__.__name__
        handler = getattr(self, method)
        return handler(label)

    # enter into new function, change context
    def type_function_call(self, label: int) -> Lattice:
        transferred_lattice: Lattice = transform([])
        old_lattice: Lattice = new_empty_lattice()
        new_lattice = union_two_lattices_in_transfer(old_lattice, transferred_lattice)
        return new_lattice

    def type_class_call(self, label: int) -> Lattice:
        transferred_lattice: Lattice = transform([])
        old_lattice: Lattice = new_empty_lattice()
        new_lattice = union_two_lattices_in_transfer(old_lattice, transferred_lattice)
        return new_lattice

    # union exit lattice and call lattice
    def type_function_return(self, label: int) -> Lattice:
        # left name in assign
        assert len(self.blocks[label].stmt[0].targets) == 1
        left_name: str = self.blocks[label].stmt[0].targets[0].id
        # right objs in pass through assign
        right_objs = self.blocks[label].pass_through_value

        assign: Lattice = transform([(left_name, right_objs)])

        call_label: int = self.inter_flows[label][0]
        call: Lattice = self.analysis_list[call_label]
        new: Lattice = union_two_lattices_in_transfer(call, assign)
        return new

    def type_class_exit(self, label: int) -> Lattice:
        transferred: Lattice = transform([])
        old: Lattice = self.analysis_list[label]
        new: Lattice = union_two_lattices_in_transfer(old, transferred)
        return new

    def type_class_return(self, label: int) -> Lattice:
        stmt: ast.ClassDef = self.blocks[label].stmt[0]
        class_name: str = stmt.name

        frame: DataStackFrame = self.blocks[label].pass_through_objs
        fields = set()
        for field in frame.items():
            fields.add(field)
        frozen_fields = frozenset(fields)
        objs: Set[Obj] = {(label, frozen_fields)}
        transferred: Lattice = transform([(class_name, objs)])

        call_label: int = self.inter_flows[label][0]
        old: Lattice = self.analysis_list[call_label]
        new: Lattice = union_two_lattices_in_transfer(old, transferred)
        return new

    # in fact it's exit
    def type_Return(self, label: int) -> Lattice:
        name: str = self.blocks[label].stmt[0].value.id
        return_label: int = self.inter_flows[label][-1]
        self.blocks[return_label].pass_through_value = self.sigma(
            self.st(name, self.context)
        )
        old: Lattice = self.analysis_list[label]
        transferred: Lattice = transform([])
        new: Lattice = union_two_lattices_in_transfer(old, transferred)
        return new

    def type_FunctionDef(self, label: int) -> Lattice:
        stmt: ast.FunctionDef = self.blocks[label].stmt[0]
        function_name: str = stmt.name
        function_objs: Set[Obj] = {FuncObjectInfo.obj}

        func_cfg = self.func_cfgs[(function_name, label)]
        entry_label: int = func_cfg[1].start_block.bid
        exit_label: int = func_cfg[1].final_block.bid
        self.func_table.insert_func(function_name, entry_label, exit_label)
        logging.debug(
            "Add ({} {} {}) to function table".format(
                function_name, entry_label, exit_label
            )
        )

        transferred_lattice: Lattice = transform([(function_name, function_objs)])
        old_lattice = self.analysis_list[label]
        new_lattice = union_two_lattices_in_transfer(old_lattice, transferred_lattice)
        return new_lattice

    def type_Assign(self, label: int) -> Lattice:
        stmt: ast.Assign = self.blocks[label].stmt[0]
        name: str = stmt.targets[0].id
        objs: Set[Obj] = self.get_objs(stmt.value)

        transferred_lattice: Lattice = transform([(name, objs)])
        old_lattice = self.analysis_list[label]
        new_lattice = union_two_lattices_in_transfer(old_lattice, transferred_lattice)
        return new_lattice

    def type_While(self, label: int) -> Lattice:
        transferred_lattice: Lattice = transform([])
        old_lattice = self.analysis_list[label]
        new_lattice = union_two_lattices_in_transfer(old_lattice, transferred_lattice)
        return new_lattice

    def type_If(self, label: int) -> Lattice:
        transferred_lattice: Lattice = transform([])
        old_lattice = self.analysis_list[label]
        new_lattice = union_two_lattices_in_transfer(old_lattice, transferred_lattice)
        return new_lattice

    def type_Pass(self, label: int) -> Lattice:
        transferred_lattice: Lattice = transform([])
        old_lattice: Lattice = self.analysis_list[label]
        new_lattice: Lattice = union_two_lattices_in_transfer(
            old_lattice, transferred_lattice
        )
        return new_lattice

    def points_to_transfer(self, label: int):

        stmt = self.blocks[label].stmt[0]
        if is_call_label(self.inter_flows, label):
            if isinstance(stmt, ast.Assign):
                self.points_to_function_call(label)
                return
            elif isinstance(stmt, ast.ClassDef):
                self.points_to_class_call(label)
                return
        elif is_entry_label(self.inter_flows, label):
            pass
        elif is_exit_label(self.inter_flows, label):
            if isinstance(stmt, ast.Return):
                self.points_to_function_return(label)
            else:
                self.points_to_class_exit(label)

        elif is_return_label(self.inter_flows, label):
            if isinstance(stmt, ast.Assign):
                self.points_to_function_return(label)
                return
            elif isinstance(stmt, ast.ClassDef):
                self.points_to_class_return(label)
                return
        method = "points_to_" + stmt.__class__.__name__
        handler = getattr(self, method)
        handler(label)

    # stmt #

    def points_to_function_call(self, label: int):

        stmt: ast.Assign = self.blocks[label].stmt[0]

        new_context = merge_dynamic(label, None, self.context)
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

    def points_to_class_call(self, label: int):
        stmt: ast.ClassDef = self.blocks[label].stmt[0]

        name: str = stmt.name

        new_context = merge_dynamic(label, None, self.context)
        next_label = self.inter_flows[label][-1]
        call_stack_frame = (next_label, self.context, self.st(name, self.context))
        logging.debug("New context after merge is: {}".format(new_context))

        self.data_stack.new_and_push_frame()
        self.call_stack.push(call_stack_frame)
        self.context = new_context

    def points_to_Return(self, label: int):
        stmt: ast.Return = self.blocks[label].stmt[0]
        _, context, address = self.call_stack.top()

        self.update_points_to(address, self.get_objs(stmt.value))
        self.data_stack.pop()
        self.call_stack.pop()
        self.context = context

    def points_to_class_exit(self, label: int):
        next_label, context, address = self.call_stack.top()
        return_label: int = self.inter_flows[label][-1]
        self.blocks[return_label].pass_through_address = address
        self.blocks[return_label].pass_through_objs = self.data_stack.top()
        self.call_stack.pop()
        self.data_stack.pop()
        self.context = context

    # Nothing needs to be done here. Since we finish the transfer in Return label
    def points_to_function_return(self, label: int):
        pass

    def points_to_class_return(self, label: int):
        address: Address = self.blocks[label].pass_through_address
        frame: DataStackFrame = self.blocks[label].pass_through_objs
        fields = set()
        for field in frame.items():
            fields.add(field)
        frozen_fields = frozenset(fields)
        objs: Set[Obj] = {(label, frozen_fields)}
        self.update_points_to(address, objs)

    # FIXME: at one time, only one name is visible.
    #  But in flows, we need to consider the situation that later declaration rewrites previous declaration
    def points_to_FunctionDef(self, label: int):
        stmt: ast.FunctionDef = self.blocks[label].stmt[0]
        name: str = stmt.name

        address: Address = self.st(name, self.context)
        objs: Set[Obj] = set()
        objs.add((label, None))
        self.update_points_to(address, objs)

    def points_to_ClassDef(self, label: int):
        pass

    def points_to_Assign(self, label: int):
        stmt: ast.Assign = self.blocks[label].stmt[0]

        right_objs = self.get_objs(stmt.value)

        # FIXME: Now we assume left has only one var.
        left_name: str = stmt.targets[0].id
        left_address: Address = self.st(left_name, self.context)
        self.update_points_to(left_address, right_objs)

    def points_to_While(self, label: int):
        pass

    def points_to_If(self, label: int):
        pass

    def points_to_Pass(self, label: int):
        pass

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

    # def get_objs_of_Call(self, expr: ast.Call) -> Set[Obj]:
    #     func: ast.expr = expr.func
    #     assert isinstance(func, ast.Name)
    #
    #     entry_label, entry_label = self.func_table.st(func.id)
    #     self.inter_flows[self.curr_label][1] = entry_label
    #     self.inter_flows[self.curr_label][2] = entry_label
    #
    #     return {NoneObjectInfo.obj}

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
