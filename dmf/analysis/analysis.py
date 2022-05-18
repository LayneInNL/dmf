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
import builtins
import logging
import os.path
from collections import defaultdict, deque
from typing import Dict, Tuple, Deque, Set
from dmf.log.logger import logger

from dmf.analysis.ctx_util import merge, record
from dmf.analysis.flow_util import (
    ProgramPoint,
    Flow,
    Inter_Flow,
    Lab,
    Basic_Flow,
)
from dmf.analysis.value import Module, Value, InsType, NoneType, Bool, Int
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
    RETURN_FLAG,
    FuncType,
    ClsType,
    INIT_FLAG,
    SELF_FLAG,
    INIT_FLAG_VALUE,
)
from dmf.flows import CFG, construct_CFG


class Base:
    def __init__(self, entry_file_path: str):

        cfg: CFG = construct_CFG(entry_file_path)
        # call them to builtins
        builtins.flows.update(cfg.flows)
        builtins.call_return_flows.update(cfg.call_return_flows)
        builtins.blocks.update(cfg.blocks)
        builtins.sub_cfgs.update(cfg.sub_cfgs)

        self.flows: Set[Basic_Flow] = builtins.flows
        self.call_return_flows: Set[Basic_Flow] = builtins.call_return_flows
        self.blocks = builtins.blocks
        self.sub_cfgs: Dict[Lab, CFG] = builtins.sub_cfgs
        self.IF: Set[Inter_Flow] = set()
        self.extremal_point: ProgramPoint = (cfg.start_block.bid, ())
        self.final_point: ProgramPoint = (cfg.final_block.bid, ())

        # working directory for the analyzed project
        # mimic current working directory
        self.work_dir = os.path.dirname(entry_file_path)
        self.main_file = entry_file_path
        # mimic sys.modules
        self.proj_work_modules = {}
        # mimic sys.path
        self.proj_work_path = []
        self.proj_work_path.append(self.work_dir)

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
        self.call_return_flows.update(cfg.call_return_flows)

    def DELTA(self, program_point: ProgramPoint):
        added = []
        added += self.DELTA_basic_flow(program_point)
        added += self.DELTA_call_flow(program_point)
        added += self.DELTA_exit_flow(program_point)
        return added

    def DELTA_basic_flow(self, program_point: ProgramPoint):
        added = []
        label, context = program_point
        for fst_lab, snd_lab in self.flows:
            if label == fst_lab:
                added.append(((label, context), (snd_lab, context)))
        return added

    def DELTA_call_flow(self, program_point: ProgramPoint):
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
    def __init__(self, file_path, module_ns):
        file = file_path
        super().__init__(file)
        self.self_info: Dict[ProgramPoint, Tuple[int, str | None, ClsType | None]] = {}
        self.work_list: Deque[Flow] = deque()
        self.analysis_list: None = None
        self.analysis_effect_list = {}
        self.extremal_value: State = State(ns=module_ns)

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
            logging.debug(
                "Lattice at {} is {}".format(
                    program_point1, self.analysis_list[program_point1]
                )
            )
            if not issubset_state(transferred, old):
                self.analysis_list[program_point2]: State = update_state(
                    transferred, old
                )

                self.LAMBDA(program_point2)
                added_program_points = self.DELTA(program_point2)
                self.work_list.extendleft(added_program_points)

    def present(self):
        for program_point, state in self.analysis_list.items():
            logger.info("Context at program point {}: {}".format(program_point, state))
            self.analysis_effect_list[program_point] = self.transfer(program_point)
            logger.info(
                "Effect at program point {}: {}".format(
                    program_point, self.analysis_effect_list[program_point]
                )
            )

    # based on current program point, update self.IF
    def LAMBDA(self, program_point: ProgramPoint) -> None:
        call_lab, ctx = program_point

        # we are only interested in call labels
        if not self.is_call_label(call_lab):
            return

        stmt = self.get_stmt_by_label(call_lab)
        # class
        if isinstance(stmt, ast.ClassDef):
            self.LAMBDA_ClassDef(program_point)
        # procedural call
        elif isinstance(stmt, ast.Call):
            func = stmt.func
            if isinstance(func, ast.Name):
                self.LAMBDA_Name(program_point, func.id)
            elif isinstance(func, ast.Attribute):
                attr: str = func.attr
                state = self.analysis_list[program_point]
                # get abstract value of receiver object
                receiver_value = compute_value_of_expr(program_point, func.value, state)
                self.LAMBDA_Attribute(program_point, receiver_value, attr)
        else:
            assert False

    def LAMBDA_Attribute(
        self, program_point: ProgramPoint, receiver_value: Value, attr: str
    ):
        for lab, typ in receiver_value:
            if isinstance(typ, ClsType):
                self.lambda_class_init(program_point, typ)
            elif isinstance(typ, FuncType):
                self.lambda_func_call(program_point, typ)
            elif isinstance(typ, InsType):
                self.lambda_method_call(program_point, typ, attr)
            else:
                assert False

    # deal with cases such as class xxx
    def LAMBDA_ClassDef(self, program_point: ProgramPoint):
        call_lab, call_ctx = program_point
        return_lab = self.get_return_label(call_lab)
        cfg = self.sub_cfgs[call_lab]
        self.add_sub_cfg(cfg)
        self.IF.add(
            (
                (call_lab, call_ctx),
                (cfg.start_block.bid, call_ctx),
                (cfg.final_block.bid, call_ctx),
                (return_lab, call_ctx),
            )
        )

    # deal with cases such as name()
    def LAMBDA_Name(self, program_point: ProgramPoint, name: str):
        call_lab, call_ctx = program_point
        state = self.analysis_list[program_point]
        # get abstract value of name
        value: Value = state.read_var_from_stack(name)
        for lab, typ in value:
            if isinstance(typ, ClsType):
                self.lambda_class_init(program_point, typ)
            elif isinstance(typ, FuncType):
                self.lambda_func_call(program_point, typ)
            else:
                logger.warn(typ)
                assert False

    def lambda_class_init(self, program_point, typ: ClsType, attr: str = "__init__"):
        call_lab, call_ctx = program_point
        return_lab = self.get_return_label(call_lab)
        init_funcs = typ.get_attribute(attr)
        for _, init_func in init_funcs:
            if isinstance(init_func, FuncType):
                entry_lab, exit_lab = init_func.get_code()
                inter_flow = (
                    (call_lab, call_ctx),
                    (entry_lab, call_ctx),
                    (exit_lab, call_ctx),
                    (return_lab, call_ctx),
                )
                self.IF.add(inter_flow)
                heap = record(call_lab, call_ctx)
                self.self_info[(entry_lab, call_ctx)] = (heap, INIT_FLAG, typ)
            else:
                logger.warn(init_func)
                assert False

    # instance.method(self)
    def lambda_method_call(
        self, program_point: ProgramPoint, ins_type: InsType, attr: str
    ):
        # call stuff
        call_lab, call_ctx = program_point
        # return label
        return_lab = self.get_return_label(call_lab)
        # call state to retrieve heap attributes
        call_state: State = self.analysis_list[program_point]
        # heap of instance
        heap = ins_type.get_heap()
        attr_value: Value = call_state.read_field_from_heap(heap, attr)
        for _, typ in attr_value:
            if isinstance(typ, FuncType):
                new_ctx = merge(call_lab, heap, call_ctx)
                entry_lab, exit_lab = typ.get_code()
                inter_flow = (
                    (call_lab, call_ctx),
                    (entry_lab, new_ctx),
                    (exit_lab, new_ctx),
                    (return_lab, call_ctx),
                )
                self.IF.add(inter_flow)
                heap = record(call_lab, call_ctx)
                self.self_info[(entry_lab, call_ctx)] = (heap, "", None)
            elif isinstance(typ, ClsType):
                self.lambda_class_init(program_point, typ)
            else:
                logger.warn(typ)
                assert False

    def lambda_func_call(self, program_point: ProgramPoint, typ: FuncType):
        call_lab, call_ctx = program_point
        return_lab = self.get_return_label(call_lab)
        entry_lab, exit_lab = typ.get_code()
        new_ctx = merge(call_lab, None, call_ctx)
        inter_flow = (
            (call_lab, call_ctx),
            (entry_lab, new_ctx),
            (exit_lab, new_ctx),
            (return_lab, call_ctx),
        )
        self.IF.add(inter_flow)

    def transfer(self, program_point: ProgramPoint) -> State | STATE_BOT:
        logging.debug(f"Transfer {program_point}")

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

        rhs_value = compute_value_of_expr(program_point, stmt.value, new)
        assert len(stmt.targets) == 1
        target: ast.expr = stmt.targets[0]
        if isinstance(target, ast.Name):
            lhs_name: str = target.id
            new.write_var_to_stack(lhs_name, rhs_value)
        elif isinstance(target, ast.Attribute):
            assert isinstance(target.value, ast.Name)
            lhs_name: str = target.value.id
            value: Value = new.read_var_from_stack(lhs_name)
            field: str = target.attr
            for lab, typ in value:
                if isinstance(typ, InsType):
                    new.write_field_to_heap(typ.get_heap(), field, rhs_value)
                elif isinstance(typ, ClsType):
                    typ.setattr(field, rhs_value)
                elif isinstance(typ, FuncType):
                    typ.setattr(field, rhs_value)
                elif isinstance(typ, (Int, Bool, NoneType)):
                    typ.setattr(field, rhs_value)
                else:
                    assert False
        else:
            assert False
        return new

    def transfer_call(self, program_point: ProgramPoint):
        call_lab, call_ctx = program_point
        stmt: ast.stmt = self.get_stmt_by_label(call_lab)
        if isinstance(stmt, (ast.ClassDef, ast.Call)):
            old: State = self.analysis_list[program_point]
            new: State = old.copy()
            new.stack_exec_in_new_ns()
            return new
        else:
            assert False

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
            value = Value()
            ins_type = InsType(heap)
            value.inject_heap_type(heap, ins_type)
            new.write_var_to_stack(SELF_FLAG, value)
            if init_flag:
                # write the init flag to stack
                new.write_var_to_stack(INIT_FLAG, INIT_FLAG_VALUE)
                # write cls_obj to heap so that we can retrieve class type
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

            call_label = self.get_call_label(return_lab)
            call_state: State = self.analysis_list[(call_label, return_ctx)]
            # get a copy of stack
            new_call_state = call_state.copy()

            return_value = return_state.read_var_from_stack(RETURN_FLAG)
            # write value to name
            new_call_state.write_var_to_stack(stmt.id, return_value)
            new_call_state.heap = new_return_state.heap
            return new_call_state
        else:
            assert False

    def transfer_Import(self, program_point: ProgramPoint):
        lab, ctx = program_point
        old: State = self.analysis_list[program_point]
        new: State = old.copy()
        stmt: ast.Import = self.get_stmt_by_label(lab)
        module_name = stmt.names[0].name
        as_name = stmt.names[0].asname
        mod = builtins.import_module(module_name)
        value = Value()
        if as_name is None:
            # no asname
            value.inject_module_type(module_name, mod)
            new.write_var_to_stack(module_name, value)
        else:
            value.inject_module_type(as_name, mod)
            new.write_var_to_stack(as_name, value)
        logging.debug("Import module {}".format(mod))
        return new

    def transfer_ImportFrom(self, program_point: ProgramPoint):
        lab, ctx = program_point
        old: State = self.analysis_list[program_point]
        new: State = old.copy()
        stmt: ast.ImportFrom = self.get_stmt_by_label(lab)
        module_name = "" if stmt.module is None else stmt.module
        dot_number = "." * stmt.level
        package = new.read_var_from_stack("__package__")
        mod = builtins.import_module(
            name=dot_number + module_name,
            package=package,
        )
        logging.debug("ImportFrom module {}".format(mod))
        aliases = stmt.names
        for alias in aliases:
            imported_name = alias.name
            imported_value = mod.read_var_from_module(imported_name)
            if alias.asname is None:
                new.write_var_to_stack(imported_name, imported_value)
            else:
                new.write_var_to_stack(alias.asname, imported_value)
        return new

    def transfer_ClassDef_return(self, program_point: ProgramPoint):
        # return stuff
        return_lab, return_ctx = program_point
        # stmt
        stmt: ast.ClassDef = self.get_stmt_by_label(return_lab)
        # return state
        return_state: State = self.analysis_list[program_point]

        # call point
        call_point = self.get_call_point(program_point)

        # old and new state
        old: State = self.analysis_list[call_point]
        new: State = old.copy()

        # class name
        cls_name = stmt.name
        # class frame
        frame: Frame = return_state.top_frame_on_stack()
        # abstract value for class
        value = Value()
        cls_type = ClsType(frame.f_locals)
        # inject namespace
        value.inject_cls_type(call_point[0], cls_type)
        # write to stack
        new.write_var_to_stack(cls_name, value)
        # return new state
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

        value = Value()
        func_type = FuncType(func_name, entry_lab, exit_lab)
        value.inject_func_type(lab, func_type)

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
        # get return value
        # if it's init, return self
        if new.stack_contains(INIT_FLAG):
            value = new.read_var_from_stack(SELF_FLAG)
        new.write_var_to_stack(RETURN_FLAG, value)
        return new
