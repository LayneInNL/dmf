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
    ProgramPoint,
    Flow,
    Inter_Flow,
    Lab,
    Basic_Flow,
)
from dmf.analysis.helper import merge, record
from dmf.analysis.stack import Frame
from dmf.analysis.state import (
    State,
    issubset_state,
    update_state,
    STATE_BOT,
    compute_value_of_expr,
)
from dmf.analysis.value import (
    Value,
    builtin_object,
    RETURN_FLAG,
    FuncObj,
    ClsObj,
    INIT_FLAG,
    SELF_FLAG,
    INIT_FLAG_VALUE,
)
from dmf.py2flows.py2flows.cfg.flows import CFG


class Base:
    def __init__(self, cfg: CFG):
        self.flows: Set[Basic_Flow] = cfg.flows
        self.IF: Set[Inter_Flow] = set()
        self.call_return_flows: Set[Basic_Flow] = cfg.call_return_flows
        self.extremal_point: ProgramPoint = (cfg.start_block.bid, ())
        self.extremal_value: State = State()
        self.blocks = cfg.blocks
        self.sub_cfgs: Dict[Lab, CFG] = cfg.sub_cfgs

    def get_stmt_by_label(self, label: Lab):
        return self.blocks[label].stmt[0]

    def is_call_label(self, label: Lab):
        for call_label, _ in self.call_return_flows:
            if label == call_label:
                return True
        return False

    def is_entry_point(self, program_point: ProgramPoint):
        for _, entry_point, _, _ in self.IF:
            if program_point == entry_point:
                return True
        return False

    def is_return_label(self, label):
        for _, return_label in self.call_return_flows:
            if label == return_label:
                return True
        return False

    def get_call_label(self, label):
        for call_label, return_label in self.call_return_flows:
            if label == return_label:
                return call_label

    def get_call_point(self, program_point):
        for call_point, _, _, return_point in self.IF:
            if program_point == return_point:
                return call_point

    def get_return_label(self, label):
        for call_label, return_label in self.call_return_flows:
            if label == call_label:
                return return_label

    def add_sub_cfg(self, cfg: CFG):
        self.blocks.update(cfg.blocks)
        self.flows.update(cfg.flows)
        self.sub_cfgs.update(cfg.sub_cfgs)

    def DELTA(self, program_point: ProgramPoint):
        added = []
        added += self.DELTA_basic_flow(program_point)
        added += self.DELTA_call_flow(program_point)
        added += self.DELTA_exit_flow(program_point)
        return added

    def DELTA_basic_flow(self, program_point):
        added = []
        label, context = program_point
        for fst_lab, snd_lab in self.flows:
            if label == fst_lab:
                added.append(((label, context), (snd_lab, context)))
        return added

    def DELTA_call_flow(self, program_point):
        added = []
        for (
            call_point,
            entry_point,
            exit_point,
            return_point,
        ) in self.IF:
            if program_point == call_point:
                added.append((call_point, entry_point))
                added.append((exit_point, return_point))
        return added

    def DELTA_exit_flow(self, program_point):
        added = []
        for (
            _,
            _,
            exit_point,
            return_point,
        ) in self.IF:
            if program_point == exit_point:
                added.append((exit_point, return_point))
        return added


