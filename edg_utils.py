import math
import os
import sys
import bit_utils
import ble_bit_offsets
import numpy as np



# https://stackoverflow.com/questions/19225188/what-method-can-i-use-instead-of-file-in-python
import inspect
if not hasattr(sys.modules[__name__], '__file__'):
    __file__ = inspect.getfile(inspect.currentframe())

###    

def get_module_path():
    return os.path.realpath(
        os.path.join(os.getcwd(), os.path.dirname(__file__))
    )
    

# amazing formula - from https://stackoverflow.com/questions/8898807/pythonic-way-to-iterate-over-bits-of-integer
def bits(n):
    while n:
        b = n & (~n+1)
        yield b
        n ^= b
        
        
def get_on_bit_offset_list(val):
    ret = []
    for b in bits(val):
        ret.append(long(math.log(b,2))) # b is value, we want bit offset
    return ret


def gen_edg_ln_feature_bitmask_hex_dump_str():
    # gen lnf bitmask
    bitmask = long(0)

    ln_bits = [
        ble_bit_offsets.Instantaneous_Speed_Supported,
        ble_bit_offsets.Location_Supported,
        ble_bit_offsets.Elevation_Supported,
        ble_bit_offsets.UTC_Time_Supported,
        ble_bit_offsets.Position_Status_Supported
    ]
    for bit_offset in ln_bits:
        print "turn on bit:", bit_offset
        bitmask = bit_utils.set_bit(bitmask, bit_offset)

    buffer = np.getbuffer(np.uint32(bitmask))
    print "buffer: {} type: {}", buffer, type(buffer)
    return str(buffer).encode('hex')
