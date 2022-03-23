class Num:
    name = 'Num'
    context = 0
    address = (name, context)

    @classmethod
    def get_num_name(cls):
        return cls.name

    @classmethod
    def get_num_context(cls):
        return cls.context

    @classmethod
    def get_num_object(cls):
        return cls.address


class String:
    pass
