import hashlib


def calc_lic(mac_addr_colon_bdaddr):

    print "mac_addr:", mac_addr_colon_bdaddr
    shaer = hashlib.sha1()
    shaer.update("edg")
    shaer.update(mac_addr_colon_bdaddr.lower()+":edg_kub")
    shaer.update("edg")
    this_sha = shaer.hexdigest()
    return this_sha+"\n"


def hello_world(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    request_json = request.get_json()
    if request.args and 'message' in request.args:
        mcb = request_json['message']        
        return calc_lic(mcb)
    elif request_json and 'message' in request_json:
        mcb = request_json['message']        
        return calc_lic(mcb)
    else:
        return 'Hello World!'
