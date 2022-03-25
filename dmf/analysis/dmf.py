from .lattice import BoolLattice
from collections import defaultdict, deque


class MFP:
    def __init__(self, CFG):
        self.flows = CFG.flows
        self.extremal_labels = [CFG.start.bid]
        self.extremal_value = []
        self.labels = CFG.labels
        self.bot = None

        self.initialize()

    def initialize(self):
        # WorkList W
        self.work_list = deque(self.flows)
        self.analysis_list = {}
        for label in self.labels:
            # We use None to represent BOTTOM in analysis lattice
            self.analysis_list[label] = BoolLattice() if label in self.extremal_labels else self.bot

    def iterate(self):
        while self.work_list:
            fst_label, snd_label = self.work_list.popleft()
