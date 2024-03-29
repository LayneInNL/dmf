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

import astor

from dmf.analysis.analysis_types import (
    ArtificialFunction,
    AnalysisFunction,
    AnalysisClass,
    AnalysisMethod,
    None_Instance,
    AnalysisInstance,
    Generator_Type,
    AnalysisDescriptor,
    AnalysisModule,
)
from dmf.analysis.analysis_types import (
    Constructor,
    ArtificialClass,
)
from dmf.analysis.analysisbase import AnalysisBase, ProgramPoint
from dmf.analysis.artificial_basic_types import ArtificialMethod
from dmf.analysis.builtin_functions import import_a_module
from dmf.analysis.context_sensitivity import merge, record
from dmf.analysis.exceptions import ParsingDefaultsError, ParsingKwDefaultsError
from dmf.analysis.gets_sets import (
    getattrs,
    analysis_getattr,
    setattrs,
    analysis_setattr,
)
from dmf.analysis.heap import Heap
from dmf.analysis.implicit_names import (
    POS_ARG_LEN,
    INIT_FLAG,
    RETURN_FLAG,
    MODULE_PACKAGE_FLAG,
    MODULE_NAME_FLAG,
    GENERATOR,
    GENERATOR_ADDRESS,
    numeric_methods,
    reversed_numeric_methods,
    augmented_numeric_methods,
    unary_methods,
)
from dmf.analysis.name_extractor import NameExtractor
from dmf.analysis.special_types import Any
from dmf.analysis.state import (
    State,
    BOTTOM,
    compare_states,
    is_bot_state,
    deepcopy_state,
    Stack,
    merge_states,
)
from dmf.analysis.typeshed_types import (
    TypeshedFunction,
    TypeshedClass,
)
from dmf.analysis.union_namespace import UnionNamespace
from dmf.analysis.value import Value, type_2_value
from dmf.log.logger import logger

Namespace_Local = "local"
Namespace_Nonlocal = "nonlocal"
Namespace_Global = "global"

AdditionalEntryInfo = namedtuple(
    "AdditionalEntryInfo",
    [
        "instance_info",
        "init_info",
        "module_info",
        "defaults_info",
        "kwdefaults_info",
        "generator_info",
    ],
)


