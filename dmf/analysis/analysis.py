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
from copy import deepcopy
from typing import Dict

from dmf.analysis.abstract_state import ContextStates, ClassTable, FuncTable, StackFrame
from dmf.analysis.abstract_value import Value
from dmf.analysis.state.space import AbstractValue


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
    def __init__(self, cfg):
        self.flows = cfg.flows
        self.extremal_label = cfg.start_block.bid
        self.extremal_value = ContextStates(extremal=True)
        self.bot = None
        self.blocks = cfg.blocks

        self.work_list = deque()
        self.analysis_list = None

        self.inter_flows = extend_inter_flows(cfg.inter_flows)
        self.func_cfgs = cfg.func_cfgs
        self.func_table = FuncTable()
        self.class_cfgs = cfg.class_cfgs
        self.class_table = ClassTable()

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
            logging.debug("Transferred States {}".format(transferred))
            if not transferred.issubset(self.analysis_list[snd_label]):
                transferred.union(self.analysis_list[snd_label])
                self.analysis_list[snd_label] = transferred

                if snd_label in self.inter_flows:
                    stmt = self.blocks[snd_label].stmt[0]
                    if self.is_call_label(snd_label):
                        if isinstance(stmt, ast.ClassDef):
                            class_name = stmt.name
                            class_cfg = self.class_cfgs[(class_name, snd_label)]
                            entry_label = class_cfg.start_block.bid
                            exit_label = class_cfg.final_block.bid
                            self.class_table.insert(class_name, entry_label, exit_label)
                            entry_label, exit_label = self.class_table.lookup(
                                class_name
                            )
                            self.modify_inter_flows(snd_label, entry_label, exit_label)
                            additional_flows = self.on_the_fly_flows(
                                snd_label, entry_label, exit_label
                            )
                            self.flows.update(additional_flows)
                            additional_blocks = self.on_the_fly_blocks(snd_label)
                            self.blocks.update(additional_blocks)
                        elif isinstance(stmt, ast.Assign):
                            if isinstance(stmt.value, ast.Call) and isinstance(
                                stmt.value.func, ast.Name
                            ):
                                func_name = stmt.value.func.id
                                _, (entry_label, exit_label) = self.func_table.lookup(
                                    func_name
                                )
                                self.modify_inter_flows(
                                    snd_label, entry_label, exit_label
                                )
                                additional_flows = self.on_the_fly_flows(
                                    snd_label, entry_label, exit_label
                                )
                                self.flows.update(additional_flows)
                                additional_blocks = self.on_the_fly_blocks(snd_label)
                                self.blocks.update(additional_blocks)

                added_flows = [(l2, l3) for l2, l3 in self.flows if l2 == snd_label]
                self.work_list.extendleft(added_flows)

    def present(self):
        all_labels = set()
        for flow in self.flows:
            all_labels.update(flow)

        for label in all_labels:
            print(label, self.analysis_list[label])
            print(label, self.transfer(label))

    def modify_inter_flows(self, call_label, entry_label, exit_label):
        self.inter_flows[call_label][1] = entry_label
        self.inter_flows[call_label][2] = exit_label
        self.inter_flows[entry_label] = self.inter_flows[exit_label] = self.inter_flows[
            call_label
        ]

    def on_the_fly_flows(self, call_label, entry_label, exit_label):
        call2entry = (call_label, entry_label)
        exit2return = (exit_label, self.inter_flows[call_label][-1])
        stmt = self.blocks[call_label].stmt[0]
        flows = {call2entry, exit2return}
        if isinstance(stmt, ast.ClassDef):
            name = stmt.name
            name_label = (name, call_label)
            flows.update(self.class_cfgs[name_label].flows)
        elif (
            isinstance(stmt, ast.Assign)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Name)
        ):
            name = stmt.value.func.id
            location, _ = self.func_table.lookup(name)
            name_label = (name, location)
            func_cfg = self.func_cfgs[name_label][1]
            flows.update(func_cfg.flows)
        return flows

    def on_the_fly_blocks(self, call_label):
        stmt = self.blocks[call_label].stmt[0]
        blocks = {}
        if isinstance(stmt, ast.ClassDef):
            name = stmt.name
            name_label = (name, call_label)
            blocks.update(self.class_cfgs[name_label].blocks)
        elif (
            isinstance(stmt, ast.Assign)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Name)
        ):
            name = stmt.value.func.id
            location, _ = self.func_table.lookup(name)
            name_label = (name, location)
            func_cfg = self.func_cfgs[name_label][1]
            blocks.update(func_cfg.blocks)

        return blocks

    def merge(self, label, heap, context):
        return context[-1:] + (label,)

    def transfer(self, label):
        # Normal: label -> analysis including context->State
        # Bot: label->None
        if self.analysis_list[label] == self.bot:
            return self.bot

        return self.do_transfer(label, self.analysis_list[label])

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

    def do_transfer(self, label, context_states: ContextStates):
        stmt = self.blocks[label].stmt[0]

        new_context_states = deepcopy(context_states)
        if self.is_call_label(label):
            if isinstance(stmt, ast.ClassDef):
                return self.transfer_class_call(label, new_context_states)
            elif (
                isinstance(stmt, ast.Assign)
                and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Name)
            ):
                return self.transfer_func_call(label, new_context_states)
        elif self.is_exit_label(label):
            if isinstance(stmt, ast.Return):
                return self.transfer_func_exit(label, new_context_states)
        elif self.is_return_label(label):
            if isinstance(stmt, ast.ClassDef):
                return self.transfer_class_return(label, new_context_states)
            elif (
                isinstance(stmt, ast.Assign)
                and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Name)
            ):
                return self.transfer_func_return(label, new_context_states)

        elif isinstance(stmt, ast.Pass):
            return self.transfer_Pass(label, new_context_states)
        elif isinstance(stmt, ast.If):
            return self.transfer_If(label, new_context_states)
        elif isinstance(stmt, ast.While):
            return self.transfer_While(label, new_context_states)
        elif isinstance(stmt, ast.Assign):
            return self.transfer_Assign(label, new_context_states)
        elif isinstance(stmt, ast.FunctionDef):
            return self.transfer_FunctionDef(label, new_context_states)
        else:
            assert False

    def transfer_class_call(self, label, new_context_states):
        for context, state in new_context_states.items():
            state.stack_enter_new_scope()
        return new_context_states

    def transfer_func_call(self, label, new_context_states):
        res_context_states = ContextStates()
        for context, state in new_context_states.items():
            state.stack_enter_new_scope()
            new_context = self.merge(label, None, context)
            res_context_states[new_context] = state
        return res_context_states

    def transfer_func_exit(self, label, new_context_states):
        return new_context_states

    def transfer_func_return(self, label, new_context_states):
        call_label = self.inter_flows[label][0]
        call_context_states = self.analysis_list[call_label]
        exit_label = self.inter_flows[label][-2]
        exit_stmt = self.blocks[exit_label].stmt[0]
        exit_name = exit_stmt.value.id

        return_stmt = self.blocks[label].stmt[0]
        return_name = return_stmt.targets[0].id
        res_context_states = deepcopy(call_context_states)
        for context, state in new_context_states.items():
            return_value = state.read_from_stack(exit_name)
            res_context_states[()].write_to_stack(return_name, return_value)

        return res_context_states

    def transfer_class_return(self, label, new_context_states):
        stmt = self.blocks[label].stmt[0]
        for context, state in new_context_states.items():
            name = stmt.name
            frame: StackFrame = state.stack.top()
            call_label = self.inter_flows[label][0]
            call_state = self.analysis_list[call_label][context]
            value = Value()
            value.inject_class(name, label, frame.get_internal_dict())
            call_state.write_to_stack(name, value)
            new_context_states[context] = call_state
        return new_context_states

    def transfer_Assign(self, label, new_context_states):
        stmt = self.blocks[label].stmt[0]
        for context, state in new_context_states.items():
            if isinstance(stmt, ast.Assign):
                value = self.get_value(stmt.value, state)
                if isinstance(stmt.targets[0], ast.Name):
                    name = stmt.targets[0].id
                    state.write_to_stack(name, value)
            else:
                assert False
        return new_context_states

    def transfer_FunctionDef(self, label, new_context_states):
        stmt = self.blocks[label].stmt[0]
        func_name = stmt.name

        func_cfg = self.func_cfgs[(func_name, label)]
        entry_label = func_cfg[1].start_block.bid
        exit_label = func_cfg[1].final_block.bid
        self.func_table.insert(func_name, label, entry_label, exit_label)
        for context, state in new_context_states.items():
            value = Value()
            value.inject_function(func_name, label)
            state.write_to_stack(func_name, value)

        return new_context_states

    def transfer_Pass(self, label, new_context_states):
        return new_context_states

    def transfer_If(self, label, new_context_states):
        return new_context_states

    def transfer_While(self, label, new_context_states):
        return new_context_states

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
