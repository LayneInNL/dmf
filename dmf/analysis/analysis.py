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
import sys
from collections import defaultdict, deque, namedtuple
from typing import Dict, Tuple, Deque, List

from dmf.analysis.analysis_types import (
    ArtificialFunction,
    AnalysisFunction,
    AnalysisClass,
    ArtificialMethod,
    AnalysisMethod,
    None_Instance,
)
from dmf.analysis.analysis_types import (
    Constructor,
    AnalysisDescriptorGetFunction,
    AnalysisDescriptorSetFunction,
    ArtificialClass,
)
from dmf.analysis.analysisbase import AnalysisBase, ProgramPoint
from dmf.analysis.builtin_functions import import_a_module
from dmf.analysis.gets_sets import getattrs, _getattr, setattrs, _setattr
from dmf.analysis.implicit_names import (
    POS_ARG_LEN,
    INIT_FLAG,
    RETURN_FLAG,
    PACKAGE_FLAG,
    NAME_FLAG,
)
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
    Stack,
    Heap,
)
from dmf.analysis.value import Value, create_value_with_type, type_2_value
from dmf.log.logger import logger

Namespace_Local = "local"
Namespace_Nonlocal = "nonlocal"
Namespace_Global = "global"
Unused_Name = "UNUSED_NAME"

AdditionalEntryInfo = namedtuple(
    "AdditionalEntryInfo",
    ["instance_info", "init_info", "module_info", "defaults_info", "kwdefaults_info"],
)

# points-to analysis
def record(label: int, context: Tuple):
    return label


def merge(label: int, heap, context: Tuple):
    return context[-1:] + (label,)


class Analysis(AnalysisBase):
    def __init__(self, qualified_module_name: str):
        super().__init__()
        # work list
        self.work_list: Deque[Tuple[ProgramPoint, ProgramPoint]] = deque()
        # extremal value
        self.extremal_value: State = State(
            Stack(), Heap(), sys.analysis_modules, sys.fake_analysis_modules
        )
        # init first frame of stack of extremal value
        self.extremal_value.stack.init_first_frame(qualified_module_name)

        curr_module = sys.analysis_modules[qualified_module_name]
        start_lab, final_lab = curr_module.tp_code
        # start point
        self.extremal_point: ProgramPoint = (start_lab, ())
        # end point
        self.final_point: ProgramPoint = (final_lab, ())

        self.entry_program_point_info: Dict[ProgramPoint, AdditionalEntryInfo] = {}
        self.analysis_list: defaultdict[ProgramPoint, State | BOTTOM] = defaultdict(
            lambda: BOTTOM
        )
        self.analysis_effect_list = {}

        self.analyzed_program_points = {self.extremal_point}

    def compute_fixed_point(self):
        self.initialize()
        self.iterate()
        self.present()

    def initialize(self):
        sys.stack = self.extremal_value.stack
        sys.heap = self.extremal_value.heap
        self.work_list.extendleft(self.generate_flow(self.extremal_point))
        self.analysis_list[self.extremal_point] = self.extremal_value

    def _push_state_to(self, state: State, program_point: ProgramPoint):
        old: State | BOTTOM = self.analysis_list[program_point]
        if not compare_states(state, old):
            state: State = merge_states(state, old)
            self.analysis_list[program_point]: State = state
            self.detect_flow(program_point)
            added_program_points = self.generate_flow(program_point)
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
            try:
                self.analysis_effect_list[program_point] = self.transfer(program_point)
                logger.info(
                    "Effect at program point {}: {}".format(
                        program_point, self.analysis_effect_list[program_point]
                    )
                )
            except:
                pass
            else:
                pass
        self.transfer(self.final_point)

    # based on current program point, update self.IF
    def detect_flow(self, program_point: ProgramPoint) -> None:

        # function calls and descriptors will produce dummy value and inter-procedural flows
        # call labels includes:
        # 1. ast.ClassDef
        # 2. ast.Call
        # 3. __get__
        # 4. __set__
        # 5. special init method for our analysis
        if self.is_call_point(program_point):
            logger.debug(f"Current lambda point: {program_point}")
            # curr_state is the previous program point
            next_state: State = self.analysis_list[program_point]
            dummy_value: Value = Value()
            next_next_state: State = deepcopy_state(next_state)
            if self.is_classdef_call_point(program_point):
                self._detect_flow_classdef(
                    program_point, next_state, next_next_state, dummy_value
                )
            elif self.is_normal_call_point(program_point):
                self._detect_flow_call(
                    program_point, next_state, next_next_state, dummy_value
                )
                next_next_class_state = deepcopy_state(next_state)
                dummy_class_value = Value()
                self._detect_flow_call_class(
                    program_point, next_state, next_next_class_state, dummy_class_value
                )
            elif self.is_class_init_call_point(program_point):
                self.detect_flow_artificial_init(
                    program_point, next_state, next_next_state, dummy_value
                )
            elif self.is_getter_call_point(program_point):
                self._detect_flow_descr_get(
                    program_point, next_state, next_next_state, dummy_value
                )
            elif self.is_setter_call_point(program_point):
                self._detect_flow_descr_set(
                    program_point, next_state, next_next_state, dummy_value
                )

    def _lambda_constructor(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
        typ: Constructor,
    ):
        # correspond to object.__new__(cls)
        # it has the form of temp_func(cls)

        stmt = self.get_stmt_by_point(program_point)
        assert len(stmt.args) == 1

        call_lab, call_ctx = program_point
        addr = record(call_lab, call_ctx)
        new_stack, new_heap = new_state.stack, new_state.heap
        types = new_state.compute_value_of_expr(stmt.args[0])
        for cls in types:
            instance = typ(addr, cls)
            new_heap.write_instance_to_heap(instance)
            dummy_value.inject_type(instance)

    def _detect_flow_artificial_function(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
        typ: ArtificialFunction,
    ):
        call_stmt = self.get_stmt_by_point(program_point)

        args, keywords = compute_func_args(
            new_state, call_stmt.args, call_stmt.keywords
        )
        try:
            res = typ(*args, **keywords)
        except TypeError:
            logger.critical(f"Functioin call failed")
        else:
            dummy_value.inject(res)

    def _detect_flow_artificial_method(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
        typ: ArtificialMethod,
    ):
        call_stmt = self.get_stmt_by_point(program_point)

        args, keywords = compute_func_args(
            new_state, call_stmt.args, call_stmt.keywords
        )
        res = typ(*args, **keywords)
        dummy_value.inject(res)

    # deal with calling __init__ implicitly during class initialization.
    # this will only happen when xxx = Class().
    def detect_flow_artificial_init(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
    ):
        call_lab, call_ctx = program_point
        ret_lab, dummy_ret_lab = self.get_special_init_return_label(call_lab)

        call_stmt: ast.Call = self.get_stmt_by_label(call_lab)
        new_stack, new_heap = new_state.stack, new_state.heap
        # new_stack, new_heap = new_state
        value: Value = new_state.compute_value_of_expr(call_stmt.func)

        for val in value:
            if isinstance(val, AnalysisMethod):
                entry_lab, exit_lab = val.tp_function.tp_code
                instance = val.tp_instance
                new_ctx: Tuple = merge(call_lab, instance.tp_address, call_ctx)

                self.entry_program_point_info[
                    (entry_lab, new_ctx)
                ] = AdditionalEntryInfo(
                    instance,
                    INIT_FLAG,
                    val.tp_module,
                    None,
                    None,
                )

                inter_flow = (
                    (call_lab, call_ctx),
                    (entry_lab, new_ctx),
                    (exit_lab, new_ctx),
                    (ret_lab, call_ctx),
                )
                self.inter_flows.add(inter_flow)
            elif isinstance(val, ArtificialMethod):
                args, keywords = compute_func_args(
                    new_state, call_stmt.args, call_stmt.keywords
                )
                one_direct_res = val(*args, **keywords)
                dummy_value.inject(one_direct_res)
            else:
                pass
            # else:
            #     dummy_value.inject_type(val)

        dummy_ret_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
        new_stack.write_var(dummy_ret_stmt.id, Namespace_Local, dummy_value)
        self._push_state_to(new_state, (dummy_ret_lab, call_ctx))

    # deal with cases such as x.y
    # since there could be descriptors when doing attribute lookup
    def _detect_flow_descr_get(
        self, program_point, old_state: State, new_state: State, dummy_value: Value
    ):
        call_stmt: ast.Attribute = self.get_stmt_by_point(program_point)
        assert isinstance(call_stmt, ast.Attribute), call_stmt

        call_lab, call_ctx = program_point
        new_stack, new_heap = new_state.stack, new_state.heap
        # abstract value of stmt.value
        value = new_state.compute_value_of_expr(call_stmt.value)
        ret_lab, dummy_ret_lab = self.get_getter_return_label(call_lab)
        direct_res, descr_gets = getattrs(value, call_stmt.attr)

        dummy_value = Value()
        dummy_value.inject(direct_res)

        # if any of two is Any, the result is Any, the flow is not constructed
        if direct_res.is_Any() or descr_gets.is_Any():
            dummy_value = Value().make_any()
            dummy_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
            new_stack.write_var(dummy_stmt.id, Namespace_Local, dummy_value)
            self._push_state_to(new_state, (dummy_ret_lab, call_ctx))
        else:
            dummy_value.inject(direct_res)
            for descr_get in descr_gets:
                if isinstance(descr_get, AnalysisDescriptorGetFunction):
                    entry_lab, exit_lab = descr_get.tp_function.tp_code
                    instance = descr_get.tp_self
                    new_ctx: Tuple = merge(call_lab, instance.tp_address, call_ctx)

                    self.entry_program_point_info[
                        (entry_lab, new_ctx)
                    ] = AdditionalEntryInfo(
                        type_2_value(instance),
                        None,
                        descr_get.tp_function.tp_module,
                        descr_get.tp_function.tp_defaults,
                        descr_get.tp_function.tp_kwdefaults,
                    )

                    inter_flow = (
                        (call_lab, call_ctx),
                        (entry_lab, new_ctx),
                        (exit_lab, new_ctx),
                        (ret_lab, call_ctx),
                    )
                    self.inter_flows.add(inter_flow)

                else:
                    dummy_value.inject(descr_get)
                    # continue
                    # raise NotImplementedError(descr_get)

                # if isinstance(descr_get, AnalysisMethod):
                #     entry_lab, exit_lab = descr_get.tp_function.tp_code
                #     instance = descr_get.tp_instance
                #     new_ctx: Tuple = merge(call_lab, instance.tp_address, call_ctx)
                #
                #     self.entry_program_point_info[
                #         (entry_lab, new_ctx)
                #     ] = AdditionalEntryInfo(
                #         instance,
                #         None,
                #         descr_get.tp_module,
                #         None,
                #         None,
                #     )
                #
                #     inter_flow = (
                #         (call_lab, call_ctx),
                #         (entry_lab, new_ctx),
                #         (exit_lab, new_ctx),
                #         (ret_lab, call_ctx),
                #     )
                #     self.inter_flows.add(inter_flow)
                # elif isinstance(descr_get, ArtificialMethod):
                #     dummy_value.inject(descr_get)

        dummy_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
        new_stack.write_var(dummy_stmt.id, Namespace_Local, dummy_value)
        self._push_state_to(new_state, (dummy_ret_lab, call_ctx))

    def _detect_flow_descr_set(
        self, program_point, old_state: State, new_state: State, dummy_value: Value
    ):
        call_stmt: ast.Assign = self.get_stmt_by_point(program_point)
        assert isinstance(call_stmt, ast.Assign), call_stmt
        assert len(call_stmt.targets) == 1 and isinstance(
            call_stmt.targets[0], ast.Attribute
        )
        attribute: ast.Attribute = call_stmt.targets[0]
        attr: str = call_stmt.targets[0].attr

        call_lab, call_ctx = program_point

        ret_lab, dummy_ret_lab = self.get_setter_return_label(call_lab)
        objs = new_state.compute_value_of_expr(attribute.value)
        value = new_state.compute_value_of_expr(call_stmt.value)

        descr_sets = setattrs(objs, attr, value)
        if descr_sets.is_Any():
            dummy_value.transform_to_Any()

        for descr_set in descr_sets:
            if isinstance(descr_set, AnalysisMethod):
                entry_lab, exit_lab = descr_set.tp_function.tp_code
                instance = descr_set.tp_instance
                new_ctx: Tuple = merge(call_lab, instance.tp_address, call_ctx)

                self.entry_program_point_info[
                    (entry_lab, new_ctx)
                ] = AdditionalEntryInfo(
                    instance,
                    None,
                    descr_set.tp_module,
                    None,
                    None,
                )

                inter_flow = (
                    (call_lab, call_ctx),
                    (entry_lab, new_ctx),
                    (exit_lab, new_ctx),
                    (ret_lab, call_ctx),
                )
                self.inter_flows.add(inter_flow)
            else:
                raise NotImplementedError

        self._push_state_to(new_state, (dummy_ret_lab, call_ctx))

    # deal with cases such as class xxx
    def _detect_flow_classdef(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
    ):
        """
        prev
        |
        curr(call)
                entry

                exit
        return
        """
        call_lab, call_ctx = program_point
        entry_lab, exit_lab = self.add_sub_cfg(call_lab)
        return_lab = self.get_classdef_return_label(call_lab)
        self.inter_flows.add(
            (
                (call_lab, call_ctx),
                (entry_lab, call_ctx),
                (exit_lab, call_ctx),
                (return_lab, call_ctx),
            )
        )
        self.entry_program_point_info[(entry_lab, call_ctx)] = AdditionalEntryInfo(
            None,
            None,
            None,
            None,
            None,
        )

    def _detect_flow_call_class(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
    ):
        call_stmt: ast.Call = self.get_stmt_by_point(program_point)
        assert isinstance(call_stmt, ast.Call), call_stmt

        call_lab, call_ctx = program_point

        value: Value = new_state.compute_value_of_expr(call_stmt.func)
        # iterate all types to find which is callable
        for type in value:
            if isinstance(type, AnalysisClass):
                self._detect_flow_class(
                    program_point, old_state, new_state, dummy_value, type
                )

        if len(dummy_value):
            _, dummy_ret_lab = self.get_special_new_return_label(call_lab)
            dummy_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
            new_state.stack.write_var(dummy_stmt.id, Namespace_Local, dummy_value)
            self._push_state_to(new_state, (dummy_ret_lab, call_ctx))

    # deal with cases such as name()
    def _detect_flow_call(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
    ):

        call_stmt: ast.Call = self.get_stmt_by_point(program_point)
        assert isinstance(call_stmt, ast.Call), call_stmt

        call_lab, call_ctx = program_point
        # record
        address = record(call_lab, call_ctx)

        dummy_value_normal: Value = Value()

        value: Value = new_state.compute_value_of_expr(call_stmt.func)
        # iterate all types to find which is callable
        for type in value:
            # if isinstance(type, AnalysisClass):
            #     self._detect_flow_class(
            #         program_point, old_state, new_state, dummy_value_special, type
            #     )
            # such as list class
            if isinstance(type, ArtificialClass):
                one_direct_res = type(
                    tp_address=address,
                    tp_class=type,
                    tp_heap=new_state.heap,
                )
                dummy_value_normal.inject(one_direct_res)
            elif isinstance(type, ArtificialFunction):
                self._detect_flow_artificial_function(
                    program_point, old_state, new_state, dummy_value_normal, type
                )
            elif isinstance(type, AnalysisFunction):
                self._detect_flow_function(
                    program_point, old_state, new_state, dummy_value_normal, type
                )
            elif isinstance(type, AnalysisMethod):
                self._detect_flow_method(
                    program_point, old_state, new_state, dummy_value_normal, type
                )
            elif isinstance(type, ArtificialMethod):
                self._detect_flow_artificial_method(
                    program_point, old_state, new_state, dummy_value_normal, type
                )
            elif isinstance(type, Constructor):
                self._lambda_constructor(
                    program_point, old_state, new_state, dummy_value_normal, type
                )

        _, dummy_ret_lab = self.get_func_return_label(call_lab)
        dummy_ret_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
        new_state.stack.write_var(
            dummy_ret_stmt.id, Namespace_Local, dummy_value_normal
        )
        self._push_state_to(new_state, (dummy_ret_lab, call_ctx))

    # deal with class initialization
    # find __new__ and __init__ method
    # then use it to create class instance
    def _detect_flow_class(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
        type: AnalysisClass,
    ):
        call_lab, call_ctx = program_point
        new_stack, new_heap = new_state.stack, new_state.heap

        tp_address = record(call_lab, call_ctx)
        new_method, new_method_descr = _getattr(type, "__new__")
        assert len(new_method_descr) == 0, new_method_descr
        for new in new_method:
            if isinstance(new, Constructor):
                one_direct_res = new(
                    tp_address=tp_address, tp_class=type, tp_heap=new_heap
                )
                dummy_value.inject(one_direct_res)
            elif isinstance(new, AnalysisFunction):
                entry_lab, exit_lab = new.tp_code
                ret_lab, _ = self.get_special_new_return_label(call_lab)
                new_ctx = merge(call_lab, None, call_ctx)
                inter_flow = (
                    (call_lab, call_ctx),
                    (entry_lab, new_ctx),
                    (exit_lab, new_ctx),
                    (ret_lab, call_ctx),
                )
                self.inter_flows.add(inter_flow)
                self.entry_program_point_info[
                    (entry_lab, new_ctx)
                ] = AdditionalEntryInfo(
                    type_2_value(type),
                    None,
                    type.tp_module,
                    None,
                    None,
                )

    # detect flows of functions which have labels
    def _detect_flow_function(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
        type: AnalysisFunction,
    ):
        call_lab, call_ctx = program_point
        entry_lab, exit_lab = type.tp_code
        ret_lab, _ = self.get_func_return_label(call_lab)

        new_ctx: Tuple = merge(call_lab, None, call_ctx)
        inter_flow = (
            (call_lab, call_ctx),
            (entry_lab, new_ctx),
            (exit_lab, new_ctx),
            (ret_lab, call_ctx),
        )
        self.inter_flows.add(inter_flow)
        self.entry_program_point_info[(entry_lab, new_ctx)] = AdditionalEntryInfo(
            None,
            None,
            type.tp_module,
            type.tp_defaults,
            type.tp_kwdefaults,
        )

    # detect flow of analysis methods which have labels
    def _detect_flow_method(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
        type: AnalysisMethod,
    ):
        call_lab, call_ctx = program_point
        entry_lab, exit_lab = type.tp_function.tp_code
        instance = type.tp_instance
        function = type.tp_function
        new_ctx: Tuple = merge(call_lab, instance.tp_address, call_ctx)

        ret_lab, _ = self.get_func_return_label(call_lab)
        self.entry_program_point_info[(entry_lab, new_ctx)] = AdditionalEntryInfo(
            type_2_value(instance),
            None,
            type.tp_module,
            function.tp_defaults,
            function.tp_kwdefaults,
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

        new_state: State = deepcopy_state(old_state)
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
        new_stack, new_heap = new_state.stack, new_state.heap
        rhs_value: Value = new_state.compute_value_of_expr(stmt.value)
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
        elif self.is_class_init_call_point(program_point):
            return self._transfer_call_normal(program_point, old_state, new_state)
        elif self.is_getter_call_point(program_point):
            return self._transfer_call_getter(program_point, old_state, new_state)
        elif self.is_setter_call_point(program_point):
            return self._transfer_call_setter(program_point, old_state, new_state)

    def _transfer_call_classdef(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        new_stack, new_heap = new_state.stack, new_state.heap
        # new_stack, new_heap = new_state
        new_stack.add_new_frame()
        return new_state

    def _transfer_call_normal(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        # Normal call has form: func_name(args, keywords)
        call_stmt: ast.Call = self.get_stmt_by_point(program_point)
        assert isinstance(call_stmt, ast.Call), call_stmt
        new_stack, _ = new_state.stack, new_state.heap

        # new namespace to simulate function call
        new_stack.add_new_frame()

        # deal with positional args
        # for instance, func(1, "hello") would be ["1": {int}, "2": {str}]
        args: List[ast.expr] = call_stmt.args
        for idx, arg in enumerate(args, 1):
            if isinstance(arg, ast.Starred):
                raise NotImplementedError(arg)
            arg_value = new_state.compute_value_of_expr(arg)
            new_stack.write_var(str(idx), Namespace_Local, arg_value)

        # set the length of pos args
        setattr(new_stack.frames[-1].f_locals, POS_ARG_LEN, len(args))

        # deal with keyword args
        keywords: List[ast.keyword] = call_stmt.keywords
        for keyword in keywords:
            # (NULL identifier for **kwargs)
            if keyword.arg is None:
                raise NotImplementedError(keyword)
            keyword_value = new_state.compute_value_of_expr(keyword.value)
            new_stack.write_var(keyword.arg, Namespace_Local, keyword_value)

        return new_state

    def _transfer_call_getter(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        call_stmt: ast.stmt = self.get_stmt_by_point(program_point)
        assert isinstance(call_stmt, ast.Attribute), call_stmt

        # new_stack, new_heap = new_state
        new_stack, new_heap = new_state.stack, new_state.heap
        new_stack.add_new_frame()

        target_value = new_state.compute_value_of_expr(call_stmt.value)
        for target_typ in target_value:
            _, attr_value = _getattr(target_typ, call_stmt.attr)
            for attr_typ in attr_value:
                if isinstance(attr_typ, AnalysisDescriptorGetFunction):
                    instance = attr_typ.tp_obj
                    instance_value = create_value_with_type(instance)
                    new_stack.write_var("1", Namespace_Local, instance_value)
                    owner = attr_typ.tp_objtype
                    owner_value = create_value_with_type(owner)
                    new_stack.write_var("2", Namespace_Local, owner_value)
                    setattr(new_stack.frames[-1].f_locals, POS_ARG_LEN, 2)
        return new_state

    def _transfer_call_setter(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        call_stmt: ast.stmt = self.get_stmt_by_point(program_point)
        assert isinstance(call_stmt, ast.Assign)
        assert len(call_stmt.targets) == 1 and isinstance(
            call_stmt.targets[0], ast.Attribute
        )

        new_stack, new_heap = new_state.stack, new_state.heap
        # new_stack, new_heap = new_state
        new_stack.add_new_frame()

        attribute: ast.Attribute = call_stmt.targets[0]
        attr: str = call_stmt.targets[0].attr

        lhs_value = new_state.compute_value_of_expr(attribute.value)
        rhs_value = new_state.compute_value_of_expr(call_stmt.value)
        for target_typ in lhs_value:
            descr_sets = _setattr(target_typ, attr, rhs_value)
            for attr_typ in descr_sets:
                if isinstance(attr_typ, AnalysisDescriptorSetFunction):
                    instance = attr_typ.tp_obj
                    instance_value = create_value_with_type(instance)
                    new_stack.write_var("1", Namespace_Local, instance_value)
                    value = attr_typ.tp_value
                    value_value = create_value_with_type(value)
                    new_stack.write_var("2", Namespace_Local, value_value)
                    setattr(new_stack.frames[-1].f_locals, POS_ARG_LEN, 2)

        return new_state

    # consider current global namespace
    def transfer_entry(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        stmt = self.get_stmt_by_point(program_point)

        new_stack, new_heap = new_state.stack, new_state.heap

        # add a special return flag to denote return values
        new_stack.write_var(RETURN_FLAG, "local", Value())

        # is self.self_info[program_point] is not None, it means
        # this is a class method call
        # we pass instance information, module name to entry labels
        (
            instance_info,
            init_info,
            module_info,
            defaults_info,
            kwdefaults_info,
        ) = self.entry_program_point_info[program_point]
        if instance_info:
            new_stack.write_var(str(0), Namespace_Local, instance_info)
        if init_info:
            # setattr(new_stack.frames[-1].f_locals, INIT_FLAG, None)
            new_stack.write_var(
                RETURN_FLAG, Namespace_Local, type_2_value(instance_info)
            )
        if module_info:
            new_stack.check_module_diff(module_info)

        if isinstance(stmt, ast.arguments):
            # Positional and keyword arguments
            start_pos = 0 if instance_info else 1
            arg_flags = parse_positional_args(start_pos, stmt, new_state)
            arg_flags = parse_keyword_args(arg_flags, stmt, new_state)
            _ = parse_default_args(arg_flags, stmt, new_state, defaults_info)
            parse_kwonly_args(stmt, new_state, kwdefaults_info)

        return new_state

    # transfer exit label
    def transfer_exit(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        new_stack, new_heap = new_state.stack, new_state.heap
        return_value = new_stack.read_var(RETURN_FLAG)
        # if no explicit return, add None
        if len(return_value) == 0:
            none_value = type_2_value(None_Instance)
            new_stack.write_var(RETURN_FLAG, Namespace_Local, none_value)

        return new_state

    # transfer return label
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
            raise NotImplementedError

    def transfer_return_setter(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.Assign,
    ):
        # new_stack, new_heap = new_state
        new_stack, new_heap = new_state.stack, new_state.heap
        new_stack.pop_frame()
        return new_state

    def transfer_return_name(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.Name,
    ):
        # new_stack, new_heap = new_state
        new_stack, new_heap = new_state.stack, new_state.heap
        return_value: Value = new_stack.read_var(RETURN_FLAG)
        # if hasattr(new_stack.frames[-1].f_locals, INIT_FLAG):
        #     return_value = new_stack.read_var("self")
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
        name = stmt.names[0].name
        asname = stmt.names[0].asname
        if asname is None:
            # execute normal import
            import_a_module(name)
            # get top-level name
            name = name.partition(".")[0]
            # but we only want top-level name
            module = import_a_module(name)
        else:
            name = asname
            module = import_a_module(name)

        new_state.stack.write_var(name, Namespace_Local, module)
        logger.debug("Import module {}".format(module))
        return new_state

    # from xxx import yyy, zzz as aaa
    def transfer_ImportFrom(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.ImportFrom,
    ):
        package = None
        if stmt.level > 0:
            package: str = getattr(new_state.stack.frames[-1].f_globals, PACKAGE_FLAG)

        new_stack = new_state.stack
        logger.debug("ImportFrom module {}".format(stmt.module))
        modules: Value = import_a_module(stmt.module, package, stmt.level)

        for alias in stmt.names:
            name = alias.name
            asname = alias.asname
            for module in modules:
                direct_res, descr_gets = _getattr(module, name)
                assert len(descr_gets) == 0
                if len(direct_res) == 0:
                    sub_module_name = f"{stmt.module}.{name}"
                    sub_module = import_a_module(sub_module_name, package, stmt.level)
                    direct_res.inject(sub_module)
                if asname is None:
                    new_stack.write_var(name, Namespace_Local, direct_res)
                else:
                    new_stack.write_var(asname, Namespace_Local, direct_res)
        return new_state

    def transfer_return_classdef(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        # return stuff
        return_lab, return_ctx = program_point
        call_lab = self.get_classdef_call_label(return_lab)
        # stmt
        stmt: ast.ClassDef = self.get_stmt_by_point(program_point)
        new_stack = new_state.stack

        # class frame
        f_locals = new_stack.top_frame().f_locals
        new_stack.pop_frame()

        # class name
        cls_name: str = stmt.name
        module: str = getattr(new_stack.frames[-1].f_globals, NAME_FLAG)

        value: Value = Value()
        bases = compute_bases(new_state, stmt)
        call_lab = self.get_classdef_call_label(return_lab)
        analysis_class: AnalysisClass = AnalysisClass(
            tp_uuid=call_lab,
            tp_module=module,
            tp_bases=bases,
            tp_dict=f_locals,
            tp_code=(call_lab, return_lab),
        )
        value.inject_type(analysis_class)
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
        entry_lab, exit_lab = self.add_sub_cfg(lab)

        defaults, kwdefaults = compute_function_defaults(new_state, node)

        func_module: str = getattr(new_state.stack.frames[-1].f_globals, PACKAGE_FLAG)

        value = Value()
        value.inject_type(
            AnalysisFunction(
                tp_uuid=lab,
                tp_module=func_module,
                tp_code=(entry_lab, exit_lab),
                tp_defaults=defaults,
                tp_kwdefaults=kwdefaults,
            )
        )

        new_state.stack.write_var(node.name, Namespace_Local, value)
        return new_state

    def transfer_If(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.If,
    ) -> State:
        return new_state

    def transfer_While(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.While,
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
        new_stack: Stack = new_state.stack
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
        new_stack, new_heap = new_state.stack, new_state.heap
        # new_stack, _ = new_state
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
        new_stack, new_heap = new_state.stack, new_state.heap
        # new_stack, _ = new_state
        new_stack.write_var(name, Namespace_Nonlocal, None)

        return new_state

    def transfer_Delete(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.Delete,
    ) -> State:
        # new_stack = new_state[0]
        new_stack, new_heap = new_state.stack, new_state.heap
        assert len(stmt.targets) == 1, stmt
        assert isinstance(stmt.targets[0], ast.Name), stmt
        name = stmt.targets[0].id
        new_stack.delete_var(name)
        return new_state

    def transfer_Pass(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.Pass,
    ) -> State:
        return new_state

    def transfer_Break(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.Break,
    ) -> State:
        return new_state

    def transfer_Continue(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.Continue,
    ) -> State:
        return new_state


sys.Analysis = Analysis