class Analysis(AnalysisBase):
    def _setup_main(self, main_abs_file_path: str):
        # prepare information for __main__ module
        cfg = self.synthesis_cfg(main_abs_file_path)
        entry_label, exit_label = self.merge_cfg_info(cfg)
        main_module = AnalysisModule(
            tp_name="__main__", tp_package="", tp_code=(entry_label, exit_label)
        )
        sys.analysis_modules["__main__"] = type_2_value(main_module)
        main_module_dict = main_module.tp_dict

        self.extremal_point: ProgramPoint = (entry_label, ())
        self.module_entry_info[self.extremal_point] = main_module_dict

    def __init__(self, main_abs_file_path: str):
        super().__init__()
        self.module_entry_info: Dict[ProgramPoint, UnionNamespace] = {}
        # work list
        self.work_list: Deque[Tuple[ProgramPoint, ProgramPoint]] = deque()
        # extremal value
        self.extremal_value: State = State(Stack())
        self.heap = Heap()
        # start point
        self.entry_program_point_info: Dict[ProgramPoint, AdditionalEntryInfo] = {}
        # record module name so that the analysis can execute exec
        self.analysis_list: defaultdict[ProgramPoint, State | BOTTOM] = defaultdict(
            lambda: BOTTOM
        )
        self.analysis_effect_list: Dict[ProgramPoint, State] = {}

        self._setup_main(main_abs_file_path)
        self.analysis_list[self.extremal_point] = self.extremal_value

    def compute_fixed_point(self):
        self.initialize()
        self.iterate()
        self.present()

    def get_analysis_effect_list(self):
        return self.analysis_effect_list

    def initialize(self):
        self.work_list.extendleft(self.generate_flow(self.extremal_point))
        self.extremal_value = deepcopy_state(self.extremal_value, self.extremal_point)

        sys.heap = self.heap
        sys.analysis = self

    def _push_state_to(self, state: State, program_point: ProgramPoint):
        old: State | BOTTOM = self.analysis_list[program_point]
        if not compare_states(state, old):
            state = merge_states(state, old)
            self.analysis_list[program_point]: State = state
            self.detect_flow(program_point)
            added_program_points = self.generate_flow(program_point)
            self.work_list.extendleft(added_program_points)

        # additional flows?
        self.work_list.extendleft(reversed(sys.prepend_flows))
        sys.prepend_flows.clear()

    def iterate(self):
        # as long as there are flows in work_list
        while self.work_list:
            logger.warning(
                f"worklist: {len(self.work_list)}, analysis list {len(self.analysis_list)}"
            )
            # get the leftmost one
            program_point1, program_point2 = self.work_list.popleft()

            transferred: State | BOTTOM = self.transfer(program_point1)
            self._push_state_to(transferred, program_point2)

    def present(self):
        for program_point in list(self.analysis_list):
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
                logger.critical(f"Program point {program_point}")

        logger.info(self.heap)

    # based on current program point, update self.IF
    def detect_flow(self, program_point: ProgramPoint) -> None:
        if self.is_call_point(program_point):
            stmt = self.get_stmt_by_point(program_point)
            logger.debug(
                f"Current lambda point: {program_point} {astor.to_source(stmt)}"
            )
            # curr_state is the previous program point
            next_state: State = self.analysis_list[program_point]
            dummy_value: Value = Value()
            next_next_state: State = deepcopy_state(next_state, program_point)

            # class definition
            if self.is_classdef_call_point(program_point):
                self._add_analysisclass_interflow(program_point)
            elif self.is_normal_call_point(program_point):
                self._detect_flow_call(
                    program_point, next_state, next_next_state, dummy_value
                )
                next_next_class_state = deepcopy_state(next_state, program_point)
                dummy_class_value = Value()
                self._detect_flow_call_class(
                    program_point, next_state, next_next_class_state, dummy_class_value
                )
            # init function during class initialization
            elif self.is_class_init_call_point(program_point):
                self.detect_flow_class_init(
                    program_point, next_state, next_next_state, dummy_value
                )
            elif self.is_right_magic_call_point(program_point):
                self._detect_flow_right_magic(
                    program_point, next_state, next_next_state, dummy_value
                )
            elif self.is_left_magic_call_point(program_point):
                self._detect_flow_left_magic(
                    program_point, next_state, next_next_state, dummy_value
                )
            elif self.is_del_magic_call_point(program_point):
                self._detect_flow_del_magic(
                    program_point, next_state, next_next_state, dummy_value
                )
            else:
                raise NotImplementedError(program_point)

    # deal with cases such as class xxx
    def _add_analysisclass_interflow(self, program_point: ProgramPoint):
        call_lab, call_ctx = program_point
        entry_lab, exit_lab = self.add_sub_cfg(call_lab)
        ret_lab = self.get_classdef_return_label(call_lab)
        self.inter_flows.add(
            (
                (call_lab, call_ctx),
                (entry_lab, call_ctx),
                (exit_lab, call_ctx),
                (ret_lab, call_ctx),
            )
        )
        self.entry_program_point_info[(entry_lab, call_ctx)] = AdditionalEntryInfo(
            None, None, None, None, None, False
        )

    # detect flows of functions which have labels
    def _add_analysisdescriptor_interflow(
        self,
        program_point: ProgramPoint,
        type: AnalysisDescriptor,
        ret_lab: int,
    ):
        self._add_analysisfunction_interflow(program_point, type.tp_function, ret_lab)

    # detect flows of functions which have labels
    def _add_analysisfunction_interflow(
        self, program_point: ProgramPoint, type: AnalysisFunction, ret_lab: int
    ):
        call_lab, call_ctx = program_point
        entry_lab, exit_lab = type.tp_code

        # used by generator
        tp_address = record(call_lab, call_ctx)

        # a pure function has no receiver object. We employ the approach Mixed-CFA described in
        # JSAI: A Static Analysis Platform for JavaScript
        # new_ctx: Tuple = merge(call_lab, type.tp_address, call_ctx)
        if sys.depth == 1:
            new_ctx: Tuple = (call_lab,)
        elif sys.depth == 2:
            new_ctx: Tuple = type.tp_address + (call_lab,)
        else:
            raise NotImplementedError
        self.entry_program_point_info[(entry_lab, new_ctx)] = AdditionalEntryInfo(
            None,
            None,
            type.tp_module,
            type.tp_defaults,
            type.tp_kwdefaults,
            (type.tp_generator, tp_address) if type.tp_generator else type.tp_generator,
        )

        inter_flow = (
            (call_lab, call_ctx),
            (entry_lab, new_ctx),
            (exit_lab, new_ctx),
            (ret_lab, call_ctx),
        )
        self.inter_flows.add(inter_flow)

    def _add_analysismethod_interflow(
        self, program_point: ProgramPoint, type: AnalysisMethod, ret_lab: int
    ):

        call_lab, call_ctx = program_point
        entry_lab, exit_lab = type.tp_function.tp_code
        # may be a class instance, may be a class
        instance: AnalysisInstance = type.tp_instance
        function: AnalysisFunction = type.tp_function
        new_ctx: Tuple = merge(call_lab, instance.tp_address, call_ctx)

        self.entry_program_point_info[(entry_lab, new_ctx)] = AdditionalEntryInfo(
            type_2_value(instance),
            INIT_FLAG if self.is_class_init_call_point(program_point) else None,
            type.tp_module,
            function.tp_defaults,
            function.tp_kwdefaults,
            False,
        )

        inter_flow = (
            (call_lab, call_ctx),
            (entry_lab, new_ctx),
            (exit_lab, new_ctx),
            (ret_lab, call_ctx),
        )
        self.inter_flows.add(inter_flow)

    # find out implicit special methods of del statement
    def _detect_flow_del_magic(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
    ):
        """
        The considered statements are
        del x -- a name
        del x[i] -- a subscript __delitem__
        del x.y -- a descriptor __delete__

        :param program_point:
        :param old_state:
        :param new_state:
        :param dummy_value:
        :return:
        """
        stmt: ast.Delete = self.get_stmt_by_point(program_point)
        target: ast.expr = stmt.targets[0]

        call_lab, call_ctx = program_point
        ret_lab, dummy_ret_lab = self.get_del_magic_return_label(call_lab)

        # find out descriptors
        if isinstance(target, ast.Attribute):
            receiver_value = new_state.compute_value_of_expr(target.value)
            descriptor_result = setattrs(receiver_value, target.attr, None)
            for descriptor in descriptor_result:
                self._add_analysisdescriptor_interflow(
                    program_point, descriptor, ret_lab
                )
        elif isinstance(target, ast.Subscript):
            receiver_value = new_state.compute_value_of_expr(target.value)
            for one_receiver in receiver_value:
                one_receiver_type = one_receiver.tp_class
                direct_result = analysis_getattr(one_receiver_type, "__delitem__")
                for one_direct in direct_result:
                    # turn into anlaysis method
                    if isinstance(one_direct, AnalysisFunction):
                        analysis_method = AnalysisMethod(
                            tp_function=one_direct, tp_instance=one_receiver
                        )
                        self._add_analysismethod_interflow(
                            program_point, analysis_method, ret_lab
                        )
        else:
            raise NotImplementedError(stmt)

        self._push_state_to(new_state, (dummy_ret_lab, call_ctx))

    def _detect_flow_left_magic(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
    ):
        """
        find out implicit function calls for lhs expression
        for instance, x.y = xxx, may be a descriptor
        x[y] = xxx, call __getitem__
        """
        stmt: ast.Assign = self.get_stmt_by_point(program_point)

        call_lab, call_ctx = program_point
        ret_lab, dummy_ret_lab = self.get_left_magic_return_label(call_lab)
        target = stmt.targets[0]
        # find out descriptors
        if isinstance(target, ast.Attribute):
            receiver_value = new_state.compute_value_of_expr(target.value)
            rhs_value = new_state.compute_value_of_expr(stmt.value)
            descriptor_result = setattrs(receiver_value, target.attr, rhs_value)

            for descriptor in descriptor_result:
                if isinstance(descriptor, AnalysisDescriptor):
                    self._add_analysisdescriptor_interflow(
                        program_point, descriptor, ret_lab
                    )
        elif isinstance(target, ast.Subscript):
            receiver_value = new_state.compute_value_of_expr(target.value)
            for one_receiver in receiver_value:
                one_receiver_type = one_receiver.tp_class
                direct_result = analysis_getattr(one_receiver_type, "__setitem__")
                for one_direct in direct_result:
                    if isinstance(one_direct, AnalysisFunction):
                        analysis_method = AnalysisMethod(
                            tp_function=one_direct, tp_instance=one_receiver
                        )
                        self._add_analysismethod_interflow(
                            program_point, analysis_method, ret_lab
                        )
        else:
            raise NotImplementedError(stmt)

        self._push_state_to(new_state, (dummy_ret_lab, call_ctx))

    # detect flows of magic methods.
    # for example, a + b we retrieve a.__add__
    def _detect_flow_right_magic(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
    ):
        # detect flow of possibly magic methods
        # for instance, a = x + y. There may be an implicit x.__add__
        # expr is guaranteed to be ast.expr type
        expr: ast.expr = self.get_stmt_by_point(program_point)

        call_lab, call_ctx = program_point
        ret_lab, dummy_ret_lab = self.get_right_magic_return_label(call_lab)

        if isinstance(expr, ast.BinOp):
            # retrieve magic methods
            normal_operator_name = numeric_methods[type(expr.op)]
            # retrieve augmented magic methods
            augmented_operator_name = augmented_numeric_methods[type(expr.op)]

            # left expr
            lhs = expr.left
            # left expr value
            lhs_value = new_state.compute_value_of_expr(lhs)
            rhs_value = new_state.compute_value_of_expr(expr.right)

            # for instance
            # x + y
            # return node
            # dummy return node
            for one_receiver in lhs_value:
                one_receiver_type = one_receiver.tp_class
                for operator_name in [normal_operator_name]:
                    # for operator_name in [normal_operator_name, augmented_operator_name]:
                    direct_res = analysis_getattr(one_receiver_type, operator_name)
                    for one_direct_res in direct_res:
                        # typeshed function
                        if isinstance(one_direct_res, TypeshedFunction):
                            one_value = one_direct_res.refine_self_to_value()
                            dummy_value.inject(one_value)
                        elif isinstance(one_direct_res, AnalysisFunction):
                            analysis_method = AnalysisMethod(
                                tp_function=one_direct_res, tp_instance=one_receiver
                            )
                            self._add_analysismethod_interflow(
                                program_point, analysis_method, ret_lab
                            )
                        elif isinstance(one_direct_res, ArtificialFunction):
                            one_value = one_direct_res(one_receiver, rhs_value)
                            dummy_value.inject(one_value)

        elif isinstance(expr, ast.UnaryOp):
            if isinstance(expr.op, ast.Not):
                one_value = new_state.compute_value_of_expr(
                    ast.NameConstant(value=True)
                )
                dummy_value.inject(one_value)
            else:
                unary_method_name = unary_methods[type(expr.op)]
                receiver_value = new_state.compute_value_of_expr(expr.operand)
                for one_receiver in receiver_value:
                    direct_res = analysis_getattr(one_receiver, unary_method_name)
                    for one_direct_res in direct_res:
                        # typeshed function
                        if isinstance(one_direct_res, TypeshedFunction):
                            one_value = one_direct_res.refine_self_to_value()
                            dummy_value.inject(one_value)
                        elif isinstance(one_direct_res, AnalysisFunction):
                            analysis_method = AnalysisMethod(
                                tp_function=one_direct_res, tp_instance=one_receiver
                            )
                            self._add_analysismethod_interflow(
                                program_point, analysis_method, ret_lab
                            )
                        elif isinstance(one_direct_res, ArtificialFunction):
                            one_value = one_direct_res(one_receiver)
                            dummy_value.inject(one_value)

        elif isinstance(expr, ast.Yield):
            one_value = new_state.compute_value_of_expr(expr)
            # used by generators
            return_value = new_state.stack.read_var(RETURN_FLAG)
            return_value.inject(one_value)
            new_state.stack.write_var(RETURN_FLAG, "local", return_value)
            # this return value is controlled by .send or just a None
            dummy_value.inject(Value.make_any())
        elif isinstance(expr, ast.YieldFrom):
            # yield from gets value from the delegated iterator.
            one_value = new_state.compute_value_of_expr(expr)
            new_state.stack.write_var(RETURN_FLAG, "local", Value.make_any())
            dummy_value.inject(one_value)
        elif isinstance(expr, ast.Compare):
            # left op right
            # I looked into the example projects, just return bool is fine.
            one_value = new_state.compute_value_of_expr(expr)
            dummy_value.inject(one_value)

        elif isinstance(expr, ast.Attribute):
            # compute receiver value
            lhs_value = new_state.compute_value_of_expr(expr.value)
            descriptor_result = getattrs(lhs_value, expr.attr)

            # add flows of possible descriptors
            for descriptor in descriptor_result:
                if isinstance(descriptor, AnalysisDescriptor):
                    self._add_analysisfunction_interflow(
                        program_point, descriptor.tp_function, ret_lab
                    )
                else:
                    dummy_value.inject(descriptor)
        elif isinstance(expr, ast.Subscript):
            # deal with something = x.y
            # at first compute x
            receiver_value = new_state.compute_value_of_expr(expr.value)
            field_value = new_state.compute_value_of_expr(expr.slice)
            for each_receiver in receiver_value:
                each_subscript_type = each_receiver.tp_class
                # then find __getitem__ based on its type
                res = analysis_getattr(each_subscript_type, "__getitem__")
                for each_res in res:
                    # special methods can be user-defined functions
                    if isinstance(each_res, AnalysisFunction):
                        _analysis_method = AnalysisMethod(
                            tp_function=each_res, tp_instance=each_receiver
                        )
                        self._add_analysismethod_interflow(
                            program_point, _analysis_method, ret_lab
                        )
                    # such as list.append
                    elif isinstance(each_res, ArtificialFunction):
                        _value = each_res(
                            type_2_value(each_receiver),
                            field_value,
                        )
                        dummy_value.inject(_value)
                    elif isinstance(each_res, TypeshedFunction):
                        _value = each_res.refine_self_to_value()
                        dummy_value.inject(_value)
        elif isinstance(expr, ast.Slice):
            slice_value = new_state.compute_value_of_expr(ast.Name(id="slice"))
            for one_slice in slice_value:
                if isinstance(one_slice, TypeshedClass):
                    one_value = one_slice()
                    dummy_value.inject(one_value)
                else:
                    raise NotImplementedError(one_slice)
        elif isinstance(
            expr,
            (
                ast.Str,
                ast.FormattedValue,
                ast.JoinedStr,
                ast.Bytes,
                ast.NameConstant,
                ast.Ellipsis,
                ast.Num,
                ast.Name,
                ast.Index,
            ),
        ):
            one_value = new_state.compute_value_of_expr(expr)
            dummy_value.inject(one_value)
        elif isinstance(
            expr,
            (
                ast.BoolOp,
                ast.Lambda,
                ast.IfExp,
                ast.Call,
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
                ast.GeneratorExp,
                ast.Await,
                ast.Constant,
                ast.List,
                ast.Tuple,
                ast.Dict,
                ast.Set,
                ast.Starred,
            ),
        ):
            raise NotImplementedError(expr)
        else:
            raise NotImplementedError(expr)

        dummy_ret_expr = self.get_stmt_by_label(dummy_ret_lab)
        # dummy_ret_expr must be an ast.Name
        assert isinstance(dummy_ret_expr, ast.Name)
        new_state.stack.write_var(dummy_ret_expr.id, Namespace_Local, dummy_value)
        self._push_state_to(new_state, (dummy_ret_lab, call_ctx))

    # deal with calling __init__ implicitly during class initialization.
    # this will only happen when xxx = Class().
    def detect_flow_class_init(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        dummy_value: Value,
    ):
        call_lab, call_ctx = program_point
        ret_lab, dummy_ret_lab = self.get_special_init_return_label(call_lab)

        call_stmt: ast.Call = self.get_stmt_by_label(call_lab)
        new_stack = new_state.stack
        inits: Value = new_state.compute_value_of_expr(call_stmt.func)

        # special init
        # one case is user defined function
        # one case is artificial function
        # one case is Any
        # otherwise ignored
        for init in inits:
            if init is Any:
                dummy_value.inject(Any)
                break
            elif isinstance(init, AnalysisMethod):
                self._add_analysismethod_interflow(program_point, init, ret_lab)
            elif isinstance(init, ArtificialMethod):
                args, keywords = new_state.compute_func_args(
                    call_stmt.args, call_stmt.keywords
                )
                one_direct_res = init(*args, **keywords)
                dummy_value.inject(one_direct_res)
            else:
                pass

        dummy_ret_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
        new_stack.write_var(dummy_ret_stmt.id, Namespace_Local, dummy_value)
        self._push_state_to(new_state, (dummy_ret_lab, call_ctx))

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
        tp_address = record(call_lab, call_ctx)
        ret_lab, dummy_ret_lab = self.get_special_new_return_label(call_lab)

        value: Value = new_state.compute_value_of_expr(call_stmt.func)
        # iterate all types to find which is callable
        for type in value:
            if isinstance(type, AnalysisClass):
                new_method = analysis_getattr(type, "__new__")
                for new in new_method:
                    if isinstance(new, Constructor):
                        one_direct_res = new(tp_address=tp_address, tp_class=type)
                        dummy_value.inject(one_direct_res)
                    elif isinstance(new, AnalysisFunction):
                        analysis_method = AnalysisMethod(
                            tp_function=new, tp_instance=type
                        )
                        self._add_analysismethod_interflow(
                            program_point, analysis_method, ret_lab
                        )
                    elif new is Any:
                        dummy_value.inject(type)

        # if len(dummy_value):
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

        call_lab, call_ctx = program_point
        ret_lab, dummy_ret_lab = self.get_func_return_label(call_lab)
        # record
        address = record(call_lab, call_ctx)

        value: Value = new_state.compute_value_of_expr(call_stmt.func)
        # iterate all types to find which is callable
        for type in value:
            if type is Any:
                dummy_value.inject(type)
            elif isinstance(type, AnalysisClass):
                logger.info("Skip AnalysisClass")
            elif isinstance(type, AnalysisFunction):
                self._add_analysisfunction_interflow(program_point, type, ret_lab)
            elif isinstance(type, AnalysisMethod):
                self._add_analysismethod_interflow(program_point, type, ret_lab)
            elif isinstance(type, AnalysisInstance):
                one_direct_result = analysis_getattr(type.tp_class, "__call__")
                for one in one_direct_result:
                    if isinstance(one, AnalysisFunction):
                        one_method = AnalysisMethod(tp_function=one, tp_instance=type)
                        self._add_analysismethod_interflow(
                            program_point, one_method, ret_lab
                        )
            # artificial related types
            elif isinstance(type, ArtificialClass):
                computed_args, computed_kwargs = new_state.compute_func_args(
                    call_stmt.args, call_stmt.keywords
                )
                one_direct_res = type(address, type, *computed_args, **computed_kwargs)
                dummy_value.inject(one_direct_res)
            elif isinstance(type, (ArtificialFunction, ArtificialMethod)):
                computed_args, computed_kwargs = new_state.compute_func_args(
                    call_stmt.args, call_stmt.keywords
                )
                res = type(*computed_args, **computed_kwargs)
                dummy_value.inject(res)
            elif isinstance(type, Constructor):
                # correspond to object.__new__(cls)
                # it has the form of temp_func(cls)
                stmt = self.get_stmt_by_point(program_point)
                types = new_state.compute_value_of_expr(stmt.args[0])
                assert len(types) == 1
                for cls in types:
                    instance = type(address, cls)
                    dummy_value.inject_type(instance)

            # type is a typeshed class, for example, slice
            elif isinstance(type, TypeshedClass):
                typeshed_instance = type()
                dummy_value.inject(typeshed_instance)
            elif isinstance(type, TypeshedFunction):
                one_value = type.refine_self_to_value()
                dummy_value.inject(one_value)
            else:
                raise NotImplementedError(type)

        dummy_ret_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
        new_state.stack.write_var(dummy_ret_stmt.id, Namespace_Local, dummy_value)
        self._push_state_to(new_state, (dummy_ret_lab, call_ctx))

    def transfer(self, program_point: ProgramPoint) -> State | BOTTOM:
        stmt = self.get_stmt_by_point(program_point)
        logger.info(f"Current program point1 {program_point} {astor.to_source(stmt)}")

        # if old_state is BOTTOM, skip this transfer
        old_state: State = self.analysis_list[program_point]
        if is_bot_state(old_state):
            return BOTTOM

        new_state: State = deepcopy_state(old_state, program_point)
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
        new_stack = new_state.stack
        rhs_value: Value = new_state.compute_value_of_expr(stmt.value)
        target: ast.expr = stmt.targets[0]
        if isinstance(target, ast.Name):
            new_stack.write_var(target.id, Namespace_Local, rhs_value)
        elif isinstance(target, (ast.List, ast.Tuple)):
            name_extractor = NameExtractor()
            all_names = name_extractor.build(target)
            for name in all_names:
                new_stack.write_var(name, Namespace_Local, Value.make_any())
        else:
            raise NotImplementedError(target)
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
        elif self.is_right_magic_call_point(program_point):
            return self._transfer_call_right_magic(program_point, old_state, new_state)
        elif self.is_left_magic_call_point(program_point):
            return self._transfer_call_left_magic(program_point, old_state, new_state)
        elif self.is_del_magic_call_point(program_point):
            return self._transfer_call_del_magic(program_point, old_state, new_state)
        else:
            raise NotImplementedError

    def _transfer_call_del_magic(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        # add a new frame
        new_state.stack.add_new_frame()
        # get expr
        del_stmt: ast.Delete = self.get_stmt_by_point(program_point)
        target: ast.expr = del_stmt.targets[0]
        if isinstance(target, ast.Attribute):
            # del x.y
            receiver_value = new_state.compute_value_of_expr(target.value)
            for receiver_type in receiver_value:
                descriptor_result = analysis_setattr(receiver_type, target.attr, None)
                for descriptor in descriptor_result:
                    if isinstance(descriptor, AnalysisDescriptor):
                        args = descriptor.tp_args
                        for idx, arg in enumerate(args, 1):
                            new_state.stack.write_var(str(idx), Namespace_Local, arg)
                        setattr(
                            new_state.stack.frames[-1].f_locals, POS_ARG_LEN, len(args)
                        )
            return new_state
        elif isinstance(target, ast.Subscript):
            # del a[1]
            receiver_value = new_state.compute_value_of_expr(target.value)
            key_value = new_state.compute_value_of_expr(target.slice)
            args = [key_value]
            for idx, arg in enumerate(args, 1):
                new_state.stack.write_var(str(idx), Namespace_Local, arg)
            setattr(new_state.stack.frames[-1].f_locals, POS_ARG_LEN, len(args))
            return new_state
        else:
            raise NotImplementedError(program_point)

    def _transfer_call_left_magic(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        # add a new frame
        new_state.stack.add_new_frame()
        # get expr
        assign_stmt: ast.Assign = self.get_stmt_by_point(program_point)
        target = assign_stmt.targets[0]
        if isinstance(target, ast.Attribute):
            attribute: ast.Attribute = assign_stmt.targets[0]
            receiver_value = new_state.compute_value_of_expr(attribute.value)
            rhs_value = new_state.compute_value_of_expr(assign_stmt.value)
            for receiver_type in receiver_value:
                descriptor_result = analysis_setattr(
                    receiver_type, attribute.attr, rhs_value
                )
                if not descriptor_result.is_any():
                    assert len(descriptor_result) <= 1
                for descriptor in descriptor_result:
                    if isinstance(descriptor, AnalysisDescriptor):
                        args = descriptor.tp_args
                        for idx, arg in enumerate(args, 1):
                            new_state.stack.write_var(str(idx), Namespace_Local, arg)
                        setattr(
                            new_state.stack.frames[-1].f_locals, POS_ARG_LEN, len(args)
                        )
            return new_state
        elif isinstance(target, ast.Subscript):
            # object.__getitem__(self, key)
            key_value = new_state.compute_value_of_expr(target.slice)
            rhs_value = new_state.compute_value_of_expr(assign_stmt.value)
            args = [key_value, rhs_value]
            for idx, arg in enumerate(args, 1):
                new_state.stack.write_var(str(idx), Namespace_Local, arg)
            setattr(new_state.stack.frames[-1].f_locals, POS_ARG_LEN, len(args))
            return new_state
        else:
            raise NotImplementedError(program_point)

    # calculate
    def _transfer_call_right_magic(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        # add a new frame
        new_state.stack.add_new_frame()
        # get expr
        call_expr: ast.expr = self.get_stmt_by_point(program_point)
        if isinstance(call_expr, ast.BinOp):
            rhs = call_expr.right
            rhs_value = new_state.compute_value_of_expr(rhs)
            new_state.stack.write_var(str(1), Namespace_Local, rhs_value)
            # set the length of pos args
            setattr(new_state.stack.frames[-1].f_locals, POS_ARG_LEN, 1)
            return new_state
        elif isinstance(call_expr, ast.UnaryOp):
            setattr(new_state.stack.frames[-1].f_locals, POS_ARG_LEN, 0)
            return new_state
        elif isinstance(call_expr, ast.Attribute):
            receiver_value = new_state.compute_value_of_expr(call_expr.value)
            descriptor_result = getattrs(receiver_value, call_expr.attr)
            # if not descriptor_result.is_any():
            #     assert len(descriptor_result) <= 1
            for descriptor in descriptor_result:
                if isinstance(descriptor, AnalysisDescriptor):
                    args = descriptor.tp_args
                    for idx, arg in enumerate(args, 1):
                        new_state.stack.write_var(str(idx), Namespace_Local, arg)
                    setattr(new_state.stack.frames[-1].f_locals, POS_ARG_LEN, len(args))
            return new_state
        elif isinstance(call_expr, ast.Subscript):
            # object.__getitem__(self, key)
            # self_value = new_state.compute_value_of_expr(call_expr.value)
            key_value = new_state.compute_value_of_expr(call_expr.slice)
            args = [key_value]
            for idx, arg in enumerate(args, 1):
                new_state.stack.write_var(str(idx), Namespace_Local, arg)
            setattr(new_state.stack.frames[-1].f_locals, POS_ARG_LEN, len(args))
            return new_state
        elif isinstance(
            call_expr,
            (
                ast.BoolOp,
                ast.Lambda,
                ast.IfExp,
                ast.Call,
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
                ast.GeneratorExp,
                ast.Await,
                ast.Constant,
                ast.List,
                ast.Tuple,
                ast.Dict,
                ast.Set,
                ast.Starred,
                ast.Yield,
                ast.YieldFrom,
                ast.Compare,
                ast.Str,
                ast.FormattedValue,
                ast.JoinedStr,
                ast.Bytes,
                ast.NameConstant,
                ast.Ellipsis,
                ast.Num,
                ast.Name,
                ast.Index,
            ),
        ):
            raise NotImplementedError(call_expr)
        else:
            raise NotImplementedError(program_point)

    def _transfer_call_classdef(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        new_stack = new_state.stack
        new_stack.add_new_frame()
        return new_state

    def _transfer_call_normal(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        # Normal call has form: func_name(args, keywords)
        call_stmt: ast.Call = self.get_stmt_by_point(program_point)
        assert isinstance(call_stmt, ast.Call), call_stmt
        new_stack = new_state.stack

        # new namespace to simulate function call
        new_stack.add_new_frame()

        # deal with positional args
        # for instance, func(1, "hello") would be ["1": {int}, "2": {str}]
        args: List[ast.expr] = call_stmt.args
        # check *args
        for arg in args:
            if isinstance(arg, ast.Starred):
                # set the length of pos args
                setattr(new_stack.frames[-1].f_locals, POS_ARG_LEN, -1)
                return new_state

        # check **kwargs
        keywords: List[ast.keyword] = call_stmt.keywords
        for keyword in keywords:
            if keyword.arg is None:
                setattr(new_stack.frames[-1].f_locals, POS_ARG_LEN, -1)
                return new_state

        for idx, arg in enumerate(args, 1):
            arg_value = new_state.compute_value_of_expr(arg)
            new_stack.write_var(str(idx), Namespace_Local, arg_value)

        # set the length of pos args
        setattr(new_stack.frames[-1].f_locals, POS_ARG_LEN, len(args))

        for keyword in keywords:
            keyword_value = new_state.compute_value_of_expr(keyword.value)
            new_stack.write_var(keyword.arg, Namespace_Local, keyword_value)

        return new_state

    def transfer_entry(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        stmt = self.get_stmt_by_point(program_point)

        new_stack = new_state.stack

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
            generator_info,
        ) = self.entry_program_point_info[program_point]
        if instance_info:
            new_stack.write_var(str(0), Namespace_Local, instance_info)
        if init_info:
            new_stack.write_var(
                RETURN_FLAG, Namespace_Local, type_2_value(instance_info)
            )
        if module_info:
            new_state.switch_global_namespace(module_info)

        if generator_info:
            setattr(new_stack.frames[-1].f_locals, GENERATOR, generator_info[0])
            setattr(new_stack.frames[-1].f_locals, GENERATOR_ADDRESS, generator_info[1])

        if isinstance(stmt, ast.arguments):
            f_locals = new_stack.top_frame().f_locals
            positional_len: int = getattr(f_locals, POS_ARG_LEN)
            if positional_len == -1:
                if instance_info:
                    first_arg = stmt.args[0].arg
                    new_stack.write_var(first_arg, "local", instance_info)
                    start_pos = 1
                else:
                    start_pos = 0
                for arg in stmt.args[start_pos:] + stmt.kwonlyargs:
                    new_stack.write_var(arg.arg, "local", Value.make_any())
                if stmt.vararg:
                    new_stack.write_var(stmt.vararg.arg, "local", Value.make_any())
                if stmt.kwarg:
                    new_stack.write_var(stmt.kwarg.arg, "local", Value.make_any())
                return new_state

            # Positional and keyword arguments
            try:
                start_pos = 0 if instance_info else 1
                arg_flags = new_state.parse_positional_args(start_pos, stmt)
                arg_flags = new_state.parse_keyword_args(arg_flags, stmt)
                arg_flags = new_state.parse_default_args(arg_flags, stmt, defaults_info)
                _ = new_state.parse_kwonly_args(stmt, kwdefaults_info)
            except (ParsingDefaultsError, ParsingKwDefaultsError):
                return BOTTOM
        elif isinstance(stmt, ast.Pass):
            pass
        else:
            raise NotImplementedError(stmt)

        return new_state

    # transfer exit label
    def transfer_exit(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        new_stack = new_state.stack
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
            if isinstance(stmt.targets[0], ast.Attribute):
                return self.transfer_return_setter(
                    program_point, old_state, new_state, stmt
                )
            elif isinstance(stmt.targets[0], ast.Subscript):
                return self.transfer_return_setter(
                    program_point, old_state, new_state, stmt
                )
            else:
                raise NotImplementedError(stmt)
        elif isinstance(stmt, ast.Delete):
            return self.transfer_return_setter(
                program_point, old_state, new_state, stmt
            )

        else:
            raise NotImplementedError(stmt)

    def transfer_return_setter(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.Assign,
    ):
        new_stack = new_state.stack
        new_stack.pop_frame()
        return new_state

    def transfer_return_name(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.Name,
    ):
        new_stack = new_state.stack
        return_value: Value = new_stack.read_var(RETURN_FLAG)

        # check if it's a generator
        if hasattr(new_stack.frames[-1].f_locals, GENERATOR):
            generator_address = getattr(
                new_stack.frames[-1].f_locals, GENERATOR_ADDRESS
            )
            tp_address = f"{generator_address}-generator"
            generator_instance = Generator_Type(
                tp_address, Generator_Type, return_value
            )
            return_value = type_2_value(generator_instance)
        new_stack.pop_frame()

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

        # execute normal import
        module = import_a_module(name)
        if sys.prepend_flows:
            # meaning that a module needs importing
            curr_flows = self.generate_flow(program_point)
            sys.prepend_flows.extend(curr_flows)
            return BOTTOM

        # import x.y
        if asname is None:
            # get top-level name
            name = name.partition(".")[0]
            # but we only want top-level name
            module = import_a_module(name)
        # import x.y as z
        else:
            name = asname
        new_state.stack.write_var(name, Namespace_Local, module)
        logger.debug("Import module {}".format(module))
        return new_state

    @staticmethod
    def _resolve_name(name, package, level):
        """Resolve a relative module name to an absolute one."""
        bits = package.rsplit(".", level - 1)
        if len(bits) < level:
            raise ValueError("attempted relative import beyond top-level package")
        base = bits[0]
        return "{}.{}".format(base, name) if name else base

    # from xxx import yyy, zzz as aaa
    def transfer_ImportFrom(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        stmt: ast.ImportFrom,
    ):
        new_stack = new_state.stack
        qualified_module_name = stmt.module
        if stmt.level > 0:
            package: str = getattr(new_stack.frames[-1].f_globals, MODULE_PACKAGE_FLAG)
            name = stmt.module if stmt.module else ""
            qualified_module_name = self._resolve_name(name, package, stmt.level)
        modules: Value = import_a_module(qualified_module_name)

        if sys.prepend_flows:
            # meaning that a module needs importing
            curr_flows = self.generate_flow(program_point)
            sys.prepend_flows.extend(curr_flows)
            return BOTTOM

        for alias in stmt.names:
            name = alias.name
            asname = alias.asname
            for module in modules:
                try:
                    direct_res = module.tp_dict.read_value(name)
                except AttributeError:
                    sub_module_name = f"{qualified_module_name}.{name}"
                    direct_res = import_a_module(sub_module_name)
                    if sys.prepend_flows:
                        # meaning that a module needs importing
                        curr_flows = self.generate_flow(program_point)
                        sys.prepend_flows.extend(curr_flows)
                        return BOTTOM

                    if asname is None:
                        new_stack.write_var(name, Namespace_Local, direct_res)
                    else:
                        new_stack.write_var(asname, Namespace_Local, direct_res)
                else:
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
        # stmt
        stmt: ast.ClassDef = self.get_stmt_by_point(program_point)
        new_stack = new_state.stack

        # class frame
        f_locals = new_stack.top_frame().f_locals
        new_stack.pop_frame()

        # class name
        cls_name: str = stmt.name
        module: str = getattr(new_stack.frames[-1].f_globals, MODULE_NAME_FLAG)

        # short circuit
        if stmt.keywords:
            new_stack.write_var(cls_name, Namespace_Local, Value.make_any())
            return new_state

        # no custom attribute access
        if (
            f_locals.contains("__getattribute__")
            or f_locals.contains("__getattr__")
            or f_locals.contains("__setattr__")
            or f_locals.contains("__delattr__")
            or f_locals.contains("__init_subclass__")
        ):
            new_stack.write_var(cls_name, Namespace_Local, Value.make_any())
            return new_state

        # we only want AnalysisClass as bases
        bases = new_state.compute_bases(stmt)
        if bases is Any:
            new_stack.write_var(cls_name, Namespace_Local, Value.make_any())
            return new_state

        value: Value = Value()
        # call_lab is the allocation label of this class
        call_lab = self.get_classdef_call_label(return_lab)
        # tp_address is an OS context
        tp_address = record(call_lab, return_ctx)
        analysis_class: AnalysisClass = AnalysisClass(
            tp_uuid=call_lab,
            tp_module=module,
            tp_bases=bases,
            tp_dict=f_locals,
            tp_code=(call_lab, return_lab),
            tp_address=tp_address,
            tp_name=cls_name,
        )
        value.inject(analysis_class)
        new_stack.write_var(cls_name, Namespace_Local, value)
        return new_state

    def _get_module_heap_address(self, module_name: str) -> Tuple:
        modules: Value = sys.analysis_modules[module_name]
        assert len(modules) == 1, modules
        for module in modules:
            return module.tp_address
        raise NotImplementedError(module_name)

    # when a function definition is encountered...
    def transfer_FunctionDef(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        node: ast.FunctionDef,
    ):
        # get function label
        lab, _ = program_point
        # get function cfg
        func_cfg = self.checkout_cfg(lab)
        # add information about func_cfg to analysis
        entry_lab, exit_lab = self.add_sub_cfg(lab)
        # compute function defaults
        defaults, kwdefaults = new_state.compute_function_defaults(node)

        func_module: str = getattr(
            new_state.stack.frames[-1].f_globals, MODULE_NAME_FLAG
        )
        module_address: Tuple = self._get_module_heap_address(func_module)

        value = Value()
        value.inject_type(
            AnalysisFunction(
                tp_uuid=lab,
                tp_module=func_module,
                tp_code=(entry_lab, exit_lab),
                tp_defaults=defaults,
                tp_kwdefaults=kwdefaults,
                tp_address=module_address,
                # if is_generator is True, this is a generator function.
                tp_generator=func_cfg.is_generator,
                tp_name=node.name,
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
        new_stack: Stack = new_state.stack
        value: Value = new_state.compute_value_of_expr(stmt.value)
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
        new_stack = new_state.stack
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
        new_stack = new_state.stack
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
        new_stack = new_state.stack
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
        if program_point[0] in self.module_entry_labels:
            module_dict = self.module_entry_info[program_point]
            new_state.exec_a_module(module_dict)
        # the exit label of a module must be ast.Pass
        # if it is encountered, pop last frame
        elif program_point[0] in self.module_exit_labels:
            new_state.stack.pop_frame()
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
