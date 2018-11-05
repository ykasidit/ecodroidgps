import bit_utils


def test():

    assert bit_utils.test_bit(1, 0)    
    assert bit_utils.test_bit(4, 2)
    assert bit_utils.test_bit(8, 3)

    val = long(0)

    val = bit_utils.set_bit(val, 0)
    assert val == 1  # 0+1

    val = bit_utils.set_bit(val, 2)
    assert val == 5  # 4+1

    val = bit_utils.set_bit(val, 3)
    assert val == 13  # 5 + 8

    val = bit_utils.clear_bit(val, 3)
    assert val == 5  # 13 - 8

    val = bit_utils.clear_bit(val, 0)
    assert val == 4  # 5 - 1

    val = bit_utils.clear_bit(val, 2)
    assert val == 0  # 4 - 4
    
    print "test_bit_utils all passed"
    


if __name__ == "__main__":
    test()
