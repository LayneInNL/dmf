from .state.space import DataStack, Store, CallStack, Context, Obj
from .state.types import BoolFalseObjectAddress, BoolTrueObjectAddress, NoneObjectAddress
from .varlattice import VarLattice

import logging
from typing import List, Tuple, Any, Dict, NewType, Optional, Set
from collections import defaultdict

import ast

Lattice = NewType('Lattice', Dict[str, VarLattice])


def transform(store: List[Tuple[str, Obj]]) -> Dict[str, VarLattice]:
    transferred_lattice = defaultdict(VarLattice)
    for name, objects in store:
        transferred_lattice[name].transform(objects)

    return transferred_lattice


def merge(original_lattice: Dict[str, VarLattice], added_lattice: Dict[str, VarLattice]) -> Dict[str, VarLattice]:
    in_original: Set[str] = set(original_lattice.keys())
    in_added: Set[str] = set(added_lattice.keys())
    mixed: Set[str] = in_original | in_added

    for key in mixed:
        if key in in_original:
            added_lattice[key].merge(original_lattice[key])

    return added_lattice


class PointsToAnalysis:
    def __init__(self, blocks):
        self.blocks = blocks
        # Control flow graph, it contains program points and ast nodes.
        self.data_stack: DataStack = DataStack()
        self.store: Store = Store()
        self.call_stack: CallStack = CallStack()
        self.context: Context = Context(())

        self.analysis_list: Optional[Dict[int, Lattice]] = None

    def link_analysis_list(self, analysis_list: Dict[int, Lattice]):
        self.analysis_list = analysis_list

    def transfer(self, label: int) -> Dict[str, VarLattice]:
        # We would like to refactor the code with the strategy in ast.NodeVisitor
        stmt = self.blocks[label].stmt[0]

        method = 'handle_' + stmt.__class__.__name__
        handler = getattr(self, method)
        transferred = handler(stmt)
        logging.debug('transferred {}'.format(transferred))

        new_lattice = transform(transferred)
        if not new_lattice:
            new_lattice = self.analysis_list[label]
        logging.debug('transferred lattice {}'.format(new_lattice))

        return new_lattice

    def handle_Assign(self, stmt: ast.Assign) -> List[Tuple[str, Obj]]:
        type_of_value = type(stmt.value)
        right_address = None
        if type_of_value == ast.NameConstant:
            right_address = self.handle_NameConstant(stmt.value)
        elif type_of_value == ast.Name:
            right_address = self.data_stack.st(stmt.value.id, self.context)
        assert right_address is not None
        right_obj = self.store.get(right_address)
        left_name = stmt.targets[0].id
        left_address = self.data_stack.st(left_name, self.context)
        self.store.insert_one(left_address, right_obj)
        return [(left_name, self.store.get(left_address))]

    def handle_NameConstant(self, expr):
        right_address = None
        if expr.value is None:
            right_address = self.data_stack.st(NoneObjectAddress.name, None)
        if type(expr.value) == bool:
            if expr.value:
                right_address = self.data_stack.st(BoolTrueObjectAddress.name, None)
            elif not expr.value:
                right_address = self.data_stack.st(BoolFalseObjectAddress.name, None)
        assert right_address is not None
        return right_address

    def handle_Pass(self, stmt: ast.Pass = None) -> List:
        return []
