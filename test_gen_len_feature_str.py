import edg_utils


def test():

    ret = edg_utils.gen_edg_ln_feature_bitmask_hex_dump_str()
    print(("gen_edg_ln_feature_bitmask_hex_dump_str() ret:", ret))
    assert ret == '4d001000'

if __name__ == "__main__":
    test()
