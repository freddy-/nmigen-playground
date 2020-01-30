from argparse import ArgumentParser

from nmigen import *
from shared.board.fpga_dev_board import FpgaDevBoard
from shared.clockDiv import ClockDivWE
from nmigen.back.pysim import Simulator, Delay


class UartRx(Elaboratable):
    def __init__(self):
        self.i_rx = Signal(reset=1)
        self.o_data = Signal(8)
        self.o_stb = Signal()

    def elaborate(self, platform):
        m = Module()

        baudCounter = Signal(max=5)
        bitCounter = Signal(max=10)
        buffer = Signal(8)

        rxSynced = Signal(2, reset=0b11)
        m.d.sync += [
            rxSynced[1].eq(rxSynced[0]),
            rxSynced[0].eq(self.i_rx)
        ]

        clkDiv = ClockDivWE(targetFreq=115200 * 2)
        m.submodules += clkDiv

        with m.If(clkDiv.o_clk):
            m.d.sync += baudCounter.eq(baudCounter + 1)

        with m.FSM():
            with m.State('IDLE'):
                m.d.sync += self.o_stb.eq(0)
                with m.If(~rxSynced[1]):
                    m.d.sync += clkDiv.i_enable.eq(1)
                    m.next = 'WAIT_HALF_BAUD'

            with m.State('WAIT_HALF_BAUD'):
                with m.If(clkDiv.o_clk):
                    m.d.sync += baudCounter.eq(0)
                    m.next = 'READ'

            with m.State('READ'):
                with m.If(baudCounter == 2):
                    with m.If(bitCounter < 8):
                        m.d.sync += [
                            buffer.eq(Cat(buffer[1:], rxSynced[1])),
                            bitCounter.eq(bitCounter + 1),
                            baudCounter.eq(0)
                        ]

                    with m.Else():
                        m.next = 'FINISH'

            with m.State('FINISH'):
                with m.If(clkDiv.o_clk):
                    m.d.sync += [
                        self.o_stb.eq(1),
                        self.o_data.eq(buffer),
                        bitCounter.eq(0),
                        baudCounter.eq(0),
                        clkDiv.i_enable.eq(0)
                    ]
                    m.next = 'IDLE'

        return m


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


class HelloWorld(Elaboratable):
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


class Main(Elaboratable):
    def __init__(self, platform=None):

        if (platform != None):
            uart = platform.request('uart')
            self.o_tx = uart.tx
            self.i_rx = uart.rx
            self.o_txLed = platform.request('led', 0)
            self.o_rxLed = platform.request('led', 1)
        else:
            self.o_tx = Signal()
            self.i_rx = Signal()
            self.o_txLed = Signal()
            self.o_rxLed = Signal()

    def elaborate(self, platform):
        m = Module()

        m.submodules.uartTx = uartTx = UartTX()
        m.submodules.uartRx = uartRx = UartRx()

        m.submodules.txLed = txLed = UartLed()
        m.submodules.rxLed = rxLed = UartLed()

        m.submodules.oneSecTimer = oneSecTimer = ClockDivWE(targetFreq=1)

        m.d.comb += [
            self.o_tx.eq(uartTx.o_tx),
            uartRx.i_rx.eq(self.i_rx),

            self.o_txLed.eq(txLed.o_led),
            self.o_rxLed.eq(rxLed.o_led),

            txLed.i_signal.eq(uartTx.o_tx),
            rxLed.i_signal.eq(self.i_rx)
        ]

        # recebe o byte
        # aguarda um segundo
        # envia o byte recebido

        buffer = Signal(8)

        with m.FSM():
            with m.State('IDLE'):
                with m.If(uartRx.o_stb):
                    m.d.sync += [
                        oneSecTimer.i_enable.eq(1),
                        buffer.eq(uartRx.o_data)
                    ]
                    m.next = 'WAIT'

            with m.State('WAIT'):
                with m.If(oneSecTimer.o_clk):
                    m.d.sync += [
                        oneSecTimer.i_enable.eq(0),
                        uartTx.i_data.eq(buffer),
                        uartTx.i_wr.eq(1)
                    ]
                    m.next = 'START_SEND'

            with m.State('START_SEND'):
                m.d.sync += uartTx.i_wr.eq(0)
                m.next = 'SENDING'

            with m.State('SENDING'):                
                with m.If(~uartTx.o_busy):
                    m.next = 'IDLE'

        return m


def parse_args():
    parser = ArgumentParser()
    p_action = parser.add_subparsers(dest='action')
    p_action.add_parser('simulatetx')
    p_action.add_parser('simulaterx')
    p_action.add_parser('simulatem')
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

    elif args.action == 'simulatetx':
        m = Module()
        m.submodules.main = uartTx = UartTX()

        i_wr = Signal()
        m.d.comb += uartTx.i_wr.eq(i_wr)

        sim = Simulator(m)
        sim.add_clock(1e-6)

        def process():
            yield Delay(5e-6)
            yield uartTx.i_data.eq(0b00001111)
            yield i_wr.eq(1)
            yield Delay(2e-6)
            yield i_wr.eq(0)
            yield Delay(1e-3)

        sim.add_sync_process(process)
        with sim.write_vcd("test.vcd", "test.gtkw"):
            sim.run()

    elif args.action == 'simulaterx':
        m = Module()
        rx = Signal(reset=1)
        m.submodules.main = main = UartRx()
        m.d.comb += main.i_rx.eq(rx)
        sim = Simulator(m)
        sim.add_clock(1e-6)

        def process():
            yield Delay(1e-5)
            yield rx.eq(0)
            yield Delay(4e-5)
            yield rx.eq(1)
            yield Delay(4e-2)

        sim.add_sync_process(process)
        with sim.write_vcd("test.vcd", "test.gtkw"):
            sim.run()


    elif args.action == 'simulatem':
        m = Module()
        rx = Signal(reset=1)
        m.submodules.main = main = Main()
        m.d.comb += main.i_rx.eq(rx)
        sim = Simulator(m)
        sim.add_clock(1e-6)

        def process():
            yield Delay(1e-5)
            yield rx.eq(0)
            yield Delay(4e-5)
            yield rx.eq(1)
            yield Delay(4e-3)

        sim.add_sync_process(process)
        with sim.write_vcd("test.vcd", "test.gtkw"):
            sim.run()
