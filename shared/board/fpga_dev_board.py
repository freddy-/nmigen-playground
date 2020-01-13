import os
import subprocess

from nmigen.build import *
from nmigen.vendor.xilinx_spartan_3_6 import *
from nmigen_boards.resources import *


__all__ = ["FpgaDevBoard"]


class FpgaDevBoard(XilinxSpartan6Platform):
    device = "xc6slx9"
    package = "tqg144"
    speed = "2"
    default_clk = "clk"  # 29.498MHZ
    resources = [
        Resource("clk", 0, Pins("P55", dir="i"),
                 Clock(29498000), Attrs(IOSTANDARD="LVCMOS33")),

        *LEDResources(pins="P82 P81",
                      attrs=Attrs(IOSTANDARD="LVCMOS33")),

        *ButtonResources(pins="P97 P99 P101 P104",
                         attrs=Attrs(IOSTANDARD="LVCMOS33")),

        Display7SegResource(0,
                            a="P88", b="P114", c="P116", d="P111",
                            e="P105", f="P102", g="P100", dp="P98",
                            invert=True, attrs=Attrs(IOSTANDARD="LVTTL")
                            ),
        Resource("display_7seg_ctrl", 0,
                 Subsignal("en", Pins("P118 P117 P115 P112", dir="o", invert=True)),
                 Attrs(IOSTANDARD="LVTTL")
                 ),
    ]
    connectors = []

    def toolchain_program(self, products, name, **options):
        fpgaprog = os.environ.get("fpgaprog", "fpgaprog")
        with products.extract("{}.bit".format(name)) as bitstream_filename:
            if options.get("flash"):
                subprocess.run(
                    [fpgaprog, "-v", "-f", bitstream_filename, "-b", "bscan_spi_lx9.bit", "-sa", "-r"], check=True)
            else:
                subprocess.run(
                    [fpgaprog, "-v", "-f", bitstream_filename], check=True)
