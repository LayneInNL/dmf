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

from dmf.analysis.lattice import Lattice, issubset
from dmf.analysis.stack import Frame
from dmf.analysis.state import State
from dmf.analysis.value import (
    Value,
    NUM_TYPE,
    NONE_TYPE,
    BOOL_TYPE,
    STR_TYPE,
    BYTE_TYPE,
)
from dmf.py2flows.py2flows.cfg.flows import CFG


class PrettyDefaultDict(defaultdict):
    __repr__ = dict.__repr__


class Analysis:
    def __init__(self, cfg: CFG, extremal_value):
        self.flows = cfg.flows
        self.inter_flows = cfg.inter_flows
        self.extremal_label = cfg.start_block.bid
        self.extremal_value = extremal_value
        logging.debug("Extremal value is: {}".format(self.extremal_value))
        self.bot = None
        self.blocks = cfg.blocks

        self.work_list: Deque[Tuple[int, int]] = deque()
        self.analysis_list: Dict[int, Lattice] | None = None

        self.sub_cfgs: Dict[int, CFG] = cfg.sub_cfgs
        self.implicit_return_name = "19951107"

    def compute_fixed_point(self):
        self.initialize()
        self.iterate()
        self.present()

    def initialize(self):
        self.work_list.extend(self.flows)
        self.analysis_list: Dict[int, Lattice] = PrettyDefaultDict(lambda: None)
        self.analysis_list[self.extremal_label] = self.extremal_value

    def iterate(self):
        while self.work_list:
            fst_label, snd_label = self.work_list.popleft()
            transferred: Lattice | None = self.transfer(fst_label)
            old: Lattice | None = self.analysis_list[snd_label]
            if not issubset(transferred, old):
                self.analysis_list[snd_label]: Lattice = transferred.update(old)

                if self.is_call_label(snd_label):
                    label: int = snd_label
                    if self.is_func_call_label(snd_label):
                        stmt: ast.Assign = self.blocks[snd_label].stmt[0]
                        call: ast.Call = stmt.value
                        func_name: str = self.get_func_name(call)
                        label = self.get_func_label(
                            func_name, self.analysis_list[snd_label]
                        )
                    sub_cfg: CFG = self.sub_cfgs[label]
                    self.sub_cfgs.update(sub_cfg.sub_cfgs)
                    self.blocks.update(sub_cfg.blocks)
                    self.flows.update(sub_cfg.flows)
                    self.inter_flows.update(sub_cfg.inter_flows)
                    return_label = self.get_return_label(snd_label)
                    entry_label, exit_label = (
                        sub_cfg.start_block.bid,
                        sub_cfg.final_block.bid,
                    )
                    self.flows.add((snd_label, entry_label))
                    self.flows.add((exit_label, return_label))

                added_flows: List[Tuple[int, int]] = [
                    (l2, l3) for l2, l3 in self.flows if l2 == snd_label
                ]
                self.work_list.extendleft(added_flows)

    def is_call_label(self, label: int):
        for a, _, _, _ in self.inter_flows:
            if a == label:
                return True
        return False

    def is_func_call_label(self, label: int):
        if self.is_call_label(label):
            stmt: ast.stmt = self.blocks[label].stmt[0]
            if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
                return True
        return False

    def get_func_name(self, expr: ast.Call):
        if isinstance(expr.func, ast.Name):
            return expr.func.id
        else:
            assert False

    def get_assign_name(self, expr: ast.expr):
        if isinstance(expr, ast.Name):
            return expr.id
        else:
            assert False

    def get_func_label(self, name: str, lattice: Lattice):
        values: List[State] = list(lattice.values())
        state: State = values[0]
        value: Value = state.read_var_from_stack(name)
        func_labels = list(value.extract_func_type())
        assert len(func_labels) == 1
        return func_labels[0]

    def is_return_label(self, label: int):
        for _, _, _, b in self.inter_flows:
            if b == label:
                return True
        return False

    def is_func_return_label(self, label: int):
        if self.is_return_label(label):
            stmt: ast.stmt = self.blocks[label].stmt[0]
            if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
                return True
        return False

    def get_call_label(self, return_label: int):
        for a, _, _, b in self.inter_flows:
            if b == return_label:
                return a

    def get_return_label(self, call_label: int):
        for a, _, _, b in self.inter_flows:
            if a == call_label:
                return b

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

    def transfer(self, label: int) -> Lattice:
        if self.analysis_list[label] == self.bot:
            return self.bot

        return self.do_transfer(label)

    def do_transfer(self, label):
        stmt: ast.stmt = self.blocks[label].stmt[0]

        stmt_name = stmt.__class__.__name__
        handler = getattr(self, "transfer_" + stmt_name)
        return handler(label)

    def transfer_Assign(self, label):
        if self.is_func_call_label(label):
            return self.transfer_func_call(label)
        elif self.is_func_return_label(label):
            return self.transfer_func_return(label)

        stmt: ast.Assign = self.blocks[label].stmt[0]
        old: Lattice = self.analysis_list[label]
        new: Lattice = old.hybrid_copy()
        for _, state in new.items():
            value: Value = get_value(stmt.value, state)
            if len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                name: str = stmt.targets[0].id
                state.write_var_to_stack(name, value)
            else:
                assert False
        return new

    def merge(self, label, heap, context):
        return context[-1:] + (label,)

    def transfer_func_call(self, label):
        old: Lattice = self.analysis_list[label]
        new: Lattice = old.hybrid_copy()
        for context, state in old.items():
            new_context = self.merge(label, None, context)
            new[new_context] = new[context]
            del new[context]
            new[new_context].stack_go_into_new_frame()
        return new

    def transfer_func_return(self, label):
        call_label: int = self.get_call_label(label)
        call: Lattice = self.analysis_list[call_label]
        new_call: Lattice = call.hybrid_copy()
        ret: Lattice = self.analysis_list[label]
        ret_name = self.implicit_return_name
        stmt: ast.Assign = self.blocks[label].stmt[0]
        assign_name = self.get_assign_name(stmt.targets[0])
        for context, state in new_call.items():
            context_at_call = self.merge(call_label, None, context)
            return_state = ret[context_at_call]
            ret_value = return_state.read_var_from_stack(ret_name)
            state.write_var_to_stack(assign_name, ret_value)
        return new_call

    def transfer_FunctionDef(self, label):
        stmt: ast.FunctionDef = self.blocks[label].stmt[0]
        old: Lattice = self.analysis_list[label]
        new: Lattice = old.hybrid_copy()
        func_name: str = stmt.name
        for _, state in new.items():
            value = Value()
            value.inject_func_type(label)
            state.write_var_to_stack(func_name, value)

        return new

    def transfer_ClassDef(self, label):
        if self.is_call_label(label):
            old: Lattice = self.analysis_list[label]
            new: Lattice = old.hybrid_copy()
            for _, state in new.items():
                state.stack_go_into_new_frame()
            return new
        elif self.is_return_label(label):
            stmt: ast.ClassDef = self.blocks[label].stmt[0]
            call_label = self.get_call_label(label)
            call: Lattice = self.analysis_list[call_label]
            new_call: Lattice = call.hybrid_copy()
            ret: Lattice = self.analysis_list[label]
            for ret_context, ret_state in ret.items():
                class_name: str = stmt.name
                frame: Frame = ret_state.top_frame_on_stack()
                value: Value = Value()
                value.inject_class_type(call_label, frame.f_locals)
                new_call[ret_context].write_var_to_stack(class_name, value)
            return new_call

    def transfer_Pass(self, label):
        return self.analysis_list[label]

    def transfer_If(self, label):
        return self.analysis_list[label]

    def transfer_While(self, label):
        return self.analysis_list[label]

    def transfer_Return(self, label):
        old = self.analysis_list[label]
        new = old.hybrid_copy()
        stmt: ast.Return = self.blocks[label].stmt[0]
        ret_name = stmt.value.id
        for context, state in new.items():
            ret_value = state.read_var_from_stack(ret_name)
            state.write_var_to_stack(self.implicit_return_name, ret_value)
        return new


def get_value(expr: ast.expr, state: State):
    if isinstance(expr, ast.Num):
        value = Value()
        value.inject_prim_type(NUM_TYPE)
        return value
    elif isinstance(expr, ast.NameConstant):
        value = Value()
        if expr.value is None:
            value.inject_prim_type(NONE_TYPE)
        else:
            value.inject_prim_type(BOOL_TYPE)
        return value
    elif isinstance(expr, (ast.Str, ast.JoinedStr)):
        value = Value()
        value.inject_prim_type(STR_TYPE)
        return value
    elif isinstance(expr, ast.Bytes):
        value = Value()
        value.inject_prim_type(BYTE_TYPE)
    elif isinstance(expr, ast.Name):
        return state.read_var_from_stack(expr.id)
    else:
        assert False
