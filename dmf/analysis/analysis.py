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
from collections import defaultdict, deque
from typing import Dict, Tuple, Deque, List

import dmf.share
from dmf.analysis.analysisbase import AnalysisBase, ProgramPoint
from dmf.analysis.prim import NoneType
from dmf.analysis.stack import Frame, analysis_stack
from dmf.analysis.state import (
    compute_function_defaults,
    compute_bases,
    parse_positional_args,
    parse_keyword_args,
    parse_default_args,
    parse_kwonly_args,
    compute_func_args,
    State,
    BOTTOM,
    compare_states,
    merge_states,
    is_bot_state,
    deepcopy_state,
)
from dmf.analysis.types import (
    ModuleType,
    CustomClass,
    FunctionObject,
    MethodClass,
    dunder_lookup,
    Constructor,
    Setattr,
    mock_value,
    SpecialMethodClass,
    Getattr,
    ListClass,
    TupleClass,
    analysis_heap,
)
from dmf.analysis.value import Value, create_value_with_type
from dmf.analysis.variables import (
    Namespace_Local,
    Namespace_Nonlocal,
    Namespace_Global,
    RETURN_FLAG,
    POS_ARG_END,
    INIT_FLAG,
    Namespace_Helper,
)
from dmf.flows.temp import Unused_Name
from dmf.log.logger import logger


def record(label: int, context: Tuple):
    return label


def merge(label: int, heap, context: Tuple):
    return context[-1:] + (label,)


