class LineRailCreator:

    def __init__(self, rail_a, rail_b):
        self.rail_a = rail_a
        self.rail_b = rail_b
        self.process_a = False
        self.process_b = False
        self.process_un = False

    def generate_linediff_del(self):
        if self.process_a or self.process_un:
            self.rail_a += 1
        self.process_a = True
        return {'lineA': self.rail_a, 'lineB': ''}

    def generate_linediff_add(self):
        if self.process_b or self.process_un:
            self.rail_b += 1
        self.process_b = True
        return {'lineA': '', 'lineB': self.rail_b}

    def generate_linediff_untouch(self):
        if self.process_un:
            self.rail_a += 1
            self.rail_b += 1
        if self.process_a and not self.process_un:
            self.rail_a += 1
        if self.process_b and not self.process_un:
            self.rail_b += 1
        self.process_un = True
        return {'lineA': str(self.rail_a), 'lineB': str(self.rail_b)}

