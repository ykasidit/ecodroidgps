from libc.stdint cimport uint64_t, uint8_t

cpdef uint64_t ONE = 1

cpdef long set_bit(uint64_t value, uint8_t bit):
    return value | (ONE<<bit)


cpdef long clear_bit(uint64_t value, uint8_t bit):
    return value & ~(ONE<<bit)


cpdef long test_bit(uint64_t value, uint8_t bit):
    return value & (ONE<<bit)