class Analysis(Base):
    def __init__(self, cfg: CFG):
        super().__init__(cfg)
        self.self_info: Dict[ProgramPoint, Tuple[int, str | None, ClsObj | None]] = {}
        self.work_list: Deque[Flow] = deque()
        self.analysis_list: defaultdict[ProgramPoint, State | STATE_BOT] | None = None

    def compute_fixed_point(self):
        self.initialize()
        self.iterate()
        self.present()

    def initialize(self):
        # add flows to work_list
        self.work_list.extendleft(self.DELTA(self.extremal_point))
        # default init analysis_list
        self.analysis_list: defaultdict[ProgramPoint, State | STATE_BOT] = defaultdict(
            lambda: STATE_BOT
        )
        # update extremal label
        self.analysis_list[self.extremal_point] = self.extremal_value

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

    # based on current program point, update self.IF
    def LAMBDA(self, program_point: ProgramPoint) -> None:
        call_lab, ctx = program_point

        # we are only interested in call labels
        if not self.is_call_label(call_lab):
            return
        return_lab = self.get_return_label(call_lab)
        stmt = self.get_stmt_by_label(call_lab)
        # class
        if isinstance(stmt, ast.ClassDef):
            self.LAMBDA_ClassDef(program_point)
        # procedural call
        elif isinstance(stmt, ast.Call):
            if isinstance(stmt.func, ast.Name):
                self.LAMBDA_Name(program_point, stmt.func.id)
            elif isinstance(stmt.func, ast.Attribute):
                state = self.analysis_list[program_point]
                receiver_value = compute_value_of_expr(stmt.func.value, state)
                heaps = receiver_value.extract_heap_types()
                # assume receiver is a heap object for now.
                attr = stmt.func.attr
                for heap in heaps:
                    method = state.read_field_from_heap(heap, attr)
                    func_types = method.extract_func_types()
                    assert len(func_types) == 1
                    new_ctx = merge(call_lab, heap, ctx)
                    for func_type in func_types:
                        inter_flow = (
                            (call_lab, ctx),
                            (func_type.entry_label, new_ctx),
                            (func_type.exit_label, new_ctx),
                            (return_lab, ctx),
                        )
                        self.IF.add(inter_flow)
                        self.self_info[(func_type.entry_label, new_ctx)] = (
                            heap,
                            None,
                            None,
                        )
        else:
            assert False

    def LAMBDA_ClassDef(self, program_point: ProgramPoint):
        call_lab, call_ctx = program_point
        return_lab = self.get_return_label(call_lab)
        class_cfg = self.sub_cfgs[call_lab]
        self.add_sub_cfg(class_cfg)
        new_ctx = merge(call_lab, None, call_ctx)
        self.IF.add(
            (
                (call_lab, call_ctx),
                (class_cfg.start_block.bid, new_ctx),
                (class_cfg.final_block.bid, new_ctx),
                (return_lab, call_ctx),
            )
        )

    def LAMBDA_Name(self, program_point: ProgramPoint, name: str):
        state = self.analysis_list[program_point]
        # get abstract value of name
        value: Value = state.read_var_from_stack(name)
        # get func_types
        func_types = value.extract_func_types()
        # deal with func types
        self.LAMBDA_Func_Types(program_point, func_types)
        # get class types
        class_types = value.extract_class_types()
        # deal with class types
        self.LAMBDA_Class_Types(program_point, class_types)

    def LAMBDA_Func_Types(self, program_point: ProgramPoint, func_types: Set[FuncObj]):
        for func_type in func_types:
            self.build_inter_flow_for_func_type(program_point, func_type)

    def build_inter_flow_for_func_type(
        self, program_point: ProgramPoint, func_type: FuncObj
    ):
        call_lab, call_ctx = program_point
        entry_lab = func_type.entry_label
        exit_lab = func_type.exit_label
        return_lab = self.get_return_label(call_lab)
        new_ctx = merge(call_lab, None, call_ctx)
        inter_flow = (
            (call_lab, call_ctx),
            (entry_lab, new_ctx),
            (exit_lab, new_ctx),
            (return_lab, call_ctx),
        )
        self.IF.add(inter_flow)

    def LAMBDA_Class_Types(self, program_point: ProgramPoint, class_types: Set[ClsObj]):
        for cls_type in class_types:
            self.build_inter_flow_for_class_type(program_point, cls_type)

    def build_inter_flow_for_class_type(
        self, program_point: ProgramPoint, class_type: ClsObj
    ):
        call_lab, call_ctx = program_point
        return_lab = self.get_return_label(call_lab)
        init_method = class_type.get_init()
        func_types = init_method.extract_func_types()
        assert len(func_types) == 1
        new_ctx = merge(call_lab, None, call_ctx)
        for func_type in func_types:
            entry_lab, exit_lab = func_type.entry_label, func_type.exit_label
            inter_flow = (
                (call_lab, call_ctx),
                (entry_lab, new_ctx),
                (exit_lab, new_ctx),
                (return_lab, call_ctx),
            )
            self.IF.add(inter_flow)
            heap = record(call_lab, call_ctx)
            self.self_info[(entry_lab, new_ctx)] = (heap, INIT_FLAG, class_type)

    def transfer(self, program_point: ProgramPoint) -> State | STATE_BOT:
        lab, _ = program_point
        if self.analysis_list[program_point] == STATE_BOT:
            return STATE_BOT

        if self.is_call_label(lab):
            return self.transfer_call(program_point)
        if self.is_entry_point(program_point):
            return self.transfer_entry(program_point)
        if self.is_return_label(lab):
            return self.transfer_return(program_point)
        return self.do_transfer(program_point)

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
        elif isinstance(target, ast.Attribute):
            assert isinstance(target.value, ast.Name)
            name: str = target.value.id
            value: Value = new.read_var_from_stack(name)
            field: str = target.attr
            heaps = value.extract_heap_types()
            for heap in heaps:
                new.write_field_to_heap(heap, field, rhs_value)
        else:
            assert False
        return new

    def transfer_call(self, program_point: ProgramPoint):
        call_lab, call_ctx = program_point
        stmt: ast.stmt = self.get_stmt_by_label(call_lab)
        if isinstance(stmt, ast.ClassDef):
            old: State = self.analysis_list[program_point]
            new: State = old.copy()
            new.stack_go_into_new_frame()
            return new
        elif isinstance(stmt, ast.Call):
            old: State = self.analysis_list[program_point]
            new: State = old.copy()
            new.stack_go_into_new_frame()
            return new

    def transfer_entry(self, program_point: ProgramPoint):
        entry_lab, entry_ctx = program_point
        stmt = self.get_stmt_by_label(entry_lab)
        old: State = self.analysis_list[program_point]
        new: State = old.copy()

        if isinstance(stmt, ast.Pass):
            return new

        # is self.self_info[program_point] is not None, it means
        # this is a class method call
        if program_point in self.self_info:
            # heap is heap, flag denotes if it's init method
            heap, init_flag, cls_obj = self.self_info[program_point]
            heap_value = Value(heap_type=heap)
            new.write_var_to_stack(SELF_FLAG, heap_value)
            if init_flag:
                new.write_var_to_stack(INIT_FLAG, INIT_FLAG_VALUE)
                new.add_heap_and_cls(heap, cls_obj)
        return new

    def transfer_return(self, program_point: ProgramPoint):
        return_lab, return_ctx = program_point
        stmt: ast.stmt = self.get_stmt_by_label(return_lab)

        if isinstance(stmt, ast.ClassDef):
            return self.transfer_ClassDef_return(program_point)
        elif isinstance(stmt, ast.Name):
            return_state = self.analysis_list[program_point]
            # get a copy of heap
            new_return_state = return_state.copy()

            call_label = self.get_call_label(return_lab, self.call_return_flows)
            call_state: State = self.analysis_list[(call_label, return_ctx)]
            # get a copy of stack
            new_call_state = call_state.copy()

            # get return value
            return_value = return_state.read_var_from_stack(RETURN_FLAG)
            # if it's init, return self
            if return_state.stack_contains(INIT_FLAG):
                return_value = return_state.read_var_from_stack(SELF_FLAG)

            # write value to name
            new_call_state.write_var_to_stack(stmt.id, return_value)
            new_call_state.heap = new_return_state.heap
            return new_call_state
        else:
            assert False

    def transfer_ClassDef_return(self, program_point: ProgramPoint):
        return_state: State = self.analysis_list[program_point]
        return_lab, return_ctx = program_point
        stmt: ast.ClassDef = self.get_stmt_by_label(return_lab)

        call_point = self.get_call_point(program_point)
        call_label = call_point[0]

        old: State = self.analysis_list[call_point]
        new: State = old.copy()

        class_name = stmt.name
        frame: Frame = return_state.top_frame_on_stack()
        value = Value()
        value.inject_class_type(
            call_label, class_name, [builtin_object], frame.f_locals
        )
        new.write_var_to_stack(class_name, value)
        return new

    def transfer_FunctionDef(self, program_point: ProgramPoint):
        lab, _ = program_point
        stmt: ast.FunctionDef = self.get_stmt_by_label(lab)
        func_cfg: CFG = self.sub_cfgs[lab]
        self.add_sub_cfg(func_cfg)

        old: State = self.analysis_list[program_point]
        new: State = old.copy()

        func_name: str = stmt.name
        entry_lab, exit_lab = func_cfg.start_block.bid, func_cfg.final_block.bid
        args = stmt.args

        value = Value()
        value.inject_func_type(lab, entry_lab, exit_lab, args)

        new.write_var_to_stack(func_name, value)

        return new

    def transfer_Pass(self, program_point: ProgramPoint) -> State:
        return self.analysis_list[program_point]

    def transfer_If(self, program_point: ProgramPoint) -> State:
        return self.analysis_list[program_point]

    def transfer_While(self, program_point: ProgramPoint) -> State:
        return self.analysis_list[program_point]

    def transfer_Return(self, program_point: ProgramPoint) -> State:
        lab, _ = program_point
        stmt: ast.Return = self.get_stmt_by_label(lab)

        old: State = self.analysis_list[program_point]
        new: State = old.copy()

        assert isinstance(stmt.value, ast.Name)
        name: str = stmt.value.id
        value: Value = new.read_var_from_stack(name)
        new.write_var_to_stack(RETURN_FLAG, value)
        return new
