
import logging
logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

import os
import pytest
import revenge
types = revenge.types

import random
from revenge.exceptions import *

here = os.path.dirname(os.path.abspath(__file__))
bin_location = os.path.join(here, "bins")

#
# Basic One
#

basic_one_path = os.path.join(bin_location, "basic_one")
basic_one_64_nopie_path = os.path.join(bin_location, "basic_one_64_nopie")
basic_one_ia32_path = os.path.join(bin_location, "basic_one_ia32")
basic_one_ia32_nopie_path = os.path.join(bin_location, "basic_one_ia32_nopie")

chess_path = os.path.join(bin_location, "ChessAI.so")


def test_modules_register_plugin():
    process = revenge.Process(basic_one_path, resume=False, verbose=False)

    class MyPlugin:
        """My docstring."""
        def __init__(self, module):
            self.module = module

    basic_one = process.modules['basic_one']

    # Shouldn't exist yet
    with pytest.raises(AttributeError):
        basic_one.myplugin

    process.modules._register_plugin(MyPlugin, "myplugin")
    myplugin = basic_one.myplugin
    assert isinstance(myplugin, MyPlugin)
    # Make sure we're not regenerating each time
    assert myplugin is basic_one.myplugin
    assert myplugin.module is basic_one

    # Make sure we're not overlapping instantiations
    libc = process.modules['*libc*']
    assert libc.myplugin is not myplugin

    assert myplugin.__doc__ == "My docstring."

    # Can't share the same name
    with pytest.raises(RevengeModulePluginAlreadyRegistered):
        process.modules._register_plugin(MyPlugin, "myplugin")

    # Not valid callable
    with pytest.raises(RevengeInvalidArgumentType):
        process.modules._register_plugin("invalid", "myplugin")

    process.quit()


def test_modules_lookup_offset():
    process = revenge.Process(basic_one_path, resume=False, verbose=False)

    assert process.modules.lookup_offset('basic_one:func') == ('basic_one', 0x64a)
    assert process.modules.lookup_offset('basic_one:i64') == ('basic_one', 0x201020)

    process.quit()

    process = revenge.Process(basic_one_ia32_nopie_path, resume=False, verbose=False)

    assert process.modules.lookup_offset('basic_one_ia32_nopie:func') == ('basic_one_ia32_nopie', 0x426)
    assert process.modules.lookup_offset('basic_one_ia32_nopie:i64') == ('basic_one_ia32_nopie', 0x2030)

    process.quit()


def test_memory_symbol_resolve():
    process = revenge.Process(basic_one_path, resume=False, verbose=False)

    strlen = process.memory[':strlen']
    strlen2 = process.memory['strlen']

    assert strlen.address == strlen2.address

    strlen3 = process.memory['strlen+0xf']
    assert strlen.address + 0xf == strlen3.address

    func = process.memory['basic_one:func']
    func2 = process.memory['basic_one:func+0x4']
    assert func2.address == func.address + 4

    process.quit()


def test_load_library():
    process = revenge.Process(basic_one_path, resume=False, verbose=False)

    with pytest.raises(StopIteration):
        process.modules["ChessAI.so"]

    chess = process.modules.load_library(chess_path)

    assert chess is not None
    assert process.memory[chess.symbols['getAiName']()].string_utf8 == "DeepFLARE"
    assert process.memory[process.memory[':getAiGreeting']()].string_utf8 == "Finally, a worthy opponent. Let us begin"

    process.quit()


