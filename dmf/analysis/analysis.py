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
from typing import Dict, Tuple, Deque, Set

from dmf.analysis.flows import (
    is_call_label,
    get_return_point,
    get_call_point,
    is_return_label,
    get_return_label,
    get_call_label,
    is_entry_point,
)
from dmf.analysis.helper import merge, record
from dmf.analysis.pp import (
    ProgramPoint,
    make_program_point_flow,
    make_IF,
)
from dmf.analysis.stack import Frame
from dmf.analysis.state import (
    State,
    issubset_state,
    update_state,
    STATE_BOT,
    compute_value_of_expr,
)
from dmf.analysis.value import Value, builtin_object, RETURN, FuncObj, ClsObj
from dmf.py2flows.py2flows.cfg.flows import CFG


class AnalysisDict(defaultdict):
    def __repr__(self):
        return dict.__repr__(self)


Flow = Tuple[ProgramPoint, ProgramPoint]


class Analysis:
    def __init__(self, cfg: CFG):
        self.flows = cfg.flows
        self.IF: Set[
            Tuple[ProgramPoint, ProgramPoint, ProgramPoint, ProgramPoint]
        ] = set()
        self.call_return_flows = cfg.call_return_flows
        self.extremal_label = (cfg.start_block.bid, ())
        self.extremal_value = State()
        logging.debug("Extremal value is: {}".format(self.extremal_value))
        self.blocks = cfg.blocks

        self.work_list: Deque[Flow] = deque()
        self.analysis_list: AnalysisDict[ProgramPoint, State | STATE_BOT] | None = None

        self.sub_cfgs: Dict[int, CFG] = cfg.sub_cfgs

    def compute_fixed_point(self):
        self.initialize()
        self.iterate()
        self.present()

    def initialize(self):
        # add flows to work_list
        self.work_list.extendleft(self.DELTA(self.extremal_label))
        # default init analysis_list
        self.analysis_list: AnalysisDict[
            ProgramPoint, State | STATE_BOT
        ] = AnalysisDict(lambda: STATE_BOT)
        # update extremal label
        self.analysis_list[self.extremal_label] = self.extremal_value

    def iterate(self):
        while self.work_list:
            program_point1, program_point2 = self.work_list.popleft()
            transferred: State | STATE_BOT = self.transfer(program_point1)
            old: State | STATE_BOT = self.analysis_list[program_point2]

            if not issubset_state(transferred, old):
                self.analysis_list[program_point2]: State = update_state(
                    transferred, old
                )

                self.LAMBDA(program_point2)

                added_program_points = self.DELTA(program_point2)
                print(added_program_points)
                self.work_list.extendleft(added_program_points)

    def present(self):
        for program_point, state in self.analysis_list.items():
            logging.debug(
                "Context at program point {}: {}".format(program_point, state)
            )
            logging.debug(
                "Effect at program point {}: {}".format(
                    program_point, self.transfer(program_point)
                )
            )

    def LAMBDA(self, program_point: ProgramPoint):
        label, context = program_point
        if not is_call_label(label, self.call_return_flows):
            return
        stmt = self.get_stmt_by_label(label)
        if isinstance(stmt, ast.ClassDef):
            self.LAMBDA_ClassDef(program_point)
        elif isinstance(stmt, ast.Assign):
            if isinstance(stmt.value, ast.Call):
                if isinstance(stmt.value.func, ast.Name):
                    self.LAMBDA_Name(program_point)

    def LAMBDA_ClassDef(self, program_point: ProgramPoint):
        label, context = program_point
        return_label = get_return_label(label, self.call_return_flows)
        class_cfg = self.sub_cfgs[label]
        self.flows.update(class_cfg.flows)
        self.blocks.update(class_cfg.blocks)
        self.sub_cfgs.update(class_cfg.sub_cfgs)
        entry_label, exit_label = (
            class_cfg.start_block.bid,
            class_cfg.final_block.bid,
        )
        new_ctx = merge(label, None, context)
        self.IF.add(
            make_IF(
                label,
                return_label,
                context,
                entry_label,
                exit_label,
                new_ctx,
            )
        )

    def LAMBDA_Name(self, program_point: ProgramPoint):
        label, context = program_point
        stmt = self.get_stmt_by_label(label)
        state = self.analysis_list[program_point]
        rhs_value: Value = state.read_var_from_stack(stmt.value.func.id)
        func_types = rhs_value.extract_func_types()
        self.LAMBDA_Func_Types(program_point, func_types)
        class_types = rhs_value.extract_class_types()
        self.LAMBDA_Class_Types(program_point, class_types)

    def LAMBDA_Func_Types(self, program_point: ProgramPoint, func_types: Set[FuncObj]):
        if not func_types:
            return

        label, context = program_point
        return_label = get_return_label(label, self.call_return_flows)
        new_context = merge(label, None, context)
        for func_type in func_types:
            IF = make_IF(
                label,
                return_label,
                context,
                func_type.entry_label,
                func_type.exit_label,
                new_context,
            )
            self.IF.add(IF)

    def LAMBDA_Class_Types(self, program_point: ProgramPoint, class_types: Set[ClsObj]):
        if not class_types:
            return

        for cls_type in class_types:
            self.do_class_type(program_point, cls_type)

    def do_class_type(self, program_point: ProgramPoint, class_type: ClsObj):
        label, context = program_point
        return_label = get_return_label(label, self.call_return_flows)
        init_method = class_type.get_init()
        func_types = init_method.extract_func_types()
        assert len(func_types) == 1
        new_context = merge(label, None, context)
        for func_type in func_types:
            entry_label, exit_label = func_type.entry_label, func_type.exit_label
            IF = make_IF(
                label, return_label, context, entry_label, exit_label, new_context
            )
            self.IF.add(IF)

    def DELTA(self, program_point: ProgramPoint):
        label, context = program_point
        added = []
        for fst_lab, snd_lab in self.flows:
            if label == fst_lab:
                added.append(make_program_point_flow(label, context, snd_lab, context))
        for (
            call_point,
            entry_point,
            exit_point,
            return_point,
        ) in self.IF:
            if program_point == call_point:
                added.append((call_point, entry_point))
                added.append((exit_point, return_point))
            elif program_point == exit_point:
                added.append((exit_point, return_point))
        return added

    def transfer(self, program_point: ProgramPoint) -> State | STATE_BOT:
        label, context = program_point
        if self.analysis_list[program_point] == STATE_BOT:
            return STATE_BOT

        if is_call_label(label, self.call_return_flows):
            return self.transfer_call(program_point)
        if is_entry_point(program_point, self.IF):
            return self.transfer_entry(program_point)
        if is_return_label(label, self.call_return_flows):
            return self.transfer_return(program_point)
        return self.do_transfer(program_point)

    def get_stmt_by_label(self, label):
        return self.blocks[label].stmt[0]

    def do_transfer(self, program_point: ProgramPoint) -> State:
        label, context = program_point
        stmt: ast.stmt = self.get_stmt_by_label(label)
        stmt_name: str = stmt.__class__.__name__
        handler = getattr(self, "transfer_" + stmt_name)
        return handler(program_point)

    def transfer_Assign(self, program_point: ProgramPoint) -> State:
        label, context = program_point
        stmt: ast.Assign = self.get_stmt_by_label(label)

        old: State = self.analysis_list[program_point]
        new: State = old.copy()

        rhs_value: Value = compute_value_of_expr(stmt.value, new)
        target: ast.expr = stmt.targets[0]
        if isinstance(target, ast.Name):
            name: str = target.id
            new.write_var_to_stack(name, rhs_value)
        # elif isinstance(target, ast.Attribute):
        #     assert isinstance(target.value, ast.Name)
        #     name: str = target.value.id
        #     value: Value = new.read_var_from_stack(name)
        #     field: str = target.attr
        #     heaps = value.extract_heap_types()
        #     for heap in heaps:
        #         new.write_field_to_heap(heap[0], field, rhs_value)
        else:
            assert False
        return new

    def transfer_call(self, program_point: ProgramPoint):
        old: State = self.analysis_list[program_point]
        new: State = old.copy()

        new.stack_go_into_new_frame()

        return new

    def transfer_entry(self, program_point: ProgramPoint):
        old: State = self.analysis_list[program_point]
        new: State = old.copy()
        return new

    def transfer_exit(self, program_point: ProgramPoint):
        pass

    def transfer_return(self, program_point: ProgramPoint):
        return_label, return_context = program_point
        stmt: ast.Assign = self.get_stmt_by_label(return_label)
        target: ast.expr = stmt.targets[0]
        return_state = self.analysis_list[program_point]
        new_return_state = return_state.copy()
        call_label = get_call_label(return_label, self.call_return_flows)
        call_state: State = self.analysis_list[(call_label, return_context)]
        new_call_state = call_state.copy()
        return_value = return_state.read_var_from_stack(RETURN)
        print(return_value)
        if isinstance(target, ast.Name):
            new_call_state.write_var_to_stack(target.id, return_value)
        new_call_state.heap = new_return_state.heap
        return new_call_state

    def transfer_FunctionDef(self, program_point: ProgramPoint):
        label, context = program_point
        stmt: ast.FunctionDef = self.get_stmt_by_label(label)
        func_cfg: CFG = self.sub_cfgs[label]
        self.flows.update(func_cfg.flows)
        self.blocks.update(func_cfg.blocks)
        self.sub_cfgs.update(func_cfg.sub_cfgs)
        old: State = self.analysis_list[program_point]
        new: State = old.copy()

        func_name: str = stmt.name
        entry_label, exit_label = func_cfg.start_block.bid, func_cfg.final_block.bid
        args = stmt.args

        value = Value()
        value.inject_func_type(label, entry_label, exit_label, args)

        new.write_var_to_stack(func_name, value)

        return new

    def transfer_ClassDef(self, program_point: ProgramPoint):
        label, context = program_point
        if is_call_label(label, self.call_return_flows):
            old: State = self.analysis_list[program_point]
            new: State = old.copy()
            return new
        elif is_return_label(label, self.call_return_flows):
            stmt: ast.ClassDef = self.get_stmt_by_label(label)
            call_point = get_call_point(program_point, self.IF)
            call_label = call_point[0]
            old: State = self.analysis_list[call_point]
            new: State = old.copy()
            return_state: State = self.analysis_list[program_point]

            class_name = stmt.name
            frame: Frame = return_state.top_frame_on_stack()
            value = Value()
            value.inject_class_type(
                call_label, class_name, [builtin_object], frame.f_locals
            )
            new.write_var_to_stack(class_name, value)
            return new

    def transfer_Pass(self, program_point: ProgramPoint) -> State:
        return self.analysis_list[program_point]

    def transfer_If(self, program_point: ProgramPoint) -> State:
        return self.analysis_list[program_point]

    def transfer_While(self, program_point: ProgramPoint) -> State:
        return self.analysis_list[program_point]

    def transfer_Return(self, program_point: ProgramPoint) -> State:
        label, context = program_point
        stmt: ast.Return = self.get_stmt_by_label(label)
        assert isinstance(stmt.value, ast.Name)
        ret_name: str = stmt.value.id
        old: State = self.analysis_list[program_point]
        new: State = old.copy()

        ret_value: Value = new.read_var_from_stack(ret_name)
        new.write_var_to_stack(RETURN, ret_value)
        return new
