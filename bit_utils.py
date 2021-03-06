ONE = 1

def set_bit(value, bit):
    return value | (ONE<<bit)


def clear_bit(value, bit):
    return value & ~(ONE<<bit)


def test_bit(value, bit):
    return value & (ONE<<bit)


