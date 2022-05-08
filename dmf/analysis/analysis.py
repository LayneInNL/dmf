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
from __future__ import annotations

import ast
import logging
from collections import defaultdict, deque
from typing import Dict, Tuple, Deque, List

from dmf.analysis.helper import (
    is_func,
    is_class,
    merge,
    record,
    compute_value_of_expr,
)
from dmf.analysis.lattice import Lattice, LATTICE_BOT, update_lattice
from dmf.analysis.stack import Frame, new_local_ns
from dmf.analysis.state import State
from dmf.analysis.utils import (
    subset,
    implicit_return,
    self_flag,
    implicit_init_flag,
)
from dmf.analysis.value import (
    Value,
    builtin_object,
    ClsObj,
)
from dmf.py2flows.py2flows.cfg.flows import CFG


class AnalysisDict(defaultdict):
    def __repr__(self):
        return dict.__repr__(self)


class Analysis:
    def __init__(self, cfg: CFG):
        self.flows = cfg.flows
        self.call_return_flows = cfg.call_return_flows
        self.entry_exit_flows = set()
        self.extremal_label = cfg.start_block.bid
        self.extremal_value = None
        logging.debug("Extremal value is: {}".format(self.extremal_value))
        self.blocks = cfg.blocks

        self.work_list: Deque[Tuple[int, int]] = deque()
        self.analysis_list: None = None

        self.sub_cfgs: Dict[int, CFG] = cfg.sub_cfgs

    def compute_fixed_point(self):
        self.initialize()
        self.iterate()
        self.present()

    def initialize(self):
        state = State()
        initial_namespace = new_local_ns()
        initial_frame = Frame(initial_namespace, None, initial_namespace, None)
        state.push_frame_to_stack(initial_frame)
        lattice = Lattice()
        lattice[()] = state
        self.extremal_value = lattice

        # add flows to work_list
        self.work_list.extend(self.flows)
        # default init analysis_list
        self.analysis_list: AnalysisDict[int, Lattice | LATTICE_BOT] = AnalysisDict(
            lambda: LATTICE_BOT
        )
        # update extremal label
        self.analysis_list[self.extremal_label] = self.extremal_value

    def iterate(self):
        while self.work_list:
            fst_label, snd_label = self.work_list.popleft()
            transferred: Lattice | LATTICE_BOT = self.transfer(fst_label)
            old: Lattice | LATTICE_BOT = self.analysis_list[snd_label]

            if not subset(transferred, old):
                self.analysis_list[snd_label]: Lattice = update_lattice(
                    transferred, old
                )

                if self.is_call_label(snd_label):
                    logging.debug("Current snd_label: {}".format(snd_label))
                    # get sub_cfg label, so that we can add entry and exit labels on the fly
                    sub_cfg_label: int = self.get_cfg_label(snd_label)
                    sub_cfg: CFG = self.sub_cfgs[sub_cfg_label]
                    entry_label, exit_label = (
                        sub_cfg.start_block.bid,
                        sub_cfg.final_block.bid,
                    )
                    return_label: int = self.get_return_label(snd_label)
                    self.flows.add((snd_label, entry_label))
                    self.flows.add((exit_label, return_label))
                    self.sub_cfgs.update(sub_cfg.sub_cfgs)
                    self.blocks.update(sub_cfg.blocks)
                    self.flows.update(sub_cfg.flows)
                    self.call_return_flows.update(sub_cfg.call_return_flows)

                added_flows: List[Tuple[int, int]] = [
                    (l2, l3) for l2, l3 in self.flows if l2 == snd_label
                ]
                self.work_list.extendleft(added_flows)

    def get_cfg_label(self, call_label: int) -> int:
        stmt: ast.stmt = self.blocks[call_label].stmt[0]
        if isinstance(stmt, ast.ClassDef):
            return call_label
        elif isinstance(stmt, ast.Assign):
            call: ast.Call = stmt.value
            lattice: Lattice = self.analysis_list[call_label]
            if isinstance(call.func, ast.Name):
                # v = func()
                # v = class()
                name = call.func.id
                for ctx, state in lattice.items():
                    method_value = state.read_var_from_stack(name)
                    if is_func(method_value):
                        return method_value.extract_func_types()
                    elif is_class(method_value):
                        cls = method_value.extract_class_object()
                        init = cls["__init__"]
                        return init.extract_func_types()

            elif isinstance(call.func, ast.Attribute):
                for ctx, state in lattice.items():
                    v = compute_value_of_expr(call.func.value, state)
                    method = call.func.attr
                    heaps = v.extract_heap_type()
                    for hctx, cls in heaps:
                        method_value: Value = state.read_field_from_heap(
                            hctx, cls, method
                        )
                        return method_value.extract_func_types()
        else:
            assert False

    def is_call_label(self, label: int) -> bool:
        for a, _ in self.call_return_flows:
            if a == label:
                return True
        return False

    def is_return_label(self, label: int):
        for _, b in self.call_return_flows:
            if b == label:
                return True
        return False

    def get_call_label(self, return_label: int) -> int:
        for a, b in self.call_return_flows:
            if b == return_label:
                return a

    def get_return_label(self, call_label: int) -> int:
        for a, b in self.call_return_flows:
            if a == call_label:
                return b

    def is_class_func_label(self, label):
        stmt: ast.FunctionDef = self.blocks[label].stmt[0]
        positional_args = stmt.args.args
        if positional_args and isinstance(positional_args[0], ast.Name):
            if positional_args[0].arg == "self":
                return True
        return False

    def present(self):
        all_labels = set()
        logging.debug("All flows {}".format(self.flows))
        for flow in self.flows:
            all_labels.update(flow)

        for label in all_labels:
            logging.debug(
                "Context at label {}: {}".format(label, self.analysis_list[label])
            )
            logging.debug("Effect at label {}: {}".format(label, self.transfer(label)))

    def transfer(self, label: int) -> Lattice | LATTICE_BOT:
        if self.analysis_list[label] == LATTICE_BOT:
            return LATTICE_BOT

        return self.do_transfer(label)

    def do_transfer(self, label: int) -> Lattice:
        stmt: ast.stmt = self.blocks[label].stmt[0]

        stmt_name: str = stmt.__class__.__name__
        handler = getattr(self, "transfer_" + stmt_name)
        return handler(label)

    def transfer_inter_call(self, call_label):
        value_expr: ast.Call = self.blocks[call_label].stmt[0].internal
        old: Lattice = self.analysis_list[call_label]
        new: Lattice = old.copy()

        for context, state in old.items():
            new_context: Tuple = merge(call_label, None, context)
            new[new_context]: State = new[context]
            del new[context]
            new[new_context].stack_go_into_new_frame()
            if isinstance(value_expr.func, ast.Name):
                # ret = func()
                # ret = class()
                func_value: Value = compute_value_of_expr(value_expr, state)
                if is_class(func_value):
                    class_object: ClsObj = func_value.extract_class_object()
                    heap: int = record(call_label, context)
                    value: Value = Value()
                    value.inject_heap_type(heap, class_object)

                    fake_value: Value = Value()
                    fake_name: str = implicit_init_flag

                    new[new_context].write_var_to_stack(self_flag, value)
                    new[new_context].write_var_to_stack(fake_name, fake_value)
                elif is_func(func_value):
                    pass
            elif isinstance(value_expr.func, ast.Attribute):
                # ret = v.method(args)
                v: Value = compute_value_of_expr(value_expr.func.value, state)
                method = value_expr.func.attr
                heaps = v.extract_heap_types()
                for hcontext, cls in heaps:
                    method_value = state.read_field_from_heap(hcontext, cls, method)
                    new[new_context].write_var_to_stack(self_flag, v)
        return new

    def transfer_inter_return(self, return_label):
        stmt: ast.Assign = self.blocks[return_label].stmt[0]
        target: ast.expr = stmt.targets[0]

        call_label: int = self.get_call_label(return_label)
        call: Lattice = self.analysis_list[call_label]
        new_call: Lattice = call.copy()
        ret: Lattice = self.analysis_list[return_label]
        for context, state in new_call.items():
            context_at_call: Tuple = merge(call_label, None, context)
            return_state = ret[context_at_call]
            ret_name: str = implicit_return
            if return_state.stack_contains(implicit_init_flag):
                ret_name = self_flag
            ret_value = return_state.read_var_from_stack(ret_name)
            if isinstance(target, ast.Name):
                assign_name: str = target.id
                state.write_var_to_stack(assign_name, ret_value)
            elif isinstance(target, ast.Attribute):
                assert isinstance(target.value, ast.Name)
                instance: str = target.value.id
                value = state.read_var_from_stack(instance)
                field: str = target.attr
                heaps = value.extract_heap_type()
                for heap in heaps:
                    state.write_field_to_heap(heap, field, ret_value)
            state.heap = return_state.heap
        return new_call

    def transfer_Assign(self, label: int) -> Lattice:
        stmt: ast.Assign = self.blocks[label].stmt[0]
        assert len(stmt.targets) == 1

        if self.is_call_label(label):
            return self.transfer_inter_call(label)
        elif self.is_return_label(label):
            return self.transfer_inter_return(label)

        old: Lattice = self.analysis_list[label]
        new: Lattice = old.copy()

        for ctx, state in new.items():
            right_value: Value = compute_value_of_expr(stmt.value, state)
            target: ast.expr = stmt.targets[0]
            if isinstance(target, ast.Name):
                name: str = target.id
                state.write_var_to_stack(name, right_value)
            elif isinstance(target, ast.Attribute):
                assert isinstance(target.value, ast.Name)
                name: str = target.value.id
                value: Value = state.read_var_from_stack(name)
                field: str = target.attr
                heaps = value.extract_heap_types()
                for heap in heaps:
                    state.write_field_to_heap(heap[0], field, right_value)
        return new

    def transfer_FunctionDef(self, label) -> Lattice:
        stmt: ast.FunctionDef = self.blocks[label].stmt[0]
        func_cfg: CFG = self.sub_cfgs[label]
        old: Lattice = self.analysis_list[label]
        new: Lattice = old.copy()

        func_name: str = stmt.name
        entry_label, exit_label = func_cfg.start_block.bid, func_cfg.final_block.bid
        self.entry_exit_flows.add((entry_label, exit_label))
        args = stmt.args
        for _, state in new.items():
            value = Value()
            value.inject_func_type(label, entry_label, exit_label, args)
            state.write_var_to_stack(func_name, value)

        return new

    def transfer_ClassDef(self, label: int) -> Lattice:
        if self.is_call_label(label):
            old: Lattice = self.analysis_list[label]
            new: Lattice = old.copy()
            for _, state in new.items():
                state.stack_go_into_new_frame()
            return new

        elif self.is_return_label(label):
            stmt: ast.ClassDef = self.blocks[label].stmt[0]
            class_name: str = stmt.name
            call_label = self.get_call_label(label)
            call: Lattice = self.analysis_list[call_label]
            new_call: Lattice = call.copy()
            ret: Lattice = self.analysis_list[label]
            for ret_context, ret_state in ret.items():
                frame: Frame = ret_state.top_frame_on_stack()
                value: Value = Value()
                value.inject_class_type(
                    call_label,
                    class_name,
                    [
                        call[ret_context]
                        .read_var_from_stack(base_class.id)
                        .extract_class_object()
                        for base_class in stmt.bases
                    ]
                    if stmt.bases
                    else [builtin_object],
                    frame.f_locals,
                )
                new_call[ret_context].write_var_to_stack(class_name, value)
            return new_call

    def transfer_Pass(self, label: int) -> Lattice:
        return self.analysis_list[label]

    def transfer_If(self, label: int) -> Lattice:
        return self.analysis_list[label]

    def transfer_While(self, label: int) -> Lattice:
        return self.analysis_list[label]

    def transfer_Return(self, label: int) -> Lattice:
        stmt: ast.Return = self.blocks[label].stmt[0]
        assert isinstance(stmt.value, ast.Name)
        ret_name: str = stmt.value.id
        old: Lattice = self.analysis_list[label]
        new: Lattice = old.copy()

        for _, state in new.items():
            ret_value: Value = state.read_var_from_stack(ret_name)
            state.write_var_to_stack(implicit_return, ret_value)
        return new
