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
from typing import Dict, Tuple, Deque, Set, List

import dmf.share
from dmf.analysis.ctx_util import merge, record
from dmf.analysis.flow_util import (
    ProgramPoint,
    Flow,
    Inter_Flow,
    Lab,
    Basic_Flow,
    Ctx,
)
from dmf.analysis.heap import analysis_heap
from dmf.analysis.prim import Int, Bool, NoneType
from dmf.analysis.stack import Frame
from dmf.analysis.state import (
    State,
    issubset_state,
    update_state,
    STATE_BOT,
    compute_value_of_expr,
)
from dmf.analysis.value import (
    InsType,
    MethodType,
    Namespace,
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
from dmf.flows import CFG
from dmf.flows.flows import BasicBlock
from dmf.log.logger import logger

empty_context = ()


class Base:
    def __init__(self, start_lab: int):

        self.flows: Set[Basic_Flow] = dmf.share.flows
        self.call_return_flows: Set[Basic_Flow] = dmf.share.call_return_flows
        self.blocks: Dict[Lab, BasicBlock] = dmf.share.blocks
        self.sub_cfgs: Dict[Lab, CFG] = dmf.share.sub_cfgs
        self.inter_flows: Set[Inter_Flow] = set()
        self.extremal_point: ProgramPoint = (start_lab, empty_context)

    def get_stmt_by_label(self, label: Lab):
        return self.blocks[label].stmt[0]

    def is_call_label(self, label: Lab):
        for call_label, _ in self.call_return_flows:
            if label == call_label:
                return True
        return False

    def is_entry_point(self, program_point: ProgramPoint):
        for _, entry_point, _, _ in self.inter_flows:
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
        for call_point, _, _, return_point in self.inter_flows:
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
        ) in self.inter_flows:
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
        ) in self.inter_flows:
            if program_point == exit_point:
                added.append((exit_point, return_point))
        return added


