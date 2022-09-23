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
import ast

# denote the length of positional args in a function call
POS_ARG_LEN = "pos_arg_len"
RETURN_FLAG = "_var_return_flag"
INIT_FLAG = "init_flag"
MODULE_PACKAGE_FLAG = "_var_module_package_flag"
# module name
MODULE_NAME_FLAG = "_var_module_name_flag"
GENERATOR = "tp_generator"
GENERATOR_ADDRESS = "tp_generator_address"
numeric_methods = {
    ast.Add: "__add__",
    ast.Sub: "__sub__",
    ast.Mult: "__mul__",
    ast.Div: "__truediv__",
    ast.FloorDiv: "__floordiv__",
    ast.Mod: "__mod__",
    ast.Pow: "__pow__",
    ast.LShift: "__lshift__",
    ast.RShift: "__rshift__",
    ast.BitAnd: "__and__",
    ast.BitXor: "__xor__",
    ast.BitOr: "__or__",
}
reversed_numeric_methods = {
    ast.Add: "__radd__",
    ast.Sub: "__rsub__",
    ast.Mult: "__rmul__",
    ast.Div: "__rtruediv__",
    ast.FloorDiv: "__rfloordiv__",
    ast.Mod: "__rmod__",
    ast.Pow: "__rpow__",
    ast.LShift: "__rlshift__",
    ast.RShift: "__rrshift__",
    ast.BitAnd: "__rand__",
    ast.BitXor: "__rxor__",
    ast.BitOr: "__ror__",
}

augmented_numeric_methods = {
    ast.Add: "__iadd__",
    ast.Sub: "__isub__",
    ast.Mult: "__imul__",
    ast.Div: "__itruediv__",
    ast.FloorDiv: "__ifloordiv__",
    ast.Mod: "__imod__",
    ast.Pow: "__ipow__",
    ast.LShift: "__ilshift__",
    ast.RShift: "__irshift__",
    ast.BitAnd: "__iand__",
    ast.BitXor: "__ixor__",
    ast.BitOr: "__ior__",
}

unary_methods = {ast.UAdd: "__pos__", ast.USub: "__neg__", ast.Invert: "__invert__"}
