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
from collections import defaultdict, deque

from dmf.analysis.abstract_state import State


class PrettyDefaultDict(defaultdict):
    __repr__ = dict.__repr__


class Analysis:
    def __init__(self, cfg):
        self.flows = cfg.flows
        self.extremal_label = cfg.start_block.bid
        self.extremal_context = ()
        self.extremal_value = State()
        self.bot = None
        self.blocks = cfg.blocks

        self.work_list = deque()
        self.analysis_flows = set()
        self.analysis_list = None

    def compute_fixed_point(self):
        self.initialize()
        self.iterate()
        self.present()

    def initialize(self):
        for fst_label, snd_label in self.flows:
            if fst_label == self.extremal_label:
                label_context = (
                    (fst_label, self.extremal_context),
                    (snd_label, self.bot),
                )
            else:
                label_context = ((fst_label, self.bot), (snd_label, self.bot))
            self.analysis_flows.add(label_context)

        self.work_list.extend(self.analysis_flows)
        self.analysis_list = PrettyDefaultDict(lambda: None)
        self.analysis_list[self.extremal_label] = self.extremal_value

    def iterate(self):
        while self.work_list:
            fst_label_context, snd_label_context = self.work_list.popleft()
            transferred = self.transfer(fst_label_context)
            if not transferred.issubset(self.analysis_list[snd_label_context]):
                self.analysis_list[snd_label_context] = self.analysis_list[snd_label_context].union(transferred)
                for label_context1, label_context2 in self.

    def present(self):
        pass

    def transfer(self, label_context):
        label, context = label_context
