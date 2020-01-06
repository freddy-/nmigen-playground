from argparse import ArgumentParser

from nmigen import *
from board.fpga_dev_board import FpgaDevBoard
from nmigen.back.pysim import Simulator, Delay


class Main(Elaboratable):

    def __init__(self, platform=None):
        self.ledState = Signal()

        if platform:
            self.clk_freq = platform.default_clk_frequency
            self.greenLed = platform.request("led", 0)
        else:
            self.clk_freq = 10
            self.greenLed = Signal()

    def elaborate(self, platform):
        m = Module()

        m.d.comb += self.greenLed.eq(self.ledState)

        timer = Signal(max=int(self.clk_freq//2),
                       reset=int(self.clk_freq//2) - 1)

        with m.If(timer == 0):
            m.d.sync += timer.eq(timer.reset)
            m.d.sync += self.ledState.eq(~self.ledState)
        with m.Else():
            m.d.sync += timer.eq(timer - 1)

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
        main = Main()
        m = Module()
        m.submodules.main = main

        sim = Simulator(m)
        sim.add_clock(1e-6)

        def process():
            for c in range(100):
                yield

        sim.add_sync_process(process)
        with sim.write_vcd("test.vcd", "test.gtkw", traces=platform._ports):
            sim.run()
