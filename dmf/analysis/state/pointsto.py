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

import ast
import logging
from collections import deque
from copy import deepcopy
from typing import List, Tuple, Dict, Set, Deque, Optional

from dmf.analysis.state.helpers import (
    issubset,
    union_analyses,
    PrettyDefaultDict,
    is_call_label,
    is_return_label,
)
from dmf.analysis.state.space import (
    Stack,
    Store,
    FuncTable,
    ClassTable,
    AbstractValue,
)
from dmf.py2flows.py2flows.cfg.flows import BasicBlock, CFG


def extend_inter_flows(inter_flows: Set[Tuple[int, Optional[int], Optional[int], int]]):
    new_inter_flows = {}
    for a, b, c, d in inter_flows:
        temp = [a, b, c, d]
        new_inter_flows[a] = temp
        new_inter_flows[d] = temp
    return new_inter_flows


class Components:
    # Control flow graph, it contains program points and ast nodes.
    def __init__(self):
        self.stack: Stack = Stack()
        self.store: Store = Store()
        self.func_table: FuncTable = FuncTable()
        self.class_table: ClassTable = ClassTable()


class TypeAnalysis(Components):
    def __init__(self, cfg: CFG):
        super().__init__()

        self.flows: Set[Tuple[int, int]] = cfg.flows
        self.inter_flows: Dict[
            int, List[int, Optional[int], Optional[int], int]
        ] = extend_inter_flows(cfg.inter_flows)

        self.extremal_label: int = cfg.start.bid
        # Note: passed by address
        self.extremal_value = {(): PrettyDefaultDict()}
        # Use None as Bottom
        self.bot = None

        # used for computing
        self.blocks: Dict[int, BasicBlock] = cfg.blocks
        self.func_cfgs: Dict[Tuple[str, int], (List[str, ast.AST], CFG)] = cfg.func_cfgs
        self.class_cfgs: Dict[Tuple[str, int], CFG] = cfg.class_cfgs

        self.work_list = None
        self.analysis_list = None

    def compute_fixed_point(self) -> None:
        self.initialize()
        self.iterate()
        self.present()

    def initialize(self) -> None:
        # WorkList W
        # lift (fst_label, snd_label) with context information
        self.work_list: Deque[Tuple] = deque(self.flows)
        logging.debug("work_list: {}".format(self.work_list))

        # Analysis list
        # label -> context -> lattice {{}}
        self.analysis_list: Dict[
            int, Dict[Tuple, Dict[str, AbstractValue]]
        ] = PrettyDefaultDict(lambda: self.bot)
        self.analysis_list[self.extremal_label] = self.extremal_value
        logging.debug("analysis_list: {}".format(self.analysis_list))

    def iterate(self) -> None:
        while self.work_list:
            fst_label, snd_label = self.work_list.popleft()
            logging.debug("Current flow({}, {})".format(fst_label, snd_label))

            transferred = self.transfer(fst_label)
            logging.debug("Transferred lattice: {}".format(transferred))

            if not issubset(transferred, self.analysis_list[snd_label]):
                self.analysis_list[snd_label] = union_analyses(
                    self.analysis_list[snd_label], transferred
                )

                if snd_label in self.inter_flows:
                    stmt = self.blocks[snd_label].stmt[0]
                    if snd_label == self.inter_flows[snd_label][0]:
                        if isinstance(stmt, ast.ClassDef):
                            class_name = stmt.name
                            name_label = (class_name, snd_label)
                            class_cfg = self.class_cfgs[name_label]
                            entry_label = class_cfg.start_block.bid
                            exit_label = class_cfg.final_block.bid
                            self.class_table.insert_class(
                                class_name, entry_label, exit_label
                            )

                            entry_label, exit_label = self.class_table.lookup(
                                class_name
                            )
                            self.modify_inter_flows(snd_label, entry_label, exit_label)
                            additional_flows = self.on_the_fly_flows(
                                snd_label, entry_label, exit_label
                            )
                            self.flows.update(additional_flows)
                            additional_blocks = self.on_the_fly_blocks(snd_label)
                            self.blocks.update(additional_blocks)

                # # it is either call label or return label
                # if snd_label in self.inter_flows:
                #     # call label
                #     if self.inter_flows[snd_label][0] == snd_label:
                #         stmt = self.blocks[snd_label].stmt[0]
                #         if isinstance(stmt, ast.Assign):
                #             if isinstance(stmt.value, ast.Call) and isinstance(
                #                 stmt.value.func, ast.Name
                #             ):
                #                 # function name
                #                 name: str = stmt.value.func.id
                #                 entry_label, exit_label = self.func_table.st(name)
                #
                #                 self.modify_inter_flows(
                #                     snd_label, entry_label, exit_label
                #                 )
                #
                #                 additional_flows = self.on_the_fly_flows(
                #                     snd_label, entry_label, exit_label
                #                 )
                #                 self.flows.update(additional_flows)
                #                 logging.debug("Add flows {}".format(additional_flows))
                #
                #                 additional_blocks = self.on_the_fly_blocks(snd_label)
                #                 self.blocks.update(additional_blocks)
                #                 logging.debug("Add blocks {}".format(additional_blocks))
                #         elif isinstance(stmt, ast.ClassDef):
                #             class_name: str = stmt.name
                #             name_label = (class_name, snd_label)
                #             class_cfg: CFG = self.class_cfgs[name_label]
                #             entry_label: int = class_cfg.start_block.bid
                #             exit_label: int = class_cfg.final_block.bid
                #             self.class_table.insert_class(
                #                 class_name, entry_label, exit_label
                #             )
                #             entry_label, exit_label = self.class_table.st(class_name)
                #             self.modify_inter_flows(snd_label, entry_label, exit_label)
                #
                #             additional_flows = self.on_the_fly_flows(
                #                 snd_label, entry_label, exit_label
                #             )
                #             self.flows.update(additional_flows)
                #             logging.debug("Add flows {}".format(additional_flows))
                #
                #             additional_blocks = self.on_the_fly_blocks(snd_label)
                #             self.blocks.update(additional_blocks)
                #             logging.debug("Add blocks {}".format(additional_blocks))

                # add related flows to work_list
                added_flows = [(l2, l3) for l2, l3 in self.flows if l2 == snd_label]
                self.work_list.extendleft(added_flows)

    def present(self) -> None:
        all_labels = set()
        for flow in self.flows:
            all_labels.update(flow)

        mfp_content = {}
        mfp_effect = {}
        for label in all_labels:
            mfp_content[label] = self.analysis_list[label]
            mfp_effect[label] = self.transfer(label)

        for label in all_labels:
            logging.debug(
                "content label: {}, value:\n {}".format(label, mfp_content[label])
            )
            logging.debug(
                "effect label: {}, value:\n {}".format(label, mfp_effect[label])
            )

    def merge(self, label, heap_contexts, context):
        return context[-1:] + (label,)

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
                func_objs = self.sigma(self.st(name, self.context))
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
            func_objs = self.sigma(self.st(name, self.context))
            assert len(func_objs) == 1
            for obj in func_objs:
                name_label = (name, obj[0])
                blocks.update(self.func_cfgs[name_label][1].blocks)
        elif isinstance(stmt, ast.ClassDef):
            name: str = stmt.name
            name_label = (name, call_label)
            blocks.update(self.class_cfgs[name_label].blocks)

        return blocks

    # transfer function: Remember (l - kill) + gen
    def transfer(self, label):
        if not self.analysis_list[label]:
            return self.bot

        stmt: ast.stmt = self.blocks[label].stmt[0]
        if label in self.inter_flows:
            if is_call_label(self.inter_flows, label):
                if isinstance(stmt, ast.Assign):
                    return self.type_function_call(label)
                elif isinstance(stmt, ast.ClassDef):
                    return self.transfer_class_call(label)
            # elif is_entry_label(self.inter_flows, label):
            #     pass
            # elif is_exit_label(self.inter_flows, label):
            #     if isinstance(stmt, ast.Return):
            #         return self.type_function_exit(label)
            #     else:
            #         return self.type_class_exit(label)
            elif is_return_label(self.inter_flows, label):
                if isinstance(stmt, ast.Assign):
                    return self.type_function_exit(label)
                elif isinstance(stmt, ast.ClassDef):
                    return self.transfer_class_return(label)

        method = "transfer_" + stmt.__class__.__name__
        handler = getattr(self, method)
        return handler(label)

    # enter into new function
    # def type_function_call(self, label: int):
    #     new_analysis = PrettyDefaultDict(lambda: None)
    #     for context, old in self.analysis_list[label].items():
    #         effects = PrettyDefaultDict(set)
    #         transferred: Lattice = transform(effects)
    #         old: Lattice = new_empty_lattice()
    #         new = union_two_lattices_in_transfer(old, transferred)
    #         new_context = merge_dynamic(label, None, context)
    #         new_analysis[new_context] = new
    #
    #     return new_analysis
    #
    # def type_class_call(self, label: int):
    #     effects = []
    #     transferred: Lattice = transform(effects)
    #     old: Lattice = new_empty_lattice()
    #     new = union_two_lattices_in_transfer(old, transferred)
    #     return new
    #
    # def type_function_return(self, label: int):
    #     effects = []
    #     # left name in assign
    #     stmt = self.blocks[label].stmt[0]
    #     left_name: str = stmt.targets[0].id
    #     # right objs in pass through assign
    #     right_objs = self.blocks[label].pass_through_value
    #     effects.append((left_name, right_objs))
    #     transferred: Lattice = transform(effects)
    #
    #     call_label: int = self.inter_flows[label][0]
    #     call = self.analysis_list[call_label]
    #     new = union_two_lattices_in_transfer(call, transferred)
    #     return new
    #
    # def type_function_exit(self, label: int):
    #     effects = []
    #     name: str = self.blocks[label].stmt[0].value.id
    #     return_label: int = self.inter_flows[label][-1]
    #     self.blocks[return_label].pass_through_value = self.sigma(
    #         self.st(name, self.context)
    #     )
    #     old: Lattice = self.analysis_list[label]
    #     transferred: Lattice = transform(effects)
    #     new: Lattice = union_two_lattices_in_transfer(old, transferred)
    #     return new
    #
    # # id function
    # def type_class_exit(self, label: int):
    #     effects = []
    #     transferred = transform(effects)
    #     old = self.analysis_list[label]
    #     new = union_two_lattices_in_transfer(old, transferred)
    #     return new
    #
    def transfer_class_return(self, label: int):
        stmt: ast.ClassDef = self.blocks[label].stmt[0]
        class_name: str = stmt.name

        frame = self.stack.top()
        fields = {}
        for field_name, field_value in frame.items():
            fields[field_name] = field_value

        self.stack.pop()

        call_label: int = self.inter_flows[label][0]
        call_context = self.analysis_list[call_label]

        abstract_value = AbstractValue()
        abstract_value.inject_class(class_name, fields)
        self.stack.insert_var(class_name, abstract_value)

        new_analysis = PrettyDefaultDict(lambda: None)
        for context, old in call_context:
            copied = deepcopy(old)
            copied[class_name] = abstract_value
            new_analysis[context] = copied

        return new_analysis

    def transfer_FunctionDef(self, label: int):
        stmt: ast.FunctionDef = self.blocks[label].stmt[0]
        function_name = stmt.name

        func_cfg = self.func_cfgs[(function_name, label)]
        entry_label = func_cfg[1].start_block.bid
        exit_label = func_cfg[1].final_block.bid
        self.func_table.insert_func(function_name, entry_label, exit_label)
        logging.debug(
            "Add ({} {} {}) to function table".format(
                function_name, entry_label, exit_label
            )
        )

        new_analysis = PrettyDefaultDict(lambda: None)
        abstract_value = AbstractValue()
        abstract_value.inject_heap_context(label)
        self.stack.insert_var(function_name, abstract_value)
        for context, old in self.analysis_list[label].items():
            copied = deepcopy(old)
            copied[function_name] = abstract_value
            new_analysis[context] = copied

        return new_analysis

    def transfer_class_call(self, label: int):
        # stmt: ast.ClassDef = self.blocks[label].stmt[0]
        # class_name = stmt.name

        new_analysis = PrettyDefaultDict(lambda: None)
        for context, old in self.analysis_list[label].items():
            # new_context = self.merge(label, None, context)
            new_analysis[context] = PrettyDefaultDict(lambda: None)
        self.stack.add_frame()
        return new_analysis

    def transfer_Assign(self, label):
        stmt: ast.Assign = self.blocks[label].stmt[0]
        name = None
        if isinstance(stmt.targets[0], ast.Name):
            name = stmt.targets[0].id
        elif isinstance(stmt.targets[0], ast.Attribute):
            assert False
        elif isinstance(stmt.targets[0], ast.Subscript):
            assert False
        elif isinstance(stmt.targets[0], ast.Tuple):
            assert False
        assert name is not None

        new_analysis = PrettyDefaultDict(lambda: None)
        value = self.get_abstract_value(stmt.value)
        self.stack.insert_var(name, value)
        for context, old in self.analysis_list[label].items():
            copied = deepcopy(old)
            copied[name] = value
            new_analysis[context] = copied
        return new_analysis

    def transfer_While(self, label: int):
        return self.transfer_Pass(label)

    def transfer_If(self, label: int):
        return self.transfer_Pass(label)

    def transfer_Pass(self, label: int):
        new_analysis = PrettyDefaultDict(lambda: None)
        for context, old in self.analysis_list[label].items():
            copied = deepcopy(old)
            new_analysis[context] = copied
        return new_analysis

    def get_abstract_value(self, expr: ast.expr):
        logging.debug("stack: {}".format(self.stack.stack))
        abstract_value = AbstractValue()
        if isinstance(expr, ast.Num):
            abstract_value.inject_num()
            return abstract_value
        elif isinstance(expr, ast.NameConstant):
            if expr.value is None:
                abstract_value.inject_none()
                return abstract_value
            else:
                abstract_value.inject_bool()
                return abstract_value
        elif isinstance(expr, ast.Name):
            value = self.stack.lookup(expr.id)
            return deepcopy(value)
        elif isinstance(expr, (ast.Str, ast.FormattedValue, ast.JoinedStr)):
            abstract_value.inject_str()
            return abstract_value
        else:
            assert False
