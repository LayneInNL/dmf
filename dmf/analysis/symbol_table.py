from __future__ import annotations


class SymbolTable(dict):
    def extract_local_nontemps(self):
        local_values = {}
        for var, value in self.items():
            if not var.is_temp() and var.is_local():
                local_values[var.name] = value

        return local_values

    def extract_locals(self):
        local_values = {}
        for var, value in self.items():
            if var.is_local():
                local_values[var.name] = value

        return local_values


class Var:
    def __init__(self, name: str):
        self.name: str = name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other: Var):
        return self.name == other.name

    def is_temp(self):
        return self.name.startswith("_var")

    def is_local(self):
        return isinstance(self, LocalVar)


class LocalVar(Var):
    def __repr__(self):
        return f"({self.name}, local)"


class NonlocalVar(Var):
    def __repr__(self):
        return f"({self.name}, nonlocal)"


class GlobalVar(Var):
    def __repr__(self):
        return f"({self.name}, global)"