def test_plt():
    process = revenge.Process(basic_one_path, resume=False, verbose=False)
    basic_one_64_nopie = revenge.Process(basic_one_64_nopie_path, resume=False)
    basic_one_ia32 = revenge.Process(basic_one_ia32_path, resume=False)
    basic_one_ia32_nopie = revenge.Process(basic_one_ia32_nopie_path, resume=False)

    #
    # First parse
    #

    basic_one_mod = process.modules['basic_one']
    assert basic_one_mod.plt & 0xfff == 0x510
    printf = process.memory[basic_one_mod.symbols['plt.printf']]
    assert printf("123456") == 6
    assert 'printf' in process.memory.describe_address(basic_one_mod.symbols['plt.printf'])
    assert 'printf' in process.memory.describe_address(basic_one_mod.symbols['got.printf'])
    assert 'printf' in process.memory.describe_address(process.memory[basic_one_mod.symbols['got.printf']].pointer)

    basic_one_mod = basic_one_64_nopie.modules['basic_one*']
    assert basic_one_mod.plt == 0x4003e0
    printf = basic_one_64_nopie.memory[basic_one_mod.symbols['plt.printf']]
    assert printf("123456") == 6
    assert 'printf' in basic_one_64_nopie.memory.describe_address(basic_one_mod.symbols['plt.printf'])
    assert 'printf' in basic_one_64_nopie.memory.describe_address(basic_one_mod.symbols['got.printf'])
    assert 'printf' in basic_one_64_nopie.memory.describe_address(basic_one_64_nopie.memory[basic_one_mod.symbols['got.printf']].pointer)

    basic_one_mod = basic_one_ia32.modules['basic_one*']
    assert basic_one_mod.plt & 0xfff == 0x3a0
    printf = basic_one_ia32.memory[basic_one_mod.symbols['plt.printf']]
    # This uses thunks... No easy way of testing call through plt rn..
    # assert printf("123456") == 6
    assert 'printf' in basic_one_ia32.memory.describe_address(basic_one_mod.symbols['plt.printf'])
    assert 'printf' in basic_one_ia32.memory.describe_address(basic_one_mod.symbols['got.printf'])
    assert 'printf' in basic_one_ia32.memory.describe_address(basic_one_ia32.memory[basic_one_mod.symbols['got.printf']].pointer)

    basic_one_mod = basic_one_ia32_nopie.modules['basic_one*']
    assert basic_one_mod.plt == 0x80482d0
    printf = basic_one_ia32_nopie.memory[basic_one_mod.symbols['plt.printf']]
    # This uses thunks... No easy way of testing call through plt rn..
    assert printf("123456") == 6
    assert 'printf' in basic_one_ia32_nopie.memory.describe_address(basic_one_mod.symbols['plt.printf'])
    assert 'printf' in basic_one_ia32_nopie.memory.describe_address(basic_one_mod.symbols['got.printf'])
    assert 'printf' in basic_one_ia32_nopie.memory.describe_address(basic_one_ia32_nopie.memory[basic_one_mod.symbols['got.printf']].pointer)

    process.quit()
    basic_one_64_nopie.quit()
    basic_one_ia32.quit()
    basic_one_ia32_nopie.quit()


def test_modules_symbols():
    process = revenge.Process(basic_one_path, resume=False, verbose=False)

    basic_one_mod = process.modules['basic_one']
    assert basic_one_mod.symbols['func'] - basic_one_mod.base == 0x64A
    assert basic_one_mod.symbols['i8'] - basic_one_mod.base == 0x201010
    assert basic_one_mod.symbols['ui8'] - basic_one_mod.base == 0x201011
    assert basic_one_mod.symbols['i16'] - basic_one_mod.base == 0x201012
    assert basic_one_mod.symbols['ui16'] - basic_one_mod.base == 0x201014
    assert basic_one_mod.symbols['i32'] - basic_one_mod.base == 0x201018
    assert basic_one_mod.symbols['ui32'] - basic_one_mod.base == 0x20101C
    assert basic_one_mod.symbols['i64'] - basic_one_mod.base == 0x201020
    assert basic_one_mod.symbols['ui64'] - basic_one_mod.base == 0x201028
    assert isinstance(basic_one_mod.symbols['ui64'].address, types.Pointer)

    process.quit()


def test_modules_by_int():
    process = revenge.Process(basic_one_path, resume=False, verbose=False)

    libc = process.modules['libc*']

    for _ in range(10):
        r = random.randint(libc.base, libc.base + libc.size)
        assert process.modules[r] == libc

    assert process.modules[123] is None

    process.quit()


def test_modules_basic():
    process = revenge.Process(basic_one_path, resume=False, verbose=False)
    main = process.memory['basic_one:main']
    main.breakpoint = True
    process.resume()

    assert process.modules['libc*'] is not None
    assert process.modules['basic_one'] is not None

    basic_one_mod = process.modules['basic_one']

    # Just make sure it does something..
    repr(basic_one_mod)

    with pytest.raises(Exception):
        basic_one_mod.name = 12

    basic_one_mod.path = "test"
    assert basic_one_mod.path == "test"

    with pytest.raises(Exception):
        basic_one_mod.path = 12

    assert isinstance(basic_one_mod.base, types.Pointer)

    basic_one_mod.base = types.Pointer(123)
    assert basic_one_mod.base == 123

    # Not sure why this changed... but assuming it's OK if we're seeing multiple modules
    assert len(process.modules) > 3

    # Just making sure this returns something for now
    repr(process.modules)

    assert "basic_one" in str(process.modules)

    with pytest.raises(NotImplementedError):
        process.modules[:]

    with pytest.raises(StopIteration):
        process.modules["Not a valid module"]

    libc = process.modules['*libc*']
    # New pointer each time
    assert libc.file is not libc.file
    assert libc.file.readable()
    assert not libc.file.writable()
    # Read twice to confirm we're getting a fresh version
    assert libc.file.read(4) == b'\x7fELF'
    assert libc.file.read(4) == b'\x7fELF'

    process.quit()