class Analysis(Base):
    def __init__(self, start_lab, module_name):
        super().__init__(start_lab)
        self.self_info: Dict[ProgramPoint, Tuple[InsType, str | None]] = {}
        self.work_list: Deque[Flow] = deque()
        self.analysis_list: None = None
        self.analysis_effect_list: None = None
        self.extremal_value: State = State()

        # init first frame
        global_ns = dmf.share.analysis_modules[module_name].get_namespace()
        if dmf.share.static_builtins:
            builtins_ns = dmf.share.analysis_modules["static_builtins"].get_namespace()
        else:
            builtins_ns = Namespace()
        self.extremal_value.init_first_frame(
            f_locals=global_ns, f_back=None, f_globals=global_ns, f_builtins=builtins_ns
        )

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
        self.analysis_effect_list = {}
        # update extremal label
        self.analysis_list[self.extremal_point] = self.extremal_value

    def iterate(self):
        while self.work_list:
            program_point1, program_point2 = self.work_list.popleft()
            logger.debug(
                "Current program point1 {} and lattice1 {}".format(
                    program_point1, self.analysis_list[program_point1]
                )
            )
            transferred: State | STATE_BOT = self.transfer(program_point1)
            old: State | STATE_BOT = self.analysis_list[program_point2]
            if not issubset_state(transferred, old):
                self.analysis_list[program_point2]: State = update_state(
                    transferred, old
                )
                self.LAMBDA(program_point2)
                added_program_points = self.DELTA(program_point2)
                logger.debug("added flows {}".format(added_program_points))
                self.work_list.extendleft(added_program_points)
            logger.debug(
                "Current program point2 {} and lattice2 {}".format(
                    program_point2, self.analysis_list[program_point2]
                )
            )

    def present(self):
        for program_point, state in self.analysis_list.items():
            logger.info("Context at program point {}: {}".format(program_point, state))
            self.analysis_effect_list[program_point] = self.transfer(program_point)
            logger.info(
                "Effect at program point {}: {}".format(
                    program_point, self.analysis_effect_list[program_point]
                )
            )
            logger.warning(dmf.share.analysis_modules["static_builtins"].namespace)

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
            # x()
            if isinstance(func, ast.Name):
                self.LAMBDA_Name(program_point, func.id)
            # x.y()
            elif isinstance(func, ast.Attribute):
                attr: str = func.attr
                state = self.analysis_list[program_point]
                # get abstract value of receiver object
                receiver_value = compute_value_of_expr(program_point, func.value, state)
                self.LAMBDA_Attribute(program_point, receiver_value, attr)
        else:
            assert False

    # deal with x.y()
    def LAMBDA_Attribute(
        self, program_point: ProgramPoint, receiver_value: Value, attr: str
    ):
        # x has type ?
        for _, typ in receiver_value:
            if isinstance(typ, ClsType):
                attr_value: Value = typ.getattr(attr)
                assert False
            elif isinstance(typ, FuncType):
                assert False
            elif isinstance(typ, InsType):
                self.lambda_attribute_call(program_point, typ, attr)
            else:
                assert False

    # deal with cases such as class xxx
    def LAMBDA_ClassDef(self, program_point: ProgramPoint):
        call_lab, call_ctx = program_point
        return_lab = self.get_return_label(call_lab)
        cfg = self.sub_cfgs[call_lab]
        self.add_sub_cfg(cfg)
        self.inter_flows.add(
            (
                (call_lab, call_ctx),
                (cfg.start_block.bid, call_ctx),
                (cfg.final_block.bid, call_ctx),
                (return_lab, call_ctx),
            )
        )

    # deal with cases such as name()
    def LAMBDA_Name(self, program_point: ProgramPoint, name: str):
        state: State = self.analysis_list[program_point]
        # get abstract value of name
        value: Value = state.read_var_from_stack(name)
        # iterate all types to find which is callable
        for _, typ in value:
            if isinstance(typ, ClsType):
                self.lambda_class_init(program_point, typ)
            elif isinstance(typ, FuncType):
                self.lambda_func_call(program_point, typ)
            else:
                logger.warn(typ)
                assert False

    # deal with class initialization
    # find __init__ method
    # then use it to create class instance
    def lambda_class_init(self, program_point, typ: ClsType, attr: str = "__init__"):
        call_lab, call_ctx = program_point
        return_lab = self.get_return_label(call_lab)
        addr = record(call_lab, call_ctx)
        ins_type = InsType(addr, typ)
        init_methods: Value = analysis_heap.read_field_from_heap(ins_type, attr)
        for _, init_method in init_methods:
            if isinstance(init_method, MethodType):
                analysis_heap.write_ins_to_heap(ins_type)
                entry_lab, exit_lab = init_method.get_code()
                inter_flow = (
                    (call_lab, call_ctx),
                    (entry_lab, call_ctx),
                    (exit_lab, call_ctx),
                    (return_lab, call_ctx),
                )
                self.inter_flows.add(inter_flow)
                self.self_info[(entry_lab, call_ctx)] = (ins_type, INIT_FLAG)
            else:
                logger.warn(init_method)
                assert False

    # instance.method()
    # in Python, two situations.
    # 1. instance function. such as instance.method(args...)
    # 2. class method. such as instance.method(self, args...)
    # We support 1. now.
    def lambda_attribute_call(
        self, program_point: ProgramPoint, instance: InsType, attr: str
    ):
        attr_value: Value = analysis_heap.read_field_from_heap(instance, attr)
        for _, typ in attr_value:
            if isinstance(typ, FuncType):
                self.lambda_func_call(program_point, typ)
            elif isinstance(typ, ClsType):
                self.lambda_class_init(program_point, typ)
            elif isinstance(typ, MethodType):
                self.lambda_method_call(program_point, instance, typ)
            else:
                logger.warn(typ)
                assert False

    # unbound func call
    # func()
    def lambda_func_call(self, program_point: ProgramPoint, typ: FuncType):
        call_lab, call_ctx = program_point
        entry_lab, exit_lab = typ.get_code()
        return_lab = self.get_return_label(call_lab)
        new_ctx: Ctx = merge(call_lab, None, call_ctx)
        inter_flow = (
            (call_lab, call_ctx),
            (entry_lab, new_ctx),
            (exit_lab, new_ctx),
            (return_lab, call_ctx),
        )
        self.inter_flows.add(inter_flow)

    def lambda_method_call(
        self, program_point: ProgramPoint, instance: InsType, typ: MethodType
    ):
        call_lab, call_ctx = program_point
        entry_lab, exit_lab = typ.get_code()
        return_lab = self.get_return_label(call_lab)
        new_ctx: Ctx = merge(call_lab, instance, call_ctx)
        inter_flow = (
            (call_lab, call_ctx),
            (entry_lab, new_ctx),
            (exit_lab, new_ctx),
            (return_lab, call_ctx),
        )
        self.inter_flows.add(inter_flow)

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
        label, _ = program_point
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
                    analysis_heap.write_field_to_heap(typ, field, rhs_value)
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
            instance, init_flag = self.self_info[program_point]
            value = Value()
            value.inject_ins_type(instance)
            new.write_var_to_stack(SELF_FLAG, value)
            if init_flag:
                # write the init flag to stack
                new.write_var_to_stack(INIT_FLAG, INIT_FLAG_VALUE)
        return new

    def transfer_return(self, program_point: ProgramPoint):
        return_lab, return_ctx = program_point
        stmt: ast.stmt = self.get_stmt_by_label(return_lab)

        if isinstance(stmt, ast.ClassDef):
            return self.transfer_ClassDef_return(program_point)
        elif isinstance(stmt, ast.Name):
            return_state = self.analysis_list[program_point]
            # new_call_state: State = call_state.copy()
            new_return_state: State = return_state.copy()
            new_return_state.pop_frame_from_stack()

            return_value: Value = return_state.read_var_from_stack(RETURN_FLAG)
            # write value to name
            new_return_state.write_var_to_stack(stmt.id, return_value)
            return new_return_state
        else:
            assert False

    def transfer_Import(self, program_point: ProgramPoint):
        lab, ctx = program_point
        old: State = self.analysis_list[program_point]
        new: State = old.copy()
        stmt: ast.Import = self.get_stmt_by_label(lab)
        module_name = stmt.names[0].name
        as_name = stmt.names[0].asname
        mod = dmf.share.static_import_module(module_name)
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
        mod = dmf.share.static_import_module(
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

        new: State = return_state.copy()
        new.pop_frame_from_stack()

        # class name
        cls_name: str = stmt.name
        module: str = new.get_current_module()
        # class frame
        frame: Frame = return_state.top_frame_on_stack()
        # abstract value for class
        value: Value = Value()

        def compute_bases(stmt: ast.ClassDef):
            if stmt.bases:
                base_types = []
                for base in stmt.bases:
                    assert isinstance(base, ast.Name)
                    base_value: Value = new.read_var_from_stack(base.id)
                    cls_types: List[ClsType] = base_value.extract_cls_type()
                    assert len(cls_types) == 1
                    for cls in cls_types:
                        base_types.append(cls)
                return base_types
            else:
                builtin_module = dmf.share.analysis_modules["static_builtins"]
                builtin_namespace = builtin_module.get_namespace()
                default_base = builtin_namespace["__object__"]
                if "static_object" in builtin_namespace:
                    static_object: Value = builtin_namespace.read_value_from_var(
                        "static_object"
                    )
                    static_object_types = static_object.extract_cls_type()
                    for typ in static_object_types:
                        default_base = typ
                return [default_base]

        bases = compute_bases(stmt)
        cls_type: ClsType = ClsType(cls_name, module, bases, frame.f_locals)
        # inject namespace
        value.inject_cls_type(cls_type)
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
        func_type = FuncType(func_name, (entry_lab, exit_lab))
        value.inject_func_type(lab, func_type)

        new.write_var_to_stack(func_name, value)
        return new

    def transfer_Pass(self, program_point: ProgramPoint) -> State:
        old: State = self.analysis_list[program_point]
        new: State = old.copy()
        return new

    def transfer_If(self, program_point: ProgramPoint) -> State:
        old: State = self.analysis_list[program_point]
        new: State = old.copy()
        return new

    def transfer_While(self, program_point: ProgramPoint) -> State:
        old: State = self.analysis_list[program_point]
        new: State = old.copy()
        return new

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

    def transfer_Global(self, program_point: ProgramPoint) -> State:
        lab, _ = program_point
        stmt: ast.Global = self.get_stmt_by_label(lab)

        old: State = self.analysis_list[program_point]
        new: State = old.copy()

        name = stmt.names[0]
        value = new.read_var_from_stack(name, scope="global")
        new.write_var_to_stack(name, value, "global")

        return new

    def transfer_Nonlocal(self, program_point: ProgramPoint) -> State:
        lab, _ = program_point
        stmt: ast.Nonlocal = self.get_stmt_by_label(lab)

        old: State = self.analysis_list[program_point]
        new: State = old.copy()

        name = stmt.names[0]
        value = new.read_var_from_stack(name)
        new.write_var_to_stack(name, value, "nonlocal")

        return new
