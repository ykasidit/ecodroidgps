import os
from dl_lic import dl_lic

def test():
    ret = dl_lic("02:42:3c:9e:35:09","e4:f6:ca:7b:8a:2f","edg.lic")
    print "cmd ret:", ret
    os.system("cat edg.lic")

    
if __name__ == "__main__":
    test()
    
