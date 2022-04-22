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
from typing import List, Tuple, Dict, NewType, Optional, Set

from .helpers import (
    extend_inter_flows,
    transform,
    union_two_lattices_in_transfer,
    is_subset,
    is_call_label,
    is_return_label,
    merge_dynamic,
    is_exit_label,
    is_entry_label,
    union_analyses,
)
from .state.space import (
    DataStack,
    Store,
    CallStack,
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
)
from .varlattice import Lattice, new_empty_lattice, VarLattice
from ..py2flows.py2flows.cfg.flows import BasicBlock, CFG

UpdatedAnalysisInfo = NewType("UpdatedAnalysisInfo", List[Tuple[str, Set[Obj]]])


class PointsToComponents:
    # Control flow graph, it contains program points and ast nodes.
    def __init__(self):
        self.data_stack: DataStack = DataStack()
        self.store: Store = Store()
        self.call_stack: CallStack = CallStack()
        self.context: Tuple = ()
        self.func_table: FuncTable = FuncTable()
        self.class_table: ClassTable = ClassTable()

    def st(self, var: str, context: Tuple) -> Address:
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

        self.extremal_label: int = cfg.start.bid
        # Note: passed by address
        self.extremal_value = {(): defaultdict(lambda: VarLattice(maximal=True))}
        # Use None as Bottom
        self.bot = None

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
        # lift (fst_label, snd_label) with context information
        self.work_list = deque(self.flows)
        logging.debug("work_list: {}".format(self.work_list))

        # Analysis list
        # label -> context -> lattice {{}}
        self.analysis_list = defaultdict(lambda: self.bot)
        self.analysis_list[self.extremal_label] = self.extremal_value
        logging.debug("analysis_list: {}".format(self.analysis_list))

    def iterate(self) -> None:
        while self.work_list:
            fst_label, snd_label = self.work_list.popleft()
            logging.debug("Current flow({}, {})".format(fst_label, snd_label))

            effects, transferred = self.type_analysis_transfer(fst_label)
            logging.debug("Transferred lattice: {}".format(transferred))
            if transferred == self.bot:
                logging.debug("Skip this iteration")
                continue

            self.points_to_transfer(fst_label, effects)

            if not is_subset(transferred, self.analysis_list[snd_label]):
                self.analysis_list[snd_label] = union_analyses(
                    self.analysis_list[snd_label], transferred
                )

                # it is either call label or return label
                if snd_label in self.inter_flows:
                    # call label
                    if self.inter_flows[snd_label][0] == snd_label:
                        stmt = self.blocks[snd_label].stmt[0]
                        if isinstance(stmt, ast.Assign):
                            if isinstance(stmt.value, ast.Call) and isinstance(
                                stmt.value.func, ast.Name
                            ):
                                # function name
                                name: str = stmt.value.func.id
                                entry_label, exit_label = self.func_table.st(name)

                                self.modify_inter_flows(
                                    snd_label, entry_label, exit_label
                                )

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
                self.work_list.extendleft(added_flows)

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
            if isinstance(stmt.value, ast.Call) and isinstance(
                stmt.value.func, ast.Name
            ):
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

    def type_analysis_transfer(self, label):
        if not self.analysis_list[label]:
            return None, self.bot

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
                    return self.type_function_exit(label)
                else:
                    return self.type_class_exit(label)
            elif is_return_label(self.inter_flows, label):
                if isinstance(stmt, ast.Assign):
                    return self.type_function_exit(label)
                elif isinstance(stmt, ast.ClassDef):
                    return self.type_class_return(label)

        method = "type_" + stmt.__class__.__name__
        handler = getattr(self, method)
        return handler(label)

    # enter into new function
    def type_function_call(self, label: int):
        new_analysis = defaultdict(lambda: None)
        for context, old in self.analysis_list[label].items():
            effects = defaultdict(set)
            transferred: Lattice = transform(effects)
            old: Lattice = new_empty_lattice()
            new = union_two_lattices_in_transfer(old, transferred)
            new_context = merge_dynamic(label, None, context)
            new_analysis[new_context] = new

        return None, new_analysis

    def type_class_call(self, label: int):
        effects = []
        transferred: Lattice = transform(effects)
        old: Lattice = new_empty_lattice()
        new = union_two_lattices_in_transfer(old, transferred)
        return effects, new

    def type_function_return(self, label: int):
        effects = []
        # left name in assign
        stmt = self.blocks[label].stmt[0]
        left_name: str = stmt.targets[0].id
        # right objs in pass through assign
        right_objs = self.blocks[label].pass_through_value
        effects.append((left_name, right_objs))
        transferred: Lattice = transform(effects)

        call_label: int = self.inter_flows[label][0]
        call = self.analysis_list[call_label]
        new = union_two_lattices_in_transfer(call, transferred)
        return effects, new

    def type_function_exit(self, label: int):
        effects = []
        name: str = self.blocks[label].stmt[0].value.id
        return_label: int = self.inter_flows[label][-1]
        self.blocks[return_label].pass_through_value = self.sigma(
            self.st(name, self.context)
        )
        old: Lattice = self.analysis_list[label]
        transferred: Lattice = transform(effects)
        new: Lattice = union_two_lattices_in_transfer(old, transferred)
        return effects, new

    # id function
    def type_class_exit(self, label: int):
        effects = []
        transferred = transform(effects)
        old = self.analysis_list[label]
        new = union_two_lattices_in_transfer(old, transferred)
        return effects, new

    def type_class_return(self, label: int):
        effects = []
        stmt: ast.ClassDef = self.blocks[label].stmt[0]
        class_name: str = stmt.name

        frame: DataStackFrame = self.blocks[label].pass_through_objs
        fields = set()
        for field in frame.items():
            fields.add(field)
        frozen_fields = frozenset(fields)
        objs: Set[Obj] = {(label, frozen_fields)}
        effects.append((class_name, objs))
        transferred: Lattice = transform(effects)

        call_label: int = self.inter_flows[label][0]
        old: Lattice = self.analysis_list[call_label]
        new: Lattice = union_two_lattices_in_transfer(old, transferred)
        return effects, new

    def type_FunctionDef(self, label: int):
        stmt: ast.FunctionDef = self.blocks[label].stmt[0]
        function_name: str = stmt.name

        func_cfg = self.func_cfgs[(function_name, label)]
        entry_label: int = func_cfg[1].start_block.bid
        exit_label: int = func_cfg[1].final_block.bid
        self.func_table.insert_func(function_name, entry_label, exit_label)
        logging.debug(
            "Add ({} {} {}) to function table".format(
                function_name, entry_label, exit_label
            )
        )

        new_analysis = defaultdict(lambda: None)
        for context, old in self.analysis_list[label].items():
            effects = defaultdict(set)
            address = self.st(function_name, self.context)
            effects[address].add((label, None))
            transferred = transform(effects)
            new = union_two_lattices_in_transfer(old, transferred)
            new_analysis[context] = new

        return None, new_analysis

    def type_Assign(self, label):
        stmt: ast.Assign = self.blocks[label].stmt[0]
        if isinstance(stmt.targets[0], ast.Name):
            name = stmt.targets[0].id
        elif isinstance(stmt.targets[0], ast.Attribute):
            assert False
        elif isinstance(stmt.targets[0], ast.Subscript):
            assert False
        elif isinstance(stmt.targets[0], ast.Tuple):
            assert False

        objs: Set[Obj] = self.get_objs(stmt.value)
        new_analysis = defaultdict(lambda: None)
        for context, old in self.analysis_list[label].items():
            effects = defaultdict(set)
            address = self.st(name, self.context)
            effects[address].update(objs)
            transferred = transform(effects)
            new = union_two_lattices_in_transfer(old, transferred)
            new_analysis[context] = new
        return None, new_analysis

    def type_While(self, label: int):
        return self.type_Pass(label)

    def type_If(self, label: int):
        return self.type_Pass(label)

    def type_Pass(self, label: int):
        new_analysis = {}
        effects = defaultdict(set)
        for context, old in self.analysis_list[label].items():
            transferred = transform(effects)
            new = union_two_lattices_in_transfer(old, transferred)
            new_analysis[context] = new
        return None, new_analysis

    def points_to_transfer(self, label, effects):

        stmt = self.blocks[label].stmt[0]
        if is_call_label(self.inter_flows, label):
            if isinstance(stmt, ast.Assign):
                self.points_to_function_call(label, effects)
                return
            elif isinstance(stmt, ast.ClassDef):
                self.points_to_class_call(label, effects)
                return
        elif is_entry_label(self.inter_flows, label):
            pass
        elif is_exit_label(self.inter_flows, label):
            if isinstance(stmt, ast.Return):
                self.points_to_function_return(label, effects)
            else:
                self.points_to_class_exit(label, effects)

        elif is_return_label(self.inter_flows, label):
            if isinstance(stmt, ast.Assign):
                self.points_to_function_return(label, effects)
                return
            elif isinstance(stmt, ast.ClassDef):
                self.points_to_class_return(label, effects)
                return
        method = "points_to_" + stmt.__class__.__name__
        handler = getattr(self, method)
        handler(label, effects)

    # stmt #

    def points_to_function_call(self, label, effects):

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

    def points_to_class_call(self, label, effects):
        stmt: ast.ClassDef = self.blocks[label].stmt[0]

        name: str = stmt.name

        new_context = merge_dynamic(label, None, self.context)
        next_label = self.inter_flows[label][-1]
        call_stack_frame = (next_label, self.context, self.st(name, self.context))
        logging.debug("New context after merge is: {}".format(new_context))

        self.data_stack.new_and_push_frame()
        self.call_stack.push(call_stack_frame)
        self.context = new_context

    def points_to_Return(self, label, effects):
        stmt: ast.Return = self.blocks[label].stmt[0]
        _, context, address = self.call_stack.top()

        self.update_points_to(address, self.get_objs(stmt.value))
        self.data_stack.pop()
        self.call_stack.pop()
        self.context = context

    def points_to_class_exit(self, label, effects):
        next_label, context, address = self.call_stack.top()
        return_label: int = self.inter_flows[label][-1]
        self.blocks[return_label].pass_through_address = address
        self.blocks[return_label].pass_through_objs = self.data_stack.top()
        self.call_stack.pop()
        self.data_stack.pop()
        self.context = context

    # Nothing needs to be done here. Since we finish the transfer in Return label
    def points_to_function_return(self, label, effects):
        pass

    def points_to_class_return(self, label, effects):
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
    def points_to_FunctionDef(self, label, effects):
        stmt: ast.FunctionDef = self.blocks[label].stmt[0]
        name: str = stmt.name

        address: Address = self.st(name, self.context)
        objs: Set[Obj] = set()
        objs.add((label, None))
        self.update_points_to(address, objs)

    def points_to_Assign(self, label, effects):
        stmt: ast.Assign = self.blocks[label].stmt[0]

        right_objs = self.get_objs(stmt.value)

        if isinstance(stmt.targets[0], ast.Name):
            left_name: str = stmt.targets[0].id
            left_address: Address = self.st(left_name, self.context)
            self.update_points_to(left_address, right_objs)
        else:
            assert False

    def points_to_While(self, label, effects):
        pass

    def points_to_If(self, label, effects):
        pass

    def points_to_Pass(self, label, effects):
        pass

    # expr #
    def get_objs(self, expr: ast.expr) -> Set[Obj]:
        method = "objs_" + expr.__class__.__name__
        handler = getattr(self, method)
        return handler(expr)

    # BoolOp has been desugared in control flow graph
    def objs_BoolOp(self, expr: ast.BoolOp):
        assert False, "BoolOp is encountered"

    def objs_BinOp(self, expr: ast.BinOp) -> Set[Obj]:

        left: ast.expr = expr.left
        right: ast.expr = expr.right
        left_objs: Set[Obj] = self.get_objs(left)
        right_objs: Set[Obj] = self.get_objs(right)

        if StrObjectInfo.obj in left_objs or StrObjectInfo.obj in right_objs:
            return {StrObjectInfo.obj}

        return {NumObjectInfo.obj}

    def objs_UnaryOp(self, expr: ast.UnaryOp) -> Set[Obj]:
        if isinstance(expr.op, (ast.Invert, ast.UAdd, ast.USub)):
            return {NumObjectInfo.obj}
        elif isinstance(expr.op, ast.Not):
            return {BoolObjectInfo.obj}

    def objs_Lambda(self, expr: ast.Lambda):
        assert False, "Lambda is encountered."

    # TODO
    def objs_IfExp(self, expr: ast.IfExp):
        assert False, "IfExp is encountered"

    def objs_Dict(self, expr: ast.Dict) -> Set[Obj]:
        return {DictObjectInfo.obj}

    def objs_Set(self, expr: ast.Set) -> Set[Obj]:
        return {SetObjectInfo.obj}

    def objs_ListComp(self, expr: ast.ListComp):
        assert False, "ListComp is encountered"

    def objs_SetComp(self, expr: ast.SetComp):
        assert False, "SetComp is encountered"

    def objs_DictComp(self, expr: ast.DictComp):
        assert False, "DictComp is encountered"

    def objs_GeneratorExpr(self, expr: ast.GeneratorExp):
        assert False, "GeneratorExpr is encountered"

    def objs_Await(self, expr: ast.Await) -> Set[Obj]:
        return self.get_objs(expr.value)

    # I remember we transform yield (empty) into yield None
    def objs_Yield(self, expr: ast.Yield) -> Set[Obj]:
        return self.get_objs(expr.value)

    def objs_YieldFrom(self, expr: ast.YieldFrom) -> Set[Obj]:
        return self.get_objs(expr.value)

    def objs_Compare(self, expr: ast.Expr) -> Set[Obj]:
        return {BoolObjectInfo.obj}

    def objs_Num(self, expr: ast.Num) -> Set[Obj]:
        return {NumObjectInfo.obj}

    def objs_Str(self, expr: ast.Str) -> Set[Obj]:
        return {StrObjectInfo.obj}

    def objs_FormattedValue(self, expr: ast.FormattedValue) -> Set[Obj]:
        assert False, "FormattedValue is encountered."

    def objs_JoinedStr(self, expr: ast.JoinedStr) -> Set[Obj]:
        return {StrObjectInfo.obj}

    def objs_Bytes(self, expr: ast.Bytes) -> Set[Obj]:
        return {StrObjectInfo.obj}

    def objs_NameConstant(self, expr: ast.NameConstant) -> Set[Obj]:
        if expr.value is None:
            return {NoneObjectInfo.obj}
        else:
            return {BoolObjectInfo.obj}

    def objs_Ellipsis(self, expr: ast.Ellipsis) -> Set[Obj]:
        assert False

    def objs_Constant(self, expr: ast.Constant) -> Set[Obj]:
        assert False

    def objs_Attribute(self, expr: ast.Attribute) -> Set[Obj]:
        value: ast.expr = expr.value
        attr = expr.attr
        value_objs = self.get_objs(value)
        assert False

    def objs_Subscript(self, expr: ast.Subscript) -> Set[Obj]:
        value: ast.expr = expr.value
        assert False

    def objs_Starred(self, expr: ast.Starred) -> Set[Obj]:
        value: ast.expr = expr.value
        assert False

    def objs_Name(self, expr: ast.Name) -> Set[Obj]:
        return self.sigma(self.st(str(expr.id), self.context))

    def objs_List(self, expr: ast.List) -> Set[Obj]:
        return {ListObjectInfo.obj}

    def objs_Tuple(self, expr: ast.Tuple) -> Set[Obj]:
        return {TupleObjectInfo.obj}
