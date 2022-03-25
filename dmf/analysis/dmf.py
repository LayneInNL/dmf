from collections import defaultdict, deque


class MFP:
    def __init__(self, CFG):
        self.flows = CFG.flows
        self.extremal_labels = [CFG.start.bid]
        self.extremal_value = []
        self.labels = CFG.labels

        self.initialize()

    def initialize(self):
        # WorkList W
        self.work_list = deque(self.flows)
        self.analysis_list = {}
        for label in self.labels:
            # We use None to represent BOTTOM in analysis lattice
            self.analysis_list[label] = [] if label in self.extremal_labels else None

    def iterate(self):
        while self.work_list:
            fst_label, snd_label = self.work_list.popleft()

    def is_subset(self, analysis1, analysis2):
        if all(analysis is None for analysis in [analysis1, analysis2]):
            return True

        if analysis2 is None:
            return False

        if analysis1 is None:
            return True


