class Base:
    def test(self):
        return 1


class Derive(Base):
    def test(self):
        return "hello"

    def print(self):
        return super(Derive, self).test()


t = Derive()
result = t.print()
