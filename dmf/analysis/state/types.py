class PrimitiveTypes:
    NUM_NEGATIVE = -10
    NUM_ZERO = -9
    NUM_POSITIVE = -8

    BOOL_FALSE = -7
    BOOL_TRUE = -6

    STR_EMPTY = -5
    STR_NON_EMPTY = -4

    BYTES = -3

    NONE = -2


class BoolFalseObjectAddress:
    name = 'False'
    context = PrimitiveTypes.BOOL_FALSE
    address = (name, context)
    obj = (context, None)


class BoolTrueObjectAddress:
    name = 'True'
    context = PrimitiveTypes.BOOL_TRUE
    address = (name, context)
    obj = (context, None)


class NoneObjectAddress:
    name = 'None'
    context = PrimitiveTypes.NONE
    address = (name, context)
    obj = (context, None)


# class StrObjectAddress:
#     name = 'Str'
#     context = -3
#     address = (name, context)
#     obj = (context, None)


# class BytesObjectAddress:
#     name = 'Bytes'
#     context = -4
#     address = (name, context)
#     obj = (context, None)
#
#


BUILTIN_CLASSES = (BoolFalseObjectAddress, BoolTrueObjectAddress, NoneObjectAddress)
