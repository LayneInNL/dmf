import logging

from .varlattice import VarLattice
from .pointsto import PointsToAnalysis
from ..py2flows.py2flows.cfg.flows import CFG
from collections import defaultdict, deque
from typing import Dict, Set, Tuple, List, Optional, Deque, DefaultDict, Any


def condense_flows(flows: Set[Tuple[int, int]]):
    condensed_flows: DefaultDict[int, Set[int]] = defaultdict(set)
    for fst, snd in flows:
        condensed_flows[fst].add(snd)

    return condensed_flows


def merge(analysis: Dict[str, VarLattice], transferred_lattice: Dict[str, VarLattice]):
    for k, _ in transferred_lattice.items():
        transferred_lattice[k].merge(analysis[k])


def is_subset(left: Optional[Dict[str, VarLattice]], right: Optional[Dict[str, VarLattice]]):
    for key, value in left.items():
        if key not in right:
            return False

        if not value.is_subset(right[key]):
            return False

    return True


class MFP:
    def __init__(self, cfg: CFG):
        self.flows: Set[Tuple[int, int]] = cfg.flows
        self.flows_mapping: DefaultDict[int, Set[int]] = condense_flows(self.flows)

        self.labels: Set[int] = cfg.labels
        self.extremal_labels: List[int] = [cfg.start.bid]
        # Note: passed by address
        self.extremal_value: Dict[str, VarLattice] = defaultdict(VarLattice)

        # Use None as Bottom
        self.bot: None = None

        self.points_to_analysis: PointsToAnalysis = PointsToAnalysis(cfg.blocks)

        # used for iteration
        self.work_list: Optional[Deque[Tuple[int, int]]] = None
        self.analysis_list: Optional[Dict[int, Dict[str, VarLattice]]] = None

        # used for final result
        self.mfp_content: Optional[Dict[int, Dict[str, VarLattice]]] = None
        self.mfp_effect: Optional[Dict[int, Dict[str, VarLattice]]] = None

    def compute_fixed_point(self) -> None:
        self.initialize()
        self.iterate()
        self.present()

    def initialize(self) -> None:
        # WorkList W
        self.work_list = deque(self.flows)
        logging.debug('work_list: {}'.format(self.work_list))
        self.analysis_list = {}
        logging.debug('analysis_list: {}'.format(self.analysis_list))
        for label in self.labels:
            # We use None to represent BOTTOM in analysis lattice
            self.analysis_list[label] = self.extremal_value if label in self.extremal_labels else self.bot

        self.points_to_analysis.link_analysis_list(self.analysis_list)

    def transfer(self, label: int) -> Dict[str, VarLattice]:
        transferred_lattice = self.points_to_analysis.transfer(label)
        return transferred_lattice

    def iterate(self) -> None:
        while self.work_list:
            fst_label, snd_label = self.work_list.popleft()
            logging.debug('Current flow({}, {})'.format(fst_label, snd_label))

            # If first one is BOT, we simply skip it. Since we flow information from known labels to unknown labels.
            if self.analysis_list[fst_label] == self.bot:
                logging.debug('{} is bot'.format(fst_label))
                continue

            # since the result of points-to analysis is incremental, we just use the transferred result
            transferred_lattice = self.transfer(fst_label)
            snd_label_lattice = self.analysis_list[snd_label]

            if snd_label_lattice == self.bot:
                self.analysis_list[snd_label] = transferred_lattice
                self.work_list.extendleft([(snd_label, l3) for l3 in self.flows_mapping[snd_label]])
            elif not is_subset(transferred_lattice, snd_label_lattice):
                merge(snd_label_lattice, transferred_lattice)
                self.work_list.extendleft([(snd_label, l3) for l3 in self.flows_mapping[snd_label]])

    def present(self) -> None:
        self.mfp_content = {}
        self.mfp_effect = {}
        for label in self.labels:
            self.mfp_content[label] = self.analysis_list[label]
            self.mfp_effect[label] = self.transfer(label)

    def pprint(self):
        for label in self.labels:
            logging.debug('content label: {}, value: {}'.format(label, self.mfp_content[label]))
            logging.debug('effect label: {}, value: {}'.format(label, self.mfp_effect[label]))
