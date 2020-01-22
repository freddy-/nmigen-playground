from argparse import ArgumentParser

from nmigen import *
from shared.board.fpga_dev_board import FpgaDevBoard
from shared.clockDiv import ClockDivWE
from nmigen.back.pysim import Simulator, Delay


class UartTX(Elaboratable):
    def __init__(self):
        self.i_wr = Signal()
        self.i_data = Signal(8)
        self.o_busy = Signal()
        self.o_tx = Signal(reset=1)

    def elaborate(self, platform):
        m = Module()

        clkDiv = ClockDivWE(targetFreq=115200)
        m.submodules += clkDiv

        busy = Signal()
        register = Signal(8)
        shiftCounter = Signal(4)

        m.d.comb += self.o_busy.eq(busy)

        with m.FSM():
            with m.State('IDLE'):
                with m.If((self.i_wr) & (~busy)):
                    m.d.sync += [
                        register.eq(self.i_data),
                        busy.eq(1),
                        clkDiv.i_enable.eq(1),
                        self.o_tx.eq(0)
                    ]

                    m.next = 'SEND_DATA'

            with m.State('SEND_DATA'):
                with m.If(clkDiv.o_clk):
                    with m.If(shiftCounter < 8):
                        m.d.sync += [
                            register.eq(register >> 1),
                            self.o_tx.eq(register[0]),
                            shiftCounter.eq(shiftCounter + 1)
                        ]

                    with m.Else():
                        m.d.sync += self.o_tx.eq(1)
                        m.next = 'FINISH'

            with m.State('FINISH'):
                with m.If(clkDiv.o_clk):
                    m.d.sync += [
                        busy.eq(0),
                        shiftCounter.eq(0),
                        clkDiv.i_enable.eq(0)
                    ]
                    m.next = 'IDLE'

        return m


class UartLed(Elaboratable):
    def __init__(self):
        self.i_signal = Signal()
        self.o_led = Signal()

    def elaborate(self, platform):
        m = Module()

        m.submodules.clkDiv = clkDiv = ClockDivWE(targetFreq=100)

        with m.If(~self.i_signal):
            m.d.sync += [
                self.o_led.eq(1),
                clkDiv.i_enable.eq(1)
            ]

        with m.If(clkDiv.o_clk):
            m.d.sync += [
                self.o_led.eq(0),
                clkDiv.i_enable.eq(0)
            ]

        return m


class Main(Elaboratable):
    def __init__(self, platform=None):
        if (platform != None):
            self.o_tx = platform.request('uart').tx
            self.o_txLed = platform.request('led', 0)
        else:
            self.o_tx = Signal()
            self.o_txLed = Signal()

    def elaborate(self, platform):
        m = Module()

        m.submodules.uartTx = uartTx = UartTX()
        m.submodules.txLed = txLed = UartLed()
        m.submodules.clkDiv = clkDiv = ClockDivWE(targetFreq=1)

        m.d.comb += [
            self.o_tx.eq(uartTx.o_tx),
            txLed.i_signal.eq(uartTx.o_tx),
            self.o_txLed.eq(txLed.o_led)
        ]

        charCounter = Signal(max=20)
        helloString = Array([
            ord('H'),
            ord('e'),
            ord('l'),
            ord('l'),
            ord('o'),
            ord(' '),
            ord('W'),
            ord('o'),
            ord('r'),
            ord('l'),
            ord('d'),
            ord('!'),
            ord(' ')
        ])

        with m.If((~uartTx.o_busy) & (~uartTx.i_wr) & (charCounter <= 12)):
            m.d.sync += [
                uartTx.i_data.eq(helloString[charCounter]),
                uartTx.i_wr.eq(1),
                charCounter.eq(charCounter + 1)
            ]
        with m.Elif(uartTx.o_busy):
            m.d.sync += uartTx.i_wr.eq(0)
        with m.Elif(clkDiv.o_clk):
            m.d.sync += [
                clkDiv.i_enable.eq(0),
                charCounter.eq(0)
            ]
        with m.Else():
            m.d.sync += clkDiv.i_enable.eq(1)

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
            yield Delay(4e-3)

        sim.add_sync_process(process)
        with sim.write_vcd("test.vcd", "test.gtkw"):
            sim.run()
