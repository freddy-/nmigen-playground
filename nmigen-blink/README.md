# NMigen Blink

#### Usage:
Before any commmand run `load-x` to prepare the Xilinx ISE environment.

Generate .vcd file: 
```sh
$ python3 main.py simulate
```

View simulation:
```sh
$ gtkwave test.vcd &
```

Generate .bit:
```sh
$ python3 main.py build
```

Download bitstream into FPGA
```sh
$ python3 main.py program
```

Download bitstream and save in the flash
```sh
$ python3 main.py program -f
```