from nmigen import *


class ClockDiv(Elaboratable):
    def __init__(self, divideBy=1):
        self.o_clk = Signal()
        self.divideBy = divideBy

    def elaborate(self, platform):
        m = Module()
        counter = Signal(max=self.divideBy + 1)

        with m.If(counter == self.divideBy):
            m.d.sync += counter.eq(0)
            m.d.sync += self.o_clk.eq(1)
        with m.Else():
            m.d.sync += counter.eq(counter + 1)
            m.d.sync += self.o_clk.eq(0)

        return m


class ClockDivWE(Elaboratable):
    def __init__(self, divideBy=10, targetFreq=None):
        self.o_clk = Signal()
        self.i_enable = Signal()
        self.divideBy = divideBy
        self.targetFreq = targetFreq

    def elaborate(self, platform):
        if (platform):
            if (self.targetFreq != None):
                self.divideBy = int(platform.default_clk_frequency // self.targetFreq)
                
        m = Module()
        counter = Signal(max=self.divideBy + 1)

        with m.If(self.i_enable):
            with m.If(counter == self.divideBy):
                m.d.sync += counter.eq(0)
                m.d.sync += self.o_clk.eq(1)
            with m.Else():
                m.d.sync += counter.eq(counter + 1)
                m.d.sync += self.o_clk.eq(0)

        with m.Else():
            m.d.sync += counter.eq(0)
            m.d.sync += self.o_clk.eq(0)

        return m
