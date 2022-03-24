class NumObjectAddress:
    name = 'Num'
    context = -1
    address = (name, context)
    obj = (context, None)


class BoolObjectAddress:
    name = 'Bool'
    context = -2
    address = (name, context)
    obj = (context, None)


class StrObjectAddress:
    name = 'Str'
    context = -3
    address = (name, context)
    obj = (context, None)


class BytesObjectAddress:
    name = 'Bytes'
    context = -4
    address = (name, context)
    obj = (context, None)


class NoneObjectAddress:
    name = 'None'
    context = -5
    address = (name, context)
    obj = (context, None)


BUILTIN_CLASSES = (NumObjectAddress, BoolObjectAddress, StrObjectAddress, BytesObjectAddress, NoneObjectAddress)