class Analysis(AnalysisBase):
    def __init__(self, module_name: str):
        super().__init__()
        self.entry_program_point_info: Dict = {}
        self.work_list: Deque[Tuple[ProgramPoint, ProgramPoint]] = deque()
        self.extremal_value: State = (analysis_stack, analysis_heap)
        self.analysis_list: defaultdict[ProgramPoint, State | BOTTOM] = defaultdict(
            lambda: BOTTOM
        )
        self.analysis_effect_list = {}

        curr_module: ModuleType = dmf.share.analysis_modules[module_name]
        start_lab, final_lab = curr_module.entry_label, curr_module.exit_label
        self.extremal_point: ProgramPoint = (start_lab, ())
        self.final_point: ProgramPoint = (final_lab, ())
        self.analyzed_program_points = {self.extremal_point}

        # init first frame
        def init_first_frame(extremal_value, module):
            global_ns = module.namespace
            extremal_value.push_frame(
                Frame(
                    f_locals=global_ns,
                    f_back=None,
                    f_globals=global_ns,
                )
            )

        init_first_frame(self.extremal_value[0], curr_module)

    def compute_fixed_point(self):
        self.initialize()
        self.iterate()
        self.present()

    def initialize(self):
        self.work_list.extendleft(self.DELTA(self.extremal_point))
        self.analysis_list[self.extremal_point] = self.extremal_value

    def _push_state_to(self, state: State, program_point: ProgramPoint):
        old: State | BOTTOM = self.analysis_list[program_point]
        if not compare_states(state, old):
            state = merge_states(state, old)
            self.analysis_list[program_point]: State = state
            self.LAMBDA(program_point)
            added_program_points = self.DELTA(program_point)
            self.work_list.extendleft(added_program_points)

    def iterate(self):
        # as long as there are flows in work_list
        while self.work_list:
            # get the leftmost one
            program_point1, program_point2 = self.work_list.popleft()
            logger.debug(f"Current program point1 {program_point1}")

            transferred: State | BOTTOM = self.transfer(program_point1)
            self._push_state_to(transferred, program_point2)

    def present(self):
        for program_point in self.analysis_list:
            logger.info(
                "Context at program point {}: {}".format(
                    program_point, self.analysis_list[program_point]
                )
            )
            self.analysis_effect_list[program_point] = self.transfer(program_point)
            logger.info(
                "Effect at program point {}: {}".format(
                    program_point, self.analysis_effect_list[program_point]
                )
            )
        self.transfer(self.final_point)

    # based on current program point, update self.IF
    def LAMBDA(self, program_point: ProgramPoint) -> None:
        logger.debug(f"Current lambda point: {program_point}")
        old_state: State = self.analysis_list[program_point]
        new_state: State = deepcopy_state(old_state)
        dummy_value: Value = Value()

        # function calls and descriptors will produce dummy value and inter-procedural flows
        # call labels includes:
        # 1. ast.ClassDef
        # 2. ast.Call
        # 3. __get__
        # 4. __set__
        # 5. special init method for our analysis
        if self.is_call_point(program_point):
            if self.is_classdef_call_point(program_point):
                self._lambda_classdef(program_point, old_state, new_state, dummy_value)
            elif self.is_normal_call_point(program_point):
                self._lambda_normal(program_point, old_state, new_state, dummy_value)
            elif self.is_special_init_call_point(program_point):
                self._lambda_special_init(
                    program_point, old_state, new_state, dummy_value
                )
            elif self.is_getter_call_point(program_point):
                self._lambda_getter(program_point, old_state, new_state, dummy_value)
            elif self.is_setter_call_point(program_point):
                self._lambda_setter(program_point, old_state, new_state, dummy_value)

    def _lambda_constructor(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
        typ: Constructor,
    ):
        # correspond to object.__new__(cls)

        stmt = self.get_stmt_by_point(program_point)
        assert isinstance(stmt, ast.Call) and len(stmt.args) == 1

        call_lab, call_ctx = program_point
        addr = record(call_lab, call_ctx)
        new_stack, new_heap = new_state
        cls_value = new_stack.compute_value_of_expr(stmt.args[0])
        for c in cls_value:
            instance = typ(addr, c)
            heap = new_heap.write_ins_to_heap(instance)
            instance.nl__dict__ = heap
            dummy_value.inject(instance)

    def _lambda_special_method(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
        typ: SpecialMethodClass,
    ):
        call_stmt = self.get_stmt_by_point(program_point)

        args, keywords = compute_func_args(
            new_state, call_stmt.args, call_stmt.keywords
        )
        res = typ(*args, **keywords)
        dummy_value.inject(res)

    def _lambda_special_init(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
    ):
        call_lab, call_ctx = program_point
        ret_lab, dummy_ret_lab = self.get_special_init_return_label(call_lab)

        call_stmt: ast.Call = self.get_stmt_by_label(call_lab)
        new_stack, new_heap = new_state
        value: Value = new_stack.compute_value_of_expr(call_stmt.func)

        for val in value:
            if isinstance(val, MethodClass):
                entry_lab, exit_lab = val.nl__func__.nl__code__
                instance = val.nl__instance__
                new_ctx: Tuple = merge(call_lab, instance.nl__address__, call_ctx)

                self.entry_program_point_info[(entry_lab, new_ctx)] = (
                    instance,
                    INIT_FLAG,
                    val.nl__module__,
                )

                inter_flow = (
                    (call_lab, call_ctx),
                    (entry_lab, new_ctx),
                    (exit_lab, new_ctx),
                    (ret_lab, call_ctx),
                )
                self.inter_flows.add(inter_flow)
            else:
                dummy_value.inject(val)

        dummy_ret_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
        new_stack.write_var(dummy_ret_stmt.id, Namespace_Local, dummy_value)
        self._push_state_to(new_state, (dummy_ret_lab, call_ctx))

    def _lambda_getter(
        self, program_point, old_state: State, new_state: State, dummy_value: Value
    ):
        call_stmt: ast.Attribute = self.get_stmt_by_point(program_point)
        assert isinstance(call_stmt, ast.Attribute), call_stmt

        call_lab, call_ctx = program_point
        new_stack, new_heap = new_state
        value = new_stack.compute_value_of_expr(call_stmt.value)
        dummy_value = Value()
        ret_lab, dummy_ret_lab = self.get_getter_return_label(call_lab)
        for val in value:
            attr_value = Getattr(val, call_stmt.attr, [])
            for attr_val in attr_value:
                if isinstance(attr_val, MethodClass):
                    entry_lab, exit_lab = attr_val.nl__func__.nl__code__
                    instance = attr_val.nl__instance__
                    new_ctx: Tuple = merge(call_lab, instance.nl__address__, call_ctx)

                    self.entry_program_point_info[(entry_lab, new_ctx)] = (
                        instance,
                        None,
                        attr_val.nl__module__,
                    )

                    inter_flow = (
                        (call_lab, call_ctx),
                        (entry_lab, new_ctx),
                        (exit_lab, new_ctx),
                        (ret_lab, call_ctx),
                    )
                    self.inter_flows.add(inter_flow)
                else:
                    dummy_value.inject_type(attr_val)

        dummy_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
        new_stack.write_var(dummy_stmt.id, Namespace_Local, dummy_value)
        self._push_state_to(new_state, (dummy_ret_lab, call_ctx))

    def _lambda_setter(
        self, program_point, old_state: State, new_state: State, dummy_value: Value
    ):
        call_stmt: ast.Assign = self.get_stmt_by_point(program_point)
        assert isinstance(call_stmt, ast.Assign), call_stmt
        assert len(call_stmt.targets) == 1 and isinstance(
            call_stmt.targets[0], ast.Attribute
        )
        new_stack, new_heap = new_state

        attribute: ast.Attribute = call_stmt.targets[0]
        attr: str = call_stmt.targets[0].attr

        call_lab, call_ctx = program_point

        ret_lab, dummy_ret_lab = self.get_setter_return_label(call_lab)
        attr_value = new_stack.compute_value_of_expr(attribute.value)
        expr_value = new_stack.compute_value_of_expr(call_stmt.value)
        for attr_type in attr_value:
            attr_value = Setattr(attr_type, attr, expr_value)
            for attr_typ in attr_value:
                if isinstance(attr_typ, MethodClass):
                    entry_lab, exit_lab = attr_typ.nl__func__.nl__code__
                    instance = attr_typ.nl__instance__
                    new_ctx: Tuple = merge(call_lab, instance.nl__address__, call_ctx)

                    self.entry_program_point_info[(entry_lab, new_ctx)] = (
                        instance,
                        None,
                        attr_typ.nl__module__,
                    )

                    inter_flow = (
                        (call_lab, call_ctx),
                        (entry_lab, new_ctx),
                        (exit_lab, new_ctx),
                        (ret_lab, call_ctx),
                    )
                    self.inter_flows.add(inter_flow)

        self._push_state_to(new_state, (dummy_ret_lab, call_ctx))

    # deal with cases such as class xxx
    def _lambda_classdef(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
    ):
        call_lab, call_ctx = program_point

        cfg, entry_lab, exit_lab = self.add_sub_cfg(call_lab)

        return_lab = self.get_classdef_return_label(call_lab)
        self.inter_flows.add(
            (
                (call_lab, call_ctx),
                (entry_lab, call_ctx),
                (exit_lab, call_ctx),
                (return_lab, call_ctx),
            )
        )
        self.entry_program_point_info[(entry_lab, call_ctx)] = (None, None, None)

    # deal with cases such as name()
    def _lambda_normal(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
    ):

        call_stmt: ast.Call = self.get_stmt_by_point(program_point)
        assert isinstance(call_stmt, ast.Call), call_stmt

        call_lab, call_ctx = program_point
        address = record(call_lab, call_ctx)

        dummy_value_normal: Value = Value()
        dummy_value_special: Value = Value()

        value: Value = new_state[0].compute_value_of_expr(call_stmt.func, address)
        # iterate all types to find which is callable
        for typ in value:
            if isinstance(typ, CustomClass):
                self._lambda_class(
                    program_point, old_state, new_state, dummy_value_special, typ
                )
            elif isinstance(typ, FunctionObject):
                self._lambda_function(
                    program_point, old_state, new_state, dummy_value, typ
                )
            elif isinstance(typ, MethodClass):
                self._lambda_method(
                    program_point, old_state, new_state, dummy_value, typ
                )
            elif isinstance(typ, SpecialMethodClass):
                self._lambda_special_method(
                    program_point, old_state, new_state, dummy_value_normal, typ
                )
            elif isinstance(typ, Constructor):
                self._lambda_constructor(
                    program_point, old_state, new_state, dummy_value_normal, typ
                )
            elif isinstance(typ, ListClass):
                self._lambda_builtin_list(
                    program_point, old_state, new_state, dummy_value_normal, typ
                )
            elif isinstance(typ, TupleClass):
                self._lambda_builtin_tuple(
                    program_point, old_state, new_state, dummy_value_normal, typ
                )

        if len(dummy_value_normal):
            _, dummy_ret_lab = self.get_func_return_label(call_lab)
            dummy_ret_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
            new_state[0].write_var(
                dummy_ret_stmt.id, Namespace_Local, dummy_value_normal
            )
            self._push_state_to(new_state, (dummy_ret_lab, call_ctx))
        if len(dummy_value_special):
            _, dummy_ret_lab = self.get_special_new_return_label(call_lab)
            dummy_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
            new_state[0].write_var(dummy_stmt.id, Namespace_Local, dummy_value_special)
            self._push_state_to(new_state, (dummy_ret_lab, call_ctx))

    def _lambda_builtin_list(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
        typ: ListClass,
    ):
        call_lab, call_ctx = program_point
        call_stmt = self.get_stmt_by_point(program_point)

        address = record(call_lab, call_ctx)
        args, _ = compute_func_args(new_state, call_stmt.args, call_stmt.keywords)
        res = typ(*args)
        res.nl__uuid__ = address
        dummy_value.inject(res)

    def _lambda_builtin_tuple(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
        typ: TupleClass,
    ):
        self._lambda_builtin_list(program_point, old_state, new_state, dummy_value, typ)

    # deal with class initialization
    # find __new__ and __init__ method
    # then use it to create class instance
    def _lambda_class(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
        typ: CustomClass,
    ):
        call_lab, call_ctx = program_point
        _, new_heap = new_state

        addr = record(call_lab, call_ctx)
        new_method = dunder_lookup(typ, "__new__")
        if isinstance(new_method, Constructor):
            instance = new_method(addr, typ)
            dummy_value.inject(instance)
        elif isinstance(new_method, FunctionObject):
            entry_lab, exit_lab = new_method.nl__code__
            ret_lab, _ = self.get_special_new_return_label(call_lab)
            new_ctx = merge(call_lab, None, call_ctx)
            inter_flow = (
                (call_lab, call_ctx),
                (entry_lab, new_ctx),
                (exit_lab, new_ctx),
                (ret_lab, call_ctx),
            )
            self.inter_flows.add(inter_flow)
            self.entry_program_point_info[(entry_lab, new_ctx)] = (
                typ,
                None,
                typ.nl__module__,
            )

    # unbound func call
    # func()
    def _lambda_function(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
        typ: FunctionObject,
    ):
        call_lab, call_ctx = program_point
        entry_lab, exit_lab = typ.nl__code__
        ret_lab, _ = self.get_func_return_label(call_lab)

        new_ctx: Tuple = merge(call_lab, None, call_ctx)
        inter_flow = (
            (call_lab, call_ctx),
            (entry_lab, new_ctx),
            (exit_lab, new_ctx),
            (ret_lab, call_ctx),
        )
        self.inter_flows.add(inter_flow)
        self.entry_program_point_info[(entry_lab, new_ctx)] = (
            None,
            None,
            typ.nl__module__,
        )

    def _lambda_method(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
        typ: MethodClass,
    ):
        call_lab, call_ctx = program_point
        entry_lab, exit_lab = typ.nl__func__.nl__code__
        instance = typ.nl__instance__
        new_ctx: Tuple = merge(call_lab, instance.nl__address__, call_ctx)

        ret_lab, dummy_ret_lab = self.get_func_return_label(call_lab)
        self.entry_program_point_info[(entry_lab, new_ctx)] = (
            instance,
            None,
            typ.nl__module__,
        )

        inter_flow = (
            (call_lab, call_ctx),
            (entry_lab, new_ctx),
            (exit_lab, new_ctx),
            (ret_lab, call_ctx),
        )
        self.inter_flows.add(inter_flow)

    def transfer(self, program_point: ProgramPoint) -> State | BOTTOM:
        # if old_state is BOTTOM, skip this transfer
        old_state: State = self.analysis_list[program_point]
        if is_bot_state(old_state):
            return BOTTOM

        new_state = deepcopy_state(old_state)
        if self.is_dummy_point(program_point):
            return self.transfer_dummy(program_point, old_state, new_state)
        elif self.is_call_point(program_point):
            return self.transfer_call(program_point, old_state, new_state)
        elif self.is_entry_point(program_point):
            return self.transfer_entry(program_point, old_state, new_state)
        elif self.is_exit_point(program_point):
            return self.transfer_exit(program_point, old_state, new_state)
        elif self.is_return_point(program_point):
            return self.transfer_return(program_point, old_state, new_state)
        return self.do_transfer(program_point, old_state, new_state)

    def transfer_dummy(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        return new_state

    def do_transfer(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ) -> State:
        stmt: ast.stmt = self.get_stmt_by_point(program_point)
        handler = getattr(self, "transfer_" + stmt.__class__.__name__)
        return handler(program_point, old_state, new_state, stmt)

    def transfer_Assign(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.Assign,
    ) -> State:
        new_stack, new_heap = new_state
        rhs_value: Value = new_stack.compute_value_of_expr(stmt.value, program_point)
        target: ast.expr = stmt.targets[0]
        if isinstance(target, ast.Name):
            new_stack.write_var(target.id, Namespace_Local, rhs_value)
        else:
            assert False
        return new_state

    def transfer_call(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        if self.is_classdef_call_point(program_point):
            return self._transfer_call_classdef(program_point, old_state, new_state)
        elif self.is_normal_call_point(program_point):
            return self._transfer_call_normal(program_point, old_state, new_state)
        elif self.is_special_init_call_point(program_point):
            return self._transfer_call_normal(program_point, old_state, new_state)
        elif self.is_getter_call_point(program_point):
            return self._transfer_call_getter(program_point, old_state, new_state)
        elif self.is_setter_call_point(program_point):
            return self._transfer_call_setter(program_point, old_state, new_state)

    def _transfer_call_classdef(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        new_stack, new_heap = new_state
        new_stack.next_ns()
        return new_state

    def _transfer_call_normal(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        # Normal call has form: func_name(args, keywords)
        call_stmt: ast.Call = self.get_stmt_by_point(program_point)
        assert isinstance(call_stmt, ast.Call), call_stmt
        new_stack, new_heap = new_state

        # new namespace to simulate function call
        new_stack.next_ns()

        # deal with positional args
        args: List[ast.expr] = call_stmt.args
        # has explicit args
        if args:
            for idx, arg in enumerate(args, 1):
                if isinstance(arg, ast.Starred):
                    raise NotImplementedError(arg)
                arg_value = new_stack.compute_value_of_expr(arg)
                new_stack.write_var(str(idx), Namespace_Local, arg_value)
            new_stack.write_helper_var(POS_ARG_END, idx)
        # may have implicit args, such as bounded methods
        else:
            new_stack.write_helper_var(POS_ARG_END, 0)

        # deal with keyword args
        keywords: List[ast.keyword] = call_stmt.keywords
        for keyword in keywords:
            if keyword.arg is None:
                raise NotImplementedError(keyword)
            keyword_value = new_stack.compute_value_of_expr(keyword.value)
            new_stack.write_var(keyword.arg, Namespace_Local, keyword_value)

        return new_state

    def _transfer_call_getter(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        call_stmt: ast.stmt = self.get_stmt_by_point(program_point)
        assert isinstance(call_stmt, ast.Attribute), call_stmt

        new_stack, new_heap = new_state
        new_stack.next_ns()

        target_value = new_stack.compute_value_of_expr(call_stmt.value)
        for target_typ in target_value:
            print(target_typ, call_stmt.attr)
            attr_value = Getattr(target_typ, call_stmt.attr, None)
            for attr_typ in attr_value:
                if isinstance(attr_typ, MethodClass):
                    instance = attr_typ.descriptor_instance
                    instance_value = create_value_with_type(instance)
                    new_stack.write_var("1", Namespace_Local, instance_value)
                    owner = attr_typ.descriptor_owner
                    owner_value = create_value_with_type(owner)
                    new_stack.write_var("2", Namespace_Local, owner_value)
                    new_stack.write_var(POS_ARG_END, Namespace_Helper, 2)

        return new_state

    def _transfer_call_setter(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        call_stmt: ast.stmt = self.get_stmt_by_point(program_point)
        assert isinstance(call_stmt, ast.Assign)
        assert len(call_stmt.targets) == 1 and isinstance(
            call_stmt.targets[0], ast.Attribute
        )

        new_stack, new_heap = new_state
        new_stack.next_ns()

        attribute: ast.Attribute = call_stmt.targets[0]
        attr: str = call_stmt.targets[0].attr

        lhs_value = new_stack.compute_value_of_expr(attribute.value)
        rhs_value = new_stack.compute_value_of_expr(call_stmt.value)
        for target_typ in lhs_value:
            attr_value = Setattr(target_typ, attr, rhs_value)
            if attr_value is not None:
                for attr_typ in attr_value:
                    if isinstance(attr_typ, MethodClass):
                        instance = attr_typ.descriptor_instance
                        instance_value = create_value_with_type(instance)
                        new_stack.write_var("1", Namespace_Local, instance_value)
                        value = attr_typ.descriptor_value
                        value_value = create_value_with_type(value)
                        new_stack.write_var("2", Namespace_Local, value_value)
                        new_stack.write_var(POS_ARG_END, Namespace_Helper, 2)

        return new_state

    # consider current global namespace
    def transfer_entry(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        stmt = self.get_stmt_by_point(program_point)
        new_stack, new_heap = new_state

        # is self.self_info[program_point] is not None, it means
        # this is a class method call
        # we pass instance information, module name to entry labels
        instance, init_flag, module_name = self.entry_program_point_info[program_point]
        if instance:
            value = create_value_with_type(instance)
            new_stack.write_var(str(0), Namespace_Local, value)
        if init_flag:
            new_stack.write_var(INIT_FLAG, Namespace_Helper, mock_value)
        if module_name:
            new_stack.check_module_diff(module_name)

        if isinstance(stmt, ast.arguments):
            # Positional and keyword arguments
            start_pos = 0 if instance else 1
            arg_flags = parse_positional_args(start_pos, stmt, new_state)
            arg_flags = parse_keyword_args(arg_flags, stmt, new_state)
            _ = parse_default_args(arg_flags, stmt, new_state)
            parse_kwonly_args(stmt, new_state)

        return new_state

    def transfer_exit(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        new_stack, new_heap = new_state
        if not new_stack.top_namespace_contains(RETURN_FLAG):
            value = create_value_with_type(NoneType())
            new_stack.write_var(RETURN_FLAG, Namespace_Local, value)

        return new_state

    def transfer_return(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        return_lab, return_ctx = program_point
        stmt: ast.stmt = self.get_stmt_by_label(return_lab)

        if isinstance(stmt, ast.ClassDef):
            return self.transfer_return_classdef(program_point, old_state, new_state)
        elif isinstance(stmt, ast.Name):
            return self.transfer_return_name(program_point, old_state, new_state, stmt)
        elif isinstance(stmt, ast.Assign):
            assert isinstance(stmt.targets[0], ast.Attribute), stmt
            return self.transfer_return_setter(
                program_point, old_state, new_state, stmt
            )
        else:
            assert False

    def transfer_return_setter(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.Assign,
    ):
        new_stack, new_heap = new_state
        new_stack.pop_frame()
        return new_state

    def transfer_return_name(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.Name,
    ):
        new_stack, new_heap = new_state
        return_value: Value = new_stack.read_var(RETURN_FLAG)
        if new_stack.top_namespace_contains(INIT_FLAG):
            return_value = new_stack.read_var("self")
        new_stack.pop_frame()

        # no need to assign
        if stmt.id == Unused_Name:
            return new_state

        # write value to name
        new_stack.write_var(stmt.id, Namespace_Local, return_value)
        return new_state

    def transfer_Import(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.Import,
    ):
        module_name = stmt.names[0].name
        as_name = stmt.names[0].asname
        mod = dmf.share.static_import_module(module_name)
        value = Value()
        value.inject_type(mod)
        new_stack = new_state[0]
        new_stack.write_var(module_name if as_name is None else as_name, value)
        logger.debug("Import module {}".format(mod))
        return new_state

    def transfer_ImportFrom(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.ImportFrom,
    ):
        new_stack = new_state[0]
        module_name = "" if stmt.module is None else stmt.module
        dot_number = "." * stmt.level
        package = new_stack.read_package()
        mod = dmf.share.static_import_module(
            name=dot_number + module_name,
            package=package,
        )
        logger.debug("ImportFrom module {}".format(mod))

        aliases = stmt.names
        for alias in aliases:
            imported_name = alias.name
            imported_value = mod.getattr(imported_name)
            if alias.asname is None:
                new_stack.write_var(imported_name, Namespace_Local, imported_value)
            else:
                new_stack.write_var(alias.asname, Namespace_Local, imported_value)
        return new_state

    def transfer_return_classdef(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        # return stuff
        return_lab, return_ctx = program_point
        # stmt
        stmt: ast.ClassDef = self.get_stmt_by_point(program_point)
        new_stack = new_state[0]

        # class frame
        frame: Frame = new_stack.top_frame()
        new_stack.pop_frame()

        # class name
        cls_name: str = stmt.name
        module: str = new_stack.read_module()

        value: Value = Value()
        bases = compute_bases(new_state, stmt)
        call_lab = self.get_classdef_call_label(return_lab)
        custom_class: CustomClass = CustomClass(
            uuid=call_lab,
            name=cls_name,
            module=module,
            bases=bases,
            dict=frame.f_locals,
        )
        value.inject_type(custom_class)
        new_stack.write_var(cls_name, Namespace_Local, value)
        return new_state

    def transfer_FunctionDef(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        node: ast.FunctionDef,
    ):
        lab, _ = program_point
        func_cfg, entry_lab, exit_lab = self.add_sub_cfg(lab)

        compute_function_defaults(new_state, node)

        func_module: str = new_state[0].read_module()
        value = create_value_with_type(
            FunctionObject(
                uuid=lab, name=node.name, module=func_module, code=(entry_lab, exit_lab)
            )
        )

        new_state[0].write_var(node.name, Namespace_Local, value)
        return new_state

    def transfer_Pass(
        self, program_point: ProgramPoint, old_state: State, new_state: State, stmt
    ) -> State:
        return new_state

    def transfer_If(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt,
    ) -> State:
        return new_state

    def transfer_While(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt,
    ) -> State:
        return new_state

    def transfer_Return(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.Return,
    ) -> State:
        name: str = stmt.value.id
        new_stack, new_heap = new_state
        value: Value = new_stack.read_var(name)
        new_stack.write_var(RETURN_FLAG, Namespace_Local, value)
        return new_state

    def transfer_Global(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.Global,
    ) -> State:
        name = stmt.names[0]
        new_stack, _ = new_state
        new_stack.write_var(name, Namespace_Global, None)

        return new_state

    def transfer_Nonlocal(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.Nonlocal,
    ) -> State:
        name = stmt.names[0]
        new_stack, _ = new_state
        new_stack.write_var(name, Namespace_Nonlocal, None)

        return new_state

    def transfer_Delete(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.Delete,
    ) -> State:
        new_stack = new_state[0]
        assert len(stmt.targets) == 1, stmt
        assert isinstance(stmt.targets[0], ast.Name), stmt
        name = stmt.targets[0].id
        new_stack.delete_var(name)
        return new_state
