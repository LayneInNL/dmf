from .lattice import BoolLattice
from .pointsto import PointsToAnalysis
from collections import defaultdict, deque
from typing import Dict
from copy import deepcopy


class MFP:
    def __init__(self, CFG):
        self.flows = CFG.flows
        self.extremal_labels = [CFG.start.bid]
        self.extremal_value: Dict[str, BoolLattice] = {}
        self.labels = CFG.labels
        self.bot = None
        self.points_to_analysis = PointsToAnalysis(CFG.blocks)

    def compute_fixed_point(self):
        self.initialize()
        self.iterate()
        self.present()

    def initialize(self):
        # WorkList W
        self.work_list = deque(self.flows)
        self.analysis_list: Dict[int, Dict[str, BoolLattice]] = {}
        for label in self.labels:
            # We use None to represent BOTTOM in analysis lattice
            self.analysis_list[label] = self.extremal_value if label in self.extremal_labels else self.bot

    def iterate(self):
        while self.work_list:
            fst_label, snd_label = self.work_list.popleft()
            # If first one is BOT, we simply skip it.
            if self.analysis_list[fst_label] == self.bot:
                continue
            transferred = self.points_to_analysis.transfer(fst_label)
            transferred_lattice = deepcopy(self.analysis_list[fst_label])
            transferred_lattice = self.transform(transferred_lattice, transferred)
            snd_label_lattice = self.analysis_list[snd_label]

            if snd_label_lattice == self.bot:
                self.analysis_list[snd_label] = transferred_lattice
                self.work_list.extendleft([(l1, l2) for l1, l2 in self.flows if l1 == snd_label])
            elif not compare(transferred_lattice, snd_label_lattice):
                self.merge(snd_label_lattice, transferred_lattice)
                self.work_list.extendleft([(l1, l2) for l1, l2 in self.flows if l1 == snd_label])

    def present(self):
        MFP_content = {}
        MFP_effect = {}
        for label in self.labels:
            MFP_content[label] = self.analysis_list[label]
            MFP_effect[label] = self.points_to_analysis.transfer(label)

    def transform(self, analysis, store):
        for name, objects in store:
            if name not in analysis:
                analysis[name] = BoolLattice()
            analysis[name].transform(objects)

        return analysis

    def merge(self, analysis: Dict[str, BoolLattice], transferred_lattice: Dict[str, BoolLattice]):
        for k, v in transferred_lattice.items():
            transferred_lattice[k].merge(analysis[k])


def compare(left: Dict[str, BoolLattice], right: Dict[str, BoolLattice]):
    for key in right:
        if key not in left:
            return True
        if left[key] > right[key]:
            return False

    return True
