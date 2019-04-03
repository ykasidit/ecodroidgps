import os
from dl_lic import dl_lic


def test(save_path='test.lic'):
    ret = dl_lic("02:42:3c:9e:35:09","e4:f6:ca:7b:8a:2f", save_path)
    print "cmd ret:", ret
    assert 0 == os.system("cat {} | grep d7d06845506a434f23420ec6df71cb674ca054f6".format(save_path))

    
if __name__ == "__main__":
    test()
    
