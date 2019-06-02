import dbus
import dbus.service
import bt_spp_funcs

__copyright__ = "EcoDroidGPS Copyright (c) 2019 Kasidit Yusuf. All rights reserved."
__author__ = "Kasidit Yusuf"
__email__ = "ykasidit@gmail.com"
__status__ = "Production"
__website__="www.ClearEvo.com"


class Profile(dbus.service.Object):

    @dbus.service.method("org.bluez.Profile1",
                         in_signature="", out_signature="")
    def Release(self):
        bt_spp_funcs.on_release(self)

    @dbus.service.method("org.bluez.Profile1",
                         in_signature="", out_signature="")
    def Cancel(self):
        bt_spp_funcs.on_cancel(self)

    @dbus.service.method("org.bluez.Profile1",
                         in_signature="o", out_signature="")
    def RequestDisconnection(self, device):
        bt_spp_funcs.on_req_disconnection(self, device)

    @dbus.service.method("org.bluez.Profile1",
                         in_signature="oha{sv}", out_signature="")
    def NewConnection(self, device, dbus_fd, properties):
        bt_spp_funcs.on_new_connection(self, device, dbus_fd, properties)

    vars_dict = None

    def set_vars_dict(self, vd):
        self.vars_dict = vd
