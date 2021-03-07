from bleson import get_provider, Advertiser, Advertisement
import bleson
import edg_gps_parser
import time

from bleson.core.roles import Advertiser
from bleson.core.types import Advertisement
from bleson.interfaces.adapter import Adapter
from bleson.logger import log

# https://github.com/google/eddystone/blob/master/protocol-specification.md
FRAME_TYPE_UID = 0x00
FRAME_TYPE_URL = 0x10
FRAME_TYPE_TLM = 0x20
FRAME_TYPE_EID = 0x30


class EcoDroidGPSBeacon(Advertiser):
    """ modified from some bleson example...       
    """
    def __init__(self, adapter, url=None, tlm=None, eid=None):
        super().__init__(adapter)
        self.advertisement=Advertisement()
        self.url = url
        self.tlm = tlm
        self.eid = eid

    @property
    def url(self):
        return self._url

    @property
    def tlm(self):
        return self._tlm

    @property
    def eid(self):
        return self._eid

    @url.setter
    def url(self, url):
        self._url = url
        if url:
            self.advertisement.raw_data=self.eddystone_type_adv_data(url, FRAME_TYPE_URL)
            log.debug("Beacon Adv URL raw data = {}".format(self.advertisement.raw_data))

    @tlm.setter
    def tlm(self, tlm):
        self._tlm = tlm
        if tlm:
            self.advertisement.raw_data=self.eddystone_type_adv_data(tlm, FRAME_TYPE_TLM)
            log.debug("Beacon Adv TLM raw data = {}".format(self.advertisement.raw_data))

    @eid.setter
    def eid(self, eid):
        self._eid = eid
        if eid:
            self.advertisement.raw_data=self.eddystone_type_adv_data(eid, FRAME_TYPE_EID)
            log.debug("Beacon Adv EID raw data = {}".format(self.advertisement.raw_data))

    # -------------------------------------------
    # Eddystone  (pretty much as-is from the Google source)
    # see: https://github.com/google/eddystone/blob/master/eddystone-url/implementations/PyBeacon/PyBeacon/PyBeacon.py

    schemes = [
        "http://www.",
        "https://www.",
        "http://",
        "https://",
    ]

    extensions = [
        ".com/", ".org/", ".edu/", ".net/", ".info/", ".biz/", ".gov/",
        ".com", ".org", ".edu", ".net", ".info", ".biz", ".gov",
    ]

    @classmethod
    def encode_url(cls, url):
        return list(range(18))
        i = 0
        data = []

        for s in range(len(cls.schemes)):
            scheme = cls.schemes[s]
            if url.startswith(scheme):
                data.append(s)
                i += len(scheme)
                break
        else:
            raise Exception("Invalid url scheme")

        while i < len(url):
            if url[i] == '.':
                for e in range(len(cls.extensions)):
                    expansion = cls.extensions[e]
                    if url.startswith(expansion, i):
                        data.append(e)
                        i += len(expansion)
                        break
                else:
                    data.append(0x2E)
                    i += 1
            else:
                data.append(ord(url[i]))
                i += 1

        return data

    @classmethod
    def eddystone_type_adv_data(cls, data, frame_type):
        log.info("Encoding data for Eddystone beacon: '{}'".format(data))
        data_len = len(data)
        print(("data_len:", data_len))

        message = [
                0x02,   # Flags length
                0x01,   # Flags data type value
                0x1a,   # Flags data

                0x03,   # Service UUID length
                0x03,   # Service UUID data type value
                0xaa,   # 16-bit Eddystone UUID
                0xfe,   # 16-bit Eddystone UUID

                5 + len(data), # Service Data length
                0x16,   # Service Data data type value
                0xaa,   # 16-bit Eddystone UUID
                0xfe,   # 16-bit Eddystone UUID

                frame_type,   # Eddystone-url frame type
                0x00,   # txpower
                ]

        message += data

        return bytearray(message)

    
