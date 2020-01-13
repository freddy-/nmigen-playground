from argparse import ArgumentParser

from nmigen import *
from shared.board.fpga_dev_board import FpgaDevBoard
from nmigen.back.pysim import Simulator, Delay, Settle

class ClockDiv(Elaboratable):
    def __init__(self, platform=None):
        self.o_clk = Signal()

    def elaborate(self, platform):
        m = Module()
        counter = Signal(max=294980)

        with m.If(counter == 294980):
            m.d.sync += counter.eq(0)
            m.d.sync += self.o_clk.eq(1)
        with m.Else():
            m.d.sync += counter.eq(counter + 1)
            m.d.sync += self.o_clk.eq(0)

        return m


class Debouncer(Elaboratable):
    def __init__(self):
        self.i_raw = Signal()
        self.o_clean = Signal()

    def elaborate(self, patform):
        m = Module()
        debouncedOutput = Signal()
        counter = Signal(8)

        clkDivider = ClockDiv()
        m.submodules += clkDivider

        m.d.comb += self.o_clean.eq(debouncedOutput)

        with m.If(clkDivider.o_clk):
            m.d.sync += counter.eq(
                Cat(counter[1:], ~self.i_raw))

        with m.If(counter == 0xFF):
            m.d.sync += debouncedOutput.eq(1)
        with m.Elif(counter == 0x00):
            m.d.sync += debouncedOutput.eq(0)
        with m.Else():
            m.d.sync += debouncedOutput.eq(debouncedOutput)

        return m


class LedToggler(Elaboratable):
    def __init__(self):
        self.i_toggle = Signal()
        self.o_led = Signal()

    def elaborate(self, platform):
        m = Module()

        ledState = Signal()
        prevDebouncedOutput = Signal()
        debouncedOutput = Signal()

        debouncer = Debouncer()
        m.submodules += debouncer

        m.d.comb += self.o_led.eq(ledState)

        m.d.comb += debouncer.i_raw.eq(self.i_toggle)
        m.d.comb += debouncedOutput.eq(debouncer.o_clean)

        with m.If(prevDebouncedOutput != debouncedOutput):
            m.d.sync += prevDebouncedOutput.eq(debouncedOutput)
            with m.If(debouncedOutput == 1):
                m.d.sync += ledState.eq(~ledState)

        return m


class Main(Elaboratable):
    def __init__(self, platform=None):
        self.clk_freq = platform.default_clk_frequency
        self.i_button_1_raw = platform.request("button", 0)
        self.i_button_2_raw = platform.request("button", 1)
        self.o_green_led = platform.request("led", 0)
        self.o_orange_led = platform.request("led", 1)

    def elaborate(self, platform):
        m = Module()

        greenLedToggler = LedToggler()
        orangeLedToggler = LedToggler()

        m.submodules += greenLedToggler
        m.submodules += orangeLedToggler

        m.d.comb += greenLedToggler.i_toggle.eq(self.i_button_1_raw)
        m.d.comb += orangeLedToggler.i_toggle.eq(self.i_button_2_raw)
        m.d.comb += self.o_green_led.eq(greenLedToggler.o_led)
        m.d.comb += self.o_orange_led.eq(orangeLedToggler.o_led)

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

    print(platform._ports)

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
        main = Debouncer()
        m = Module()
        btn = Signal()
        m.d.comb += main.i_raw.eq(btn)
        m.submodules.main = main

        sim = Simulator(m)
        sim.add_clock(1e-6)

        def process():
            yield Delay(6e-3)
            yield btn.eq(1)
            yield Delay(1e-3)
            yield btn.eq(0)
            yield Delay(1e-3)

        sim.add_sync_process(process)
        with sim.write_vcd("test.vcd", "test.gtkw", traces=[btn, main.o_clean]):
            sim.run()
