from argparse import ArgumentParser

from nmigen import *
from shared.board.fpga_dev_board import FpgaDevBoard
from shared.clockDiv import ClockDiv
from nmigen.back.pysim import Simulator, Delay


class BinaryToDecimalConverter(Elaboratable):
    def __init__(self):
        self.i_value = Signal(16)
        self.o_thousands = Signal(4)
        self.o_hundreds = Signal(4)
        self.o_tens = Signal(4)
        self.o_ones = Signal(4)

    def elaborate(self, platform):
        m = Module()

        value = Signal(16)
        register = Signal(32)
        thousands = Signal(4)
        hundreds = Signal(4)
        tens = Signal(4)
        ones = Signal(4)
        counter = Signal(max=20)

        with m.FSM():
            with m.State('IDLE'):
                with m.If(value != self.i_value):
                    m.d.sync += register.eq(self.i_value)
                    m.d.sync += value.eq(self.i_value)
                    m.d.sync += counter.eq(0)
                    m.next = 'SHIFT'

            with m.State('SHIFT'):
                m.d.sync += register.eq(Cat(0, register))
                with m.If(counter >= 15):
                    m.next = 'FINISH'
                with m.Else():
                    m.d.sync += counter.eq(counter + 1)
                    m.next = 'EXTRACT_NIBBLES'

            with m.State('EXTRACT_NIBBLES'):
                m.d.sync += thousands.eq(register[28:32])
                m.d.sync += hundreds.eq(register[24:28])
                m.d.sync += tens.eq(register[20:24])
                m.d.sync += ones.eq(register[16:20])
                m.next = 'ADD'

            with m.State('ADD'):
                with m.If(hundreds >= 5):
                    m.d.sync += hundreds.eq(hundreds + 3)
                with m.Else():
                    m.d.sync += hundreds.eq(hundreds)

                with m.If(tens >= 5):
                    m.d.sync += tens.eq(tens + 3)
                with m.Else():
                    m.d.sync += tens.eq(tens)

                with m.If(ones >= 5):
                    m.d.sync += ones.eq(ones + 3)
                with m.Else():
                    m.d.sync += ones.eq(ones)

                m.next = 'CONCAT'

            with m.State('CONCAT'):
                m.d.sync += register.eq(Cat(register[:16],
                                            ones, tens, hundreds, thousands))
                m.next = 'SHIFT'

            with m.State('FINISH'):
                m.d.sync += self.o_thousands.eq(register[28:32])
                m.d.sync += self.o_hundreds.eq(register[24:28])
                m.d.sync += self.o_tens.eq(register[20:24])
                m.d.sync += self.o_ones.eq(register[16:20])
                m.next = 'IDLE'

        return m


class BcdTo7Segment(Elaboratable):
    def __init__(self):
        self.i_bcd = Signal(4)
        self.o_7seg = Signal(8)

    def elaborate(self, platform):
        m = Module()

        with m.Switch(self.i_bcd):
            with m.Case(0b0000):
                m.d.comb += self.o_7seg.eq(0b10111111)
            with m.Case(0b0001):
                m.d.comb += self.o_7seg.eq(0b10000110)
            with m.Case(0b0010):
                m.d.comb += self.o_7seg.eq(0b11011011)
            with m.Case(0b0011):
                m.d.comb += self.o_7seg.eq(0b11001111)
            with m.Case(0b0100):
                m.d.comb += self.o_7seg.eq(0b11100110)
            with m.Case(0b0101):
                m.d.comb += self.o_7seg.eq(0b11101101)
            with m.Case(0b0110):
                m.d.comb += self.o_7seg.eq(0b11111101)
            with m.Case(0b0111):
                m.d.comb += self.o_7seg.eq(0b10000111)
            with m.Case(0b1000):
                m.d.comb += self.o_7seg.eq(0b11111111)
            with m.Case(0b1001):
                m.d.comb += self.o_7seg.eq(0b11101111)

        return m


class SevenSegmentsDisplay(Elaboratable):
    def __init__(self):
        self.i_value = Signal(16)
        self.o_digits = Signal(4)
        self.o_segments = Signal(8)

    def elaborate(self, platform):
        m = Module()

        digitCounter = Signal(4, reset=0b1000)
        clockDiv = ClockDiv(150000)  # 196Hz ~5ms
        bcdConverter = BinaryToDecimalConverter()
        thousandsConverter = BcdTo7Segment()
        hundredesConverter = BcdTo7Segment()
        tensConverter = BcdTo7Segment()
        onesConverter = BcdTo7Segment()

        m.submodules += clockDiv, bcdConverter, thousandsConverter, hundredesConverter, tensConverter, onesConverter

        m.d.comb += [
            thousandsConverter.i_bcd.eq(bcdConverter.o_thousands),
            hundredesConverter.i_bcd.eq(bcdConverter.o_hundreds),
            tensConverter.i_bcd.eq(bcdConverter.o_tens),
            onesConverter.i_bcd.eq(bcdConverter.o_ones),

            bcdConverter.i_value.eq(self.i_value),

            self.o_digits.eq(digitCounter)
        ]

        with m.If(clockDiv.o_clk):
            m.d.sync += digitCounter.eq(Cat(digitCounter[1:], digitCounter[0]))

        with m.Switch(digitCounter):
            with m.Case(0b1000):
                m.d.sync += self.o_segments.eq(thousandsConverter.o_7seg)
            with m.Case(0b0100):
                m.d.sync += self.o_segments.eq(hundredesConverter.o_7seg)
            with m.Case(0b0010):
                m.d.sync += self.o_segments.eq(tensConverter.o_7seg)
            with m.Default():
                m.d.sync += self.o_segments.eq(onesConverter.o_7seg)

        return m


class Main(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        digits = platform.request('display_7seg_ctrl')
        segments = platform.request('display_7seg')

        display = SevenSegmentsDisplay()
        m.submodules += display

        m.d.comb += [
            display.i_value.eq(1234),
            digits.eq(display.o_digits),
            segments.eq(display.o_segments)
        ]

        return m


def parse_args():
    parser = ArgumentParser()
    p_action = parser.add_subparsers(dest='action')
    p_action.add_parser('simulate')
    p_action.add_parser('build')
    p_program = p_action.add_parser('program')

    p_program.add_argument('-f', '--flash',
                           help='save the bitstream in flash',
                           action='store_true')

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    platform = FpgaDevBoard()

    if args.action == 'build':
        platform.build(Main(platform=platform))

    elif args.action == 'program':
        if args.flash:
            platform.build(Main(platform=platform), do_program=True,
                           program_opts={"flash": True})
        else:
            platform.build(Main(platform=platform), do_program=True,
                           program_opts={"flash": False})

    elif args.action == 'simulate':
        main = BinaryToDecimalConverter()
        m = Module()
        m.submodules.main = main

        sim = Simulator(m)
        sim.add_clock(1e-6)

        def process():
            yield Delay(6e-3)

        sim.add_sync_process(process)
        with sim.write_vcd("test.vcd", "test.gtkw"):
            sim.run()
