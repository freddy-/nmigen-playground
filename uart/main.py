from argparse import ArgumentParser

from nmigen import *
from shared.board.fpga_dev_board import FpgaDevBoard
from shared.clockDiv import ClockDivWE
from nmigen.back.pysim import Simulator, Delay

# i_clk
# i_wr
# i_data
# o_busy
# o_tx


# quando i_wr && (!o_busy)
#   copia i_data pra um registrador local
#   seta o_busy pra true
#   seta o_tx pra false


class UartTX(Elaboratable):
    def __init__(self):
        self.i_wr = Signal()
        self.i_data = Signal(8)
        self.o_busy = Signal()
        self.o_tx = Signal(reset=1)

    def elaborate(self, platform):
        m = Module()

        # TODO calcular para o baud rate correto 115200
        clkDiv = ClockDivWE(divideBy=256)
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

        m.submodules.clkDiv = clkDiv = ClockDivWE(divideBy=294980)

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
    def __init__(self, platform):
        self.o_tx = platform.request('uart').tx
        self.o_txLed = platform.request('led', 0)

    def elaborate(self, platform):
        m = Module()

        m.submodules.uartTx = uartTx = UartTX()
        m.submodules.txLed = txLed = UartLed()
        m.submodules.clkDiv = clkDiv = ClockDivWE(divideBy=14749000) # ~500ms

        m.d.comb += [
            clkDiv.i_enable.eq(1),

            self.o_tx.eq(uartTx.o_tx),

            txLed.i_signal.eq(uartTx.o_tx),
            self.o_txLed.eq(txLed.o_led)
        ]

        with m.If((clkDiv.o_clk) & (~uartTx.o_busy)):
            m.d.sync += [
                uartTx.i_data.eq(ord('X')),
                uartTx.i_wr.eq(1)
            ]
        with m.Else():
            m.d.sync += uartTx.i_wr.eq(0)

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
        main = UartTX()
        m = Module()
        i_wr = Signal()
        i_data = Signal(8)
        m.submodules.main = main
        m.d.sync += main.i_wr.eq(i_wr)
        m.d.sync += main.i_data.eq(i_data)

        sim = Simulator(m)
        sim.add_clock(1e-6)

        def process():
            yield Delay(5e-6)
            yield i_wr.eq(1)
            yield i_data.eq(0b11100101)
            yield Delay(1e-6)
            yield i_wr.eq(0)
            yield Delay(4e-3)

            yield i_wr.eq(1)
            yield i_data.eq(0b01010101)
            yield Delay(1e-6)
            yield i_wr.eq(0)
            yield Delay(4e-3)

        sim.add_sync_process(process)
        with sim.write_vcd("test.vcd", "test.gtkw"):
            sim.run()
