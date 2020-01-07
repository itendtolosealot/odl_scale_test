class A():
    def __init__(self, B):
        self._b = B

    def run(self):
        c=self._b.run()
        return c

class B():
    def __init__(self):
        self._a = A(self)

    def run(self):
        return 3

    def get_data(self):
        return self._a.run()


if __name__ == '__main__':
    b = B()
    print("B returns: " + str(b.get_data()))
