from .lattice import BoolLattice
from .pointsto import PointsToAnalysis
from collections import defaultdict, deque
from typing import Dict


class MFP:
    def __init__(self, CFG):
        self.flows = CFG.flows
        self.extremal_labels = [CFG.start.bid]
        self.extremal_value: Dict[str, BoolLattice] = defaultdict(BoolLattice)
        self.labels = CFG.labels
        self.bot = None

        self.initialize()

        self.points_to_analysis = PointsToAnalysis(CFG.blocks)

    def initialize(self):
        # WorkList W
        self.work_list = deque(self.flows)
        self.analysis_list: Dict[int, Dict[str, BoolLattice]] = defaultdict()
        for label in self.labels:
            # We use None to represent BOTTOM in analysis lattice
            self.analysis_list[label] = self.extremal_value if label in self.extremal_labels else self.bot

    def iterate(self):
        while self.work_list:
            fst_label, snd_label = self.work_list.popleft()
            if self.analysis_list[fst_label] == self.bot:
                continue
            transferred = self.points_to_analysis.transfer(fst_label)
            self.transform(self.analysis_list[fst_label], transferred)
            snd_label_lattice = self.analysis_list[snd_label]

            if transferred < snd_label_lattice:
                self.merge(snd_label_lattice, transferred)
                self.work_list.extendleft([(snd_label, trd_label) for trd_label in self.flows[snd_label_lattice]])

    def present(self):
        MFP_content = {}
        MFP_effect = {}
        for label in self.labels:
            MFP_content[label] = self.analysis_list[label]
            MFP_effect[label] = self.points_to_analysis.transfer(label)

    def transform(self, analysis, store):
        for name, objects in store:
            analysis[name].transform(objects)

    def merge(self, analysis, transferred):
        pass
