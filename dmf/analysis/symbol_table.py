from __future__ import annotations


class SymbolTable(dict):
    pass


class Var:
    def __init__(self, name: str):
        self.name: str = name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other: Var):
        return self.name == other.name

    def is_temp(self):
        return self.name.startswith("_var")


class LocalVar(Var):
    def __repr__(self):
        return f"({self.name}, local)"


class NonlocalVar(Var):
    def __repr__(self):
        return f"({self.name}, nonlocal)"


class GlobalVar(Var):
    def __repr__(self):
        return f"({self.name}, global)"
