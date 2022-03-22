from .state.space import AbstractState
from .state.types import Num, String

import ast
from collections import defaultdict


def normalize_flows(edges):
    new_dict = defaultdict(set)

    for fst, snd in edges:
        new_dict[fst].add(snd)

    return new_dict


class PointsToAnalysis:
    def __init__(self, CFG):
        # singleton object to denote ast.Num
        self.Num = Num()
        # singleton object to denote ast.Str
        self.String = String()
        # Control flow graph, it contains program points and ast nodes.
        self.CFG = CFG
        self.flows = normalize_flows(CFG.edges)

    def next_stmt_id(self, curr_stmt_id):
        return self.flows[curr_stmt_id]

    def transition(self, current_abstract_state: AbstractState) -> AbstractState:
        stmt_id, stack, store, call_stack, context = current_abstract_state
        stmt = self.CFG[stmt_id]
        if type(stmt) == ast.Assign:
            next_stmt_id = self.next_stmt_id(stmt_id)
            if type(stmt.value) == ast.Num:

