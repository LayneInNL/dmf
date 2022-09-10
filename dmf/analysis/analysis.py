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
import copy
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
    TypeExprVisitor,
)
from dmf.analysis.analysis_types import (
    Constructor,
    ArtificialClass,
)
from dmf.analysis.analysisbase import AnalysisBase, ProgramPoint
from dmf.analysis.artificial_basic_types import ArtificialMethod
from dmf.analysis.builtin_functions import import_a_module
from dmf.analysis.context_sensitivity import merge, record
from dmf.analysis.gets_sets import getattrs, _getattr, setattrs, _setattr
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
from dmf.analysis.typeshed_types import (
    TypeshedFunction,
    TypeshedClass,
    TypeshedInstance,
)
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
    def __init__(self, qualified_module_name: str):
        super().__init__()
        # work list
        self.work_list: Deque[Tuple[ProgramPoint, ProgramPoint]] = deque()
        # extremal value
        self.extremal_value: State = State(
            Stack(),
            Heap(),
            qualified_module_name,
        )
        curr_module: Value = sys.analysis_modules[qualified_module_name]
        curr_module = curr_module.extract_1_elt()
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

    def compute_fixed_point(self):
        self.initialize()
        self.iterate()
        self.present()

    def initialize(self):
        self.extremal_value = deepcopy_state(self.extremal_value, self.extremal_point)
        self.work_list.extendleft(self.generate_flow(self.extremal_point))
        self.analysis_list[self.extremal_point] = self.extremal_value

    def _push_state_to(self, state: State, program_point: ProgramPoint):
        old: State | BOTTOM = self.analysis_list[program_point]
        if not compare_states(state, old):
            self.analysis_list[program_point]: State = state
            self.detect_flow(program_point)
            added_program_points = self.generate_flow(program_point)
            self.work_list.extendleft(added_program_points)

    def iterate(self):
        # as long as there are flows in work_list
        while self.work_list:
            # get the leftmost one
            program_point1, program_point2 = self.work_list.popleft()
            stmt = self.get_stmt_by_point(program_point1)
            logger.info(
                f"Current program point1 {program_point1} {astor.to_source(stmt)}"
            )

            transferred: State | BOTTOM = self.transfer(program_point1)
            self._push_state_to(transferred, program_point2)

    def present(self):
        for program_point in list(self.analysis_list) + [self.final_point]:
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
        call_lab, call_ctx = program_point
        entry_lab, exit_lab = type.tp_function.tp_code

        # used by generator
        tp_address = record(call_lab, call_ctx)

        new_ctx: Tuple = merge(call_lab, None, call_ctx)
        self.entry_program_point_info[(entry_lab, new_ctx)] = AdditionalEntryInfo(
            None,
            None,
            type.tp_function.tp_module,
            type.tp_function.tp_defaults,
            type.tp_function.tp_kwdefaults,
            (type.tp_function.tp_generator, tp_address)
            if type.tp_function.tp_generator
            else type.tp_function.tp_generator,
        )

        inter_flow = (
            (call_lab, call_ctx),
            (entry_lab, new_ctx),
            (exit_lab, new_ctx),
            (ret_lab, call_ctx),
        )
        self.inter_flows.add(inter_flow)

    # detect flows of functions which have labels
    def _add_analysisfunction_interflow(
        self, program_point: ProgramPoint, type: AnalysisFunction, ret_lab: int
    ):
        call_lab, call_ctx = program_point
        entry_lab, exit_lab = type.tp_code

        # used by generator
        tp_address = record(call_lab, call_ctx)

        new_ctx: Tuple = merge(call_lab, None, call_ctx)
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
        instance: AnalysisInstance = type.tp_instance
        function: AnalysisFunction = type.tp_function
        if hasattr(instance, "tp_address"):
            # instance is an instance
            new_ctx: Tuple = merge(call_lab, instance.tp_address, call_ctx)
        else:
            # instance is a class, encountered in @classmethod
            new_ctx: Tuple = merge(call_lab, None, call_ctx)

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

        # del name
        if isinstance(target, ast.Name):
            new_state.stack.delete_var(target.id)
        # find out descriptors
        elif isinstance(target, ast.Attribute):
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
                direct_result, _ = _getattr(one_receiver_type, "__delitem__")
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

        :param program_point:
        :param old_state:
        :param new_state:
        :param dummy_value:
        :return:
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
                direct_result, _ = _getattr(one_receiver_type, "__setitem__")
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
            operator_name = numeric_methods[type(expr.op)]
            # retrieve reversed magic methods
            reversed_operator_name = reversed_numeric_methods[type(expr.op)]
            # retrieve augmented magic methods
            augmented_operator_name = augmented_numeric_methods[type(expr.op)]

            # left expr
            lhs = expr.left
            # left expr value
            lhs_value = new_state.compute_value_of_expr(lhs)
            rhs = expr.right
            rhs_value = new_state.compute_value_of_expr(rhs)

            # for instance
            # x + y
            # return node
            # dummy return node
            for one_receiver in lhs_value:
                one_receiver_type = one_receiver.tp_class
                direct_res, _ = _getattr(one_receiver_type, operator_name)
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
                    direct_res, _ = _getattr(one_receiver, unary_method_name)
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
        elif isinstance(expr, ast.Attribute):
            # compute receiver value
            lhs_value = new_state.compute_value_of_expr(expr.value)
            direct_result, descriptor_result = getattrs(lhs_value, expr.attr)
            dummy_value.inject(direct_result)

            # add flows of possible descriptors
            for descriptor in descriptor_result:
                if isinstance(descriptor, AnalysisDescriptor):
                    self._add_analysisfunction_interflow(
                        program_point, descriptor.tp_function, ret_lab
                    )
                else:
                    raise NotImplementedError(descriptor)
        elif isinstance(expr, ast.Subscript):
            # deal with something = x.y
            # at first compute x
            receiver_value = new_state.compute_value_of_expr(expr.value)
            field_value = new_state.compute_value_of_expr(expr.slice)
            for each_receiver in receiver_value:
                each_subscript_type = each_receiver.tp_class
                # then find __getitem__ based on its type
                res, descr_res = _getattr(each_subscript_type, "__getitem__")
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
        new_stack, new_heap = new_state.stack, new_state.heap
        args, keywords = compute_func_args(
            new_state, call_stmt.args, call_stmt.keywords
        )
        # new_stack, new_heap = new_state
        inits: Value = new_state.compute_value_of_expr(call_stmt.func)

        # special init
        # one case is user defined function
        # one case is artificial function
        for init in inits:
            if isinstance(init, AnalysisMethod):
                self._add_analysismethod_interflow(program_point, init, ret_lab)
            elif isinstance(init, ArtificialMethod):
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
        computed_args, computed_kwargs = compute_func_args(
            new_state, call_stmt.args, call_stmt.keywords
        )

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
                one_direct_result, _ = _getattr(type.tp_class, "__call__")
                for one in one_direct_result:
                    if isinstance(one, AnalysisFunction):
                        one_method = AnalysisMethod(tp_function=one, tp_instance=type)
                        self._add_analysismethod_interflow(
                            program_point, one_method, ret_lab
                        )
            # artificial related types
            elif isinstance(type, ArtificialClass):
                one_direct_res = type(address, type, *computed_args, **computed_kwargs)
                dummy_value.inject(one_direct_res)
            elif isinstance(type, (ArtificialFunction, ArtificialMethod)):
                res = type(*computed_args, **computed_kwargs)
                dummy_value.inject(res)
            elif isinstance(type, Constructor):
                # correspond to object.__new__(cls)
                # it has the form of temp_func(cls)
                stmt = self.get_stmt_by_point(program_point)
                new_stack, new_heap = new_state.stack, new_state.heap
                types = new_state.compute_value_of_expr(stmt.args[0])
                assert len(types) == 1
                for cls in types:
                    tp_dict = sys.heap.write_instance_to_heap(address)
                    instance = type(address, cls, tp_dict)
                    new_heap.write_instance_to_heap(instance)
                    dummy_value.inject_type(instance)

            # type is a typeshed class, for example, slice
            elif isinstance(type, TypeshedClass):
                typeshed_instance = TypeshedInstance(
                    type.tp_name, type.tp_module, type.tp_qualname, type
                )
                dummy_value.inject(typeshed_instance)
            elif isinstance(type, TypeshedFunction):
                functions = type.functions
                one_value = Value()
                visitor = TypeExprVisitor(type)
                for function in functions:
                    function_return_return = visitor.visit(function.returns)
                    one_value.inject(function_return_return)
                dummy_value.inject(one_value)
            else:
                raise NotImplementedError(type)

        dummy_ret_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
        new_state.stack.write_var(dummy_ret_stmt.id, Namespace_Local, dummy_value)

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
        new_method, _ = _getattr(type, "__new__")

        for new in new_method:
            if isinstance(new, Constructor):
                one_direct_res = new(
                    tp_address=tp_address, tp_class=type, tp_heap=new_heap
                )
                dummy_value.inject(one_direct_res)
            elif isinstance(new, AnalysisFunction):
                analysis_method = AnalysisMethod(tp_function=new, tp_instance=type)
                ret_lab, _ = self.get_special_new_return_label(call_lab)
                self._add_analysismethod_interflow(
                    program_point, analysis_method, ret_lab
                )

    def transfer(self, program_point: ProgramPoint) -> State | BOTTOM:
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
        new_stack, new_heap = new_state.stack, new_state.heap
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
                descriptor_result = _setattr(receiver_type, target.attr, None)
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
            args = [receiver_value, key_value]
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
        if isinstance(assign_stmt.targets[0], ast.Attribute):
            attribute: ast.Attribute = assign_stmt.targets[0]
            receiver_value = new_state.compute_value_of_expr(attribute.value)
            rhs_value = new_state.compute_value_of_expr(assign_stmt.value)
            for receiver_type in receiver_value:
                descriptor_result = _setattr(receiver_type, attribute.attr, rhs_value)
                for descriptor in descriptor_result:
                    if isinstance(descriptor, AnalysisDescriptor):
                        args = descriptor.tp_args
                        for idx, arg in enumerate(args, 1):
                            new_state.stack.write_var(str(idx), Namespace_Local, arg)
                        setattr(
                            new_state.stack.frames[-1].f_locals, POS_ARG_LEN, len(args)
                        )
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
        elif isinstance(call_expr, ast.Attribute):
            receiver_value = new_state.compute_value_of_expr(call_expr.value)
            _, descriptor_result = getattrs(receiver_value, call_expr.attr)
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
        else:
            raise NotImplementedError(program_point)

    def _transfer_call_classdef(
        self, program_point: ProgramPoint, old_state: State, new_state: State
    ):
        new_stack, new_heap = new_state.stack, new_state.heap
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
                assert isinstance(arg.value, ast.Name), arg
                new_stack.write_var(arg.value.id, Namespace_Local, Value.make_any())
            arg_value = new_state.compute_value_of_expr(arg)
            new_stack.write_var(str(idx), Namespace_Local, arg_value)

        # set the length of pos args
        setattr(new_stack.frames[-1].f_locals, POS_ARG_LEN, len(args))

        # deal with keyword args
        keywords: List[ast.keyword] = call_stmt.keywords
        for keyword in keywords:
            # (NULL identifier for **kwargs)
            if keyword.arg is None:
                assert isinstance(keyword.value, ast.Name), keyword
                new_stack.write_var(keyword.value.id, Namespace_Local, Value.make_any())
            keyword_value = new_state.compute_value_of_expr(keyword.value)
            new_stack.write_var(keyword.arg, Namespace_Local, keyword_value)

        return new_state

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
            generator_info,
        ) = self.entry_program_point_info[program_point]
        if instance_info:
            new_stack.write_var(str(0), Namespace_Local, instance_info)
        if init_info:
            # setattr(new_stack.frames[-1].f_locals, INIT_FLAG, None)
            new_stack.write_var(
                RETURN_FLAG, Namespace_Local, type_2_value(instance_info)
            )
        if module_info:
            new_state.switch_global_namespace(module_info)

        if generator_info:
            setattr(new_stack.frames[-1].f_locals, GENERATOR, generator_info[0])
            setattr(new_stack.frames[-1].f_locals, GENERATOR_ADDRESS, generator_info[1])

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
        new_stack, new_heap = new_state.stack, new_state.heap
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
            package: str = getattr(
                new_state.stack.frames[-1].f_globals, MODULE_PACKAGE_FLAG
            )

        new_stack = new_state.stack
        logger.debug("ImportFrom module {}".format(stmt.module))
        modules: Value = import_a_module(stmt.module, package, stmt.level)

        for alias in stmt.names:
            name = alias.name
            asname = alias.asname
            for module in modules:
                direct_res, _ = _getattr(module, name)
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
        # stmt
        stmt: ast.ClassDef = self.get_stmt_by_point(program_point)
        new_stack = new_state.stack

        # class frame
        f_locals = new_stack.top_frame().f_locals
        new_stack.pop_frame()

        # class name
        cls_name: str = stmt.name
        module: str = getattr(new_stack.frames[-1].f_globals, MODULE_NAME_FLAG)

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
        value.inject(analysis_class)
        new_stack.write_var(cls_name, Namespace_Local, value)
        return new_state

    # when a function definition is encountered...
    def transfer_FunctionDef(
        self,
        program_point: ProgramPoint,
        old_state: State,
        new_state: State,
        node: ast.FunctionDef,
    ):
        lab, _ = program_point
        func_cfg = self.checkout_cfg(lab)

        entry_lab, exit_lab = self.add_sub_cfg(lab)

        defaults, kwdefaults = compute_function_defaults(new_state, node)

        func_module: str = getattr(
            new_state.stack.frames[-1].f_globals, MODULE_NAME_FLAG
        )

        value = Value()
        value.inject_type(
            AnalysisFunction(
                tp_uuid=lab,
                tp_module=func_module,
                tp_code=(entry_lab, exit_lab),
                tp_defaults=defaults,
                tp_kwdefaults=kwdefaults,
                # if is_generator is True, this is a generator function.
                tp_generator=func_cfg.is_generator,
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
