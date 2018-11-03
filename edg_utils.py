import math
import os
import sys


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
