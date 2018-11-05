import bt_spp_funcs
import ecodroidgps_server


def test():

    gd = ecodroidgps_server.alloc_gps_data_queues_dict()

    i = bt_spp_funcs.get_q_list_avail_index(gd)
    assert i == 0

    pre_loop_i = bt_spp_funcs.get_q_list_avail_index(gd)
    bt_spp_funcs.release_q_list_index(gd, pre_loop_i)
    
    n_rounds = 100
    n_alloc = 10

    for round in range(n_rounds):
        to_release = []
        for a in range(n_alloc):
            i = bt_spp_funcs.get_q_list_avail_index(gd)
            to_release.append(i)
            print "alloc got i", i
        for i in to_release:
            bt_spp_funcs.release_q_list_index(gd, i)
            
    i = bt_spp_funcs.get_q_list_avail_index(gd)
    print "final alloc i:", i
    assert i == pre_loop_i

    # no release this one

    more_n = 29
    for r in range(more_n):
        bt_spp_funcs.get_q_list_avail_index(gd)

    i = bt_spp_funcs.get_q_list_avail_index(gd)
    print "final post more_n got i", i
    assert i == pre_loop_i + more_n + 1
        
            
    


if __name__ == "__main__":
    test()
