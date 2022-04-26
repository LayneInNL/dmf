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
import ast
import logging
from collections import defaultdict, deque
from typing import Dict

from dmf.analysis.abstract_state import ContextStates, StackFrame
from dmf.analysis.abstract_value import Value
from dmf.py2flows.py2flows.cfg.flows import CFG


class PrettyDefaultDict(defaultdict):
    __repr__ = dict.__repr__


def extend_inter_flows(inter_flows):
    new_inter_flows = {}
    for a, b, c, d in inter_flows:
        temp = [a, b, c, d]
        new_inter_flows[a] = temp
        new_inter_flows[d] = temp

    return new_inter_flows


class Analysis:
    def __init__(self, cfg: CFG):
        self.flows = cfg.flows
        self.extremal_label = cfg.start_block.bid
        self.extremal_value = ContextStates(extremal=True)
        self.bot = None
        self.blocks = cfg.blocks

        self.work_list = deque()
        self.analysis_list = None

        self.inter_flows = extend_inter_flows(cfg.inter_flows)
        self.sub_cfgs: Dict[int, CFG] = cfg.sub_cfgs

    def compute_fixed_point(self):
        self.initialize()
        self.iterate()
        self.present()

    def initialize(self):
        self.work_list.extend(self.flows)
        self.analysis_list: Dict[int, ContextStates] = PrettyDefaultDict(lambda: None)
        self.analysis_list[self.extremal_label] = self.extremal_value

    def iterate(self):
        while self.work_list:
            fst_label, snd_label = self.work_list.popleft()
            transferred = self.transfer(fst_label)
            if transferred == self.bot:
                continue
            if not transferred.issubset(self.analysis_list[snd_label]):
                transferred.union(self.analysis_list[snd_label])
                self.analysis_list[snd_label] = transferred

                if snd_label in self.inter_flows:
                    if self.is_call_label(snd_label):
                        stmt = self.blocks[snd_label].stmt[0]
                        cfg = None
                        if isinstance(stmt, ast.ClassDef):
                            cfg = self.sub_cfgs[snd_label]
                            self.sub_cfgs.update(cfg.sub_cfgs)
                        elif isinstance(stmt, ast.Assign):
                            if isinstance(stmt.value, ast.Call) and isinstance(
                                stmt.value.func, ast.Name
                            ):
                                func_name = stmt.value.func.id
                                for _, state in self.analysis_list[snd_label].items():
                                    value = state.read_from_stack(func_name)
                                    locations = value.extract_functions()
                                    location = list(locations)
                                    logging.debug("locations {}".format(location))
                                assert len(location) == 1
                                cfg = self.sub_cfgs[location[0]]
                                self.sub_cfgs.update(cfg.sub_cfgs)
                            else:
                                assert False
                        entry_label = cfg.start_block.bid
                        exit_label = cfg.final_block.bid
                        return_label = self.inter_flows[snd_label][-1]
                        self.modify_inter_flows(snd_label, entry_label, exit_label)
                        self.flows.update(
                            {
                                (snd_label, entry_label),
                                (exit_label, return_label),
                            }
                        )
                        additional_flows = cfg.flows
                        logging.debug("Additional flows {}".format(additional_flows))
                        self.flows.update(additional_flows)
                        additional_blocks = cfg.blocks
                        self.blocks.update(additional_blocks)

                added_flows = [(l2, l3) for l2, l3 in self.flows if l2 == snd_label]
                self.work_list.extendleft(added_flows)

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

    def modify_inter_flows(self, call_label, entry_label, exit_label):
        self.inter_flows[call_label][1] = entry_label
        self.inter_flows[call_label][2] = exit_label
        self.inter_flows[entry_label] = self.inter_flows[exit_label] = self.inter_flows[
            call_label
        ]

    def merge(self, label, heap, context):
        return context[-1:] + (label,)

    def transfer(self, label):
        # Normal: label -> analysis including context->State
        # Bot: label->None
        if self.analysis_list[label] == self.bot:
            return self.bot

        return self.do_transfer(label)

    def is_call_label(self, label):
        if label in self.inter_flows and label == self.inter_flows[label][0]:
            return True
        return False

    def is_entry_label(self, label):
        pass

    def is_exit_label(self, label):
        if label in self.inter_flows and label == self.inter_flows[label][-2]:
            return True
        return False

    def is_return_label(self, label):
        if label in self.inter_flows and label == self.inter_flows[label][-1]:
            return True
        return False

    def do_transfer(self, label):
        stmt = self.blocks[label].stmt[0]

        if self.is_call_label(label):
            if isinstance(stmt, ast.ClassDef):
                return self.transfer_class_call(label)
            elif (
                isinstance(stmt, ast.Assign)
                and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Name)
            ):
                return self.transfer_func_call(label)
        elif self.is_exit_label(label):
            if isinstance(stmt, ast.Return):
                return self.transfer_func_exit(label)
            elif isinstance(stmt, ast.Pass):
                return self.transfer_class_exit(label)
        elif self.is_return_label(label):
            if isinstance(stmt, ast.ClassDef):
                return self.transfer_class_return(label)
            elif (
                isinstance(stmt, ast.Assign)
                and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Name)
            ):
                return self.transfer_func_return(label)

        elif isinstance(stmt, ast.Pass):
            return self.transfer_Pass(label)
        elif isinstance(stmt, ast.If):
            return self.transfer_If(label)
        elif isinstance(stmt, ast.While):
            return self.transfer_While(label)
        elif isinstance(stmt, ast.Assign):
            return self.transfer_Assign(label)
        elif isinstance(stmt, ast.FunctionDef):
            return self.transfer_FunctionDef(label)
        else:
            assert False

    def extract_params(self, args: ast.arguments):
        param_list = []
        for arg in args.args:
            param_list.append(arg.arg)
        return param_list

    def extract_func_params(self, func: ast.FunctionDef):
        args = func.args
        return self.extract_params(args)

    def param_value_list(self, params, args, state):
        param_value = []
        for loc, arg in enumerate(args):
            if isinstance(arg, (ast.Str, ast.Num, ast.NameConstant)):
                arg_value = self.get_value(arg, state)
            elif isinstance(arg, ast.Name):
                arg_value = state.read_from_stack(arg.id)
            else:
                assert False
            param_value.append((params[loc], arg_value))
        return param_value

    def transfer_class_call(self, label):
        old_context_states = self.analysis_list[label]
        new_context_states = old_context_states.copy()
        for context, state in new_context_states.items():
            state.stack_enter_new_scope("local")

        return new_context_states

    def transfer_func_call(self, label):
        stmt: ast.Assign = self.blocks[label].stmt[0]
        call: ast.Call = stmt.value
        name = call.func.id
        old_context_states = self.analysis_list[label]
        new_context_states = old_context_states.copy()
        for context, state in old_context_states.items():
            value = state.read_from_stack(name)
            func_labels = value.extract_functions_as_list()
            assert len(func_labels) == 1

            func_def_stmt: ast.FunctionDef = self.blocks[func_labels[0]].stmt[0]
            param_list = self.extract_func_params(func_def_stmt)
            arg_list = call.args
            param_value = self.param_value_list(param_list, arg_list, state)

            new_state = new_context_states[context]
            new_state.stack_enter_new_scope("local")
            for param, param_value in param_value:
                new_state.write_to_stack(param, param_value)
            new_context = self.merge(label, None, context)
            new_context_states[new_context] = new_state
            del new_context_states[context]

        return new_context_states

    def transfer_func_exit(self, label):
        old_context_states = self.analysis_list[label]
        new_context_states = old_context_states.copy()
        return new_context_states

    def transfer_class_exit(self, label):
        old_context_states = self.analysis_list[label]
        return old_context_states

    def transfer_func_return(self, label):
        call_label = self.inter_flows[label][0]
        call_context_states = self.analysis_list[call_label]
        exit_label = self.inter_flows[label][-2]
        exit_stmt = self.blocks[exit_label].stmt[0]
        exit_name = exit_stmt.value.id
        return_context_states = self.analysis_list[label]
        return_stmt = self.blocks[label].stmt[0]
        return_name = return_stmt.targets[0].id
        new_context_states = call_context_states.copy()
        for call_context, call_state in call_context_states.items():
            context_at_call = self.merge(call_label, None, call_context)
            for return_context, return_state in return_context_states.items():
                if context_at_call == return_context:
                    return_value = return_state.read_from_stack(exit_name)
                    new_context_states[call_context].write_to_stack(
                        return_name, return_value
                    )

        return new_context_states

    def transfer_class_return(self, label):
        stmt = self.blocks[label].stmt[0]
        return_context_states = self.analysis_list[label]
        call_label = self.inter_flows[label][0]
        call_context_states = self.analysis_list[call_label]
        new_call_context_states = call_context_states.copy()
        for context, state in return_context_states.items():
            class_name = stmt.name
            frame: StackFrame = state.stack.top()
            call_state = new_call_context_states[context]
            value = Value()
            value.inject_class(label, frame.symbol_table())
            call_state.write_to_stack(class_name, value)
        return new_call_context_states

    def transfer_Assign(self, label):
        stmt = self.blocks[label].stmt[0]
        old_context_states = self.analysis_list[label]
        new_context_states = old_context_states.copy()
        for context, state in new_context_states.items():
            value = self.get_value(stmt.value, state)
            if isinstance(stmt.targets[0], ast.Name):
                name = stmt.targets[0].id
                state.write_to_stack(name, value)
            else:
                assert False
        return new_context_states

    def transfer_FunctionDef(self, label):
        stmt = self.blocks[label].stmt[0]
        old_context_states = self.analysis_list[label]
        new_context_states = old_context_states.copy()
        func_name = stmt.name
        for context, state in new_context_states.items():
            value = Value()
            value.inject_function(label)
            state.write_to_stack(func_name, value)

        return new_context_states

    def transfer_Pass(self, label):
        old_context_states = self.analysis_list[label]
        return old_context_states

    def transfer_If(self, label):
        old_context_states = self.analysis_list[label]
        return old_context_states

    def transfer_While(self, label):
        old_context_states = self.analysis_list[label]
        return old_context_states

    def get_value(self, expr, state):
        if isinstance(expr, ast.Num):
            return Value(value_num=True)
        elif isinstance(expr, ast.NameConstant):
            if expr.value is None:
                return Value(value_none=True)
            else:
                return Value(value_bool=True)
        elif isinstance(expr, ast.Str):
            return Value(value_str=True)
        elif isinstance(expr, ast.Name):
            return state.read_from_stack(expr.id)
        else:
            assert False
