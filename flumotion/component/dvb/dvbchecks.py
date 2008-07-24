# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

# This file may be distributed and/or modified under the terms of
# the GNU General Public License version 2 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.GPL" in the source distribution for more information.

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

import os
import string

import gobject
import gst
from twisted.internet import defer

from flumotion.common import gstreamer, log, messages
from flumotion.worker.checks import check
from flumotion.worker.checks.gst010 import do_element_check

__version__ = "$Rev: 6883 $"

def getListOfAdaptersWithTypes():
    """
    Probe the system to find adapters and types.
    Returns a list of dvb type, adapter number, human-readable
    device name

    @rtype: L{twisted.internet.defer.Deferred}
    """
    result = messages.Result()
    def get_type_of_adapter(adapter):
        dvbelement = gst.element_factory_make ("dvbsrc", "test_dvbsrc")
        dvbelement.set_property("adapter", adapter)
        pipeline = gst.Pipeline("")
        pipeline.add(dvbelement)
        pipeline.set_state(gst.STATE_READY)
        pipeline.get_state()
        bus = pipeline.get_bus()
        adaptertype = None
        while bus.have_pending():
            msg = bus.pop()
            if msg.type == gst.MESSAGE_ELEMENT and msg.src == dvbelement:
                structure = msg.structure
                if structure.get_name() == "dvb-adapter":
                    adaptertype = structure["type"]
                    break
        pipeline.set_state(gst.STATE_NULL)
        return adaptertype
    # FIXME: use hal instead
    adapterlist = []
    for i in range (0,8):
        if os.path.exists('/dev/dvb/adapter%d/frontend0' % i):
            adaptertype = get_type_of_adapter(i)
            adapterlist.append((adaptertype, i, "DVB (%s) Adapter %d" % (
                    adaptertype,i)))
    result.succeed(adapterlist)
    return result

def getTerrestrialLocations():
    """
    Find from the system to find locations where initial tuning data is
    available.
    Returns a dict with country -> list of (city, absolute filename)

    @rtype: L{twisted.internet.defer.Deferred}
    """
    def splitLocation(location):
        return string.split(location, "-", maxsplit=1)
    result = messages.Result()
    locations = {}
    for path in ["/usr/share/dvb", "/usr/share/dvb-apps", 
            "/usr/share/doc/dvb-utils/examples/scan"]:
        if os.path.exists(path):
            for f in os.listdir(os.path.join(path, 'dvb-t')):
                country = "Unknown"
                city = ""
                try:
                    country, city = splitLocation(f)
                except Exception, e:
                    city = f
                if not locations.has_key(country):
                    locations[country] = []
                print "Adding country %s city %s" % (country, city)
                locations[country].append(
                    (city, os.path.join(path, 'dvb-t', f)))

    result.succeed(locations)
    return result

def getInitialTuning(adapterType, initialTuningFile):
    """
    Provide initial tuning parameters.
    Returns a dict with tuning parameters.
    """
    result = messages.Result()
    ret = []
    if os.path.exists(initialTuningFile):
        f = open(initialTuningFile, "r")
        while True:
            line = f.readline()
            if not line:
                break
            if line[0] != '#':
                params = line[:-1].split(" ")
                if params[0] == "T" and adapterType == "DVB-T":
                    if len(params) == 9:
                        d = { "frequency":int(params[1]),
                              "bandwidth":int(params[2][0]),
                              "code-rate-hp":params[3],
                              "code-rate-lp":params[4],
                              "constellation":params[5],
                              "transmission-mode":params[6],
                              "guard-interval":int(params[7].split("/")[1]),
                              "hierarchy":params[8]}
                        ret.append(d)
                    elif params[0] == "S" and adapterType == "DVB-S":
                        if len(params) == 5:
                            d = { "frequency":int(params[1]),
                                  "symbol-rate":int(params[3])/1000,
                                  "inner-fec":params[4] }
                            if params[2] == "V":
                                d["polarization"] = "vertical"
                            else:
                                d["polarization"] = "horizontal"
                            ret.append(d)
                    elif params[0] == "C" and adapterType == "DVB-C":
                        if len(params) == 5:
                            d = { "frequency":int(params[1]),
                                  "symbol-rate":int(params[2])/1000,
                                  "inner-fec":params[3],
                                  "modulation":params[4] }
                            ret.append(d)
        f.close()
    result.succeed(ret)
    return result


class DVBScanner:
    def __init__(self, adapter=0, frontend=0, scanning_complete_cb=None,
        channel_added_cb=None):
        self.adapter = adapter
        self.frontend = frontend
        self.adaptertype = None
        self.channels = {} # service id -> transport stream id
        self.current_tuning_params = {}
        self.transport_streams = {} # ts id -> tuning_params
        self.pipeline = None
        self.locked = False
        self.nit_arrived = False
        self.sdt_arrived = False
        self.pat_arrived = False
        self.check_for_lock_event_id = None
        self.wait_for_tables_event_id = None
        self.scanning_complete_cb = scanning_complete_cb
        self.channel_added_cb = channel_added_cb

        self.pipeline =  gst.parse_launch(
            "dvbsrc name=dvbsrc adapter=%d frontend=%d pids=0:16:17:18 " \
            "stats-reporting-interval=0 ! mpegtsparse ! " \
            "fakesink silent=true" % (self.adapter, self.frontend))
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.bus_watch_func)
        self.pipeline.set_state(gst.STATE_READY)
        self.pipeline.get_state()

    def wait_for_tables(self):
        self.pipeline.set_state(gst.STATE_READY)
        self.pipeline.get_state()
        self.locked = False
        self.scanned = False
        if self.scanning_complete_cb:
            self.scanning_complete_cb()

    def check_for_lock(self):
        if not self.locked:
            self.pipeline.set_state(gst.STATE_READY)
        # block until state change completed
        self.pipeline.get_state()
        self.scanned = False
        
        self.scanning_complete_cb()
        return False

    def have_dvb_adapter_type(self, type):
        self.adaptertype = type
        print "Adapter type is %s" % type

    def bus_watch_func(self, bus, message):
        t = message.type
        #print "Bus watch function for message %r" % message
        if t == gst.MESSAGE_ELEMENT:
            if message.structure.get_name() == 'dvb-adapter':
                s = message.structure
                self.have_dvb_adapter_type(s["type"])
            elif message.structure.get_name() == 'dvb-frontend-stats':
                s = message.structure
                if s["lock"] and not self.locked:
                    self.locked = True
                    gobject.source_remove(self.check_for_lock_event_id)
                    self.check_for_lock_event_id = None
                    self.wait_for_tables_event_id = gobject.timeout_add(
                        10*1000, 
                        self.wait_for_tables)
            elif message.structure.get_name() == 'dvb-read-failure':
                if self.check_for_lock_event_id:
                    gobject.source_remove(self.check_for_lock_event_id)
                    self.check_for_lock_event_id = None
                if self.wait_for_tables_event_id:
                    gobject.source_remove(self.wait_for_tables_event_id)
                    self.wait_for_tables_event_id = None
                self.wait_for_tables()
            elif message.structure.get_name() == 'sdt':
                s = message.structure
                services = s["services"]
                tsid = s["transport-stream-id"]
                actual = s["actual-transport-stream"]
                if actual:
                    for service in services:
                        name = service.get_name()
                        sid = int(name[8:])
                        if service.has_key("name"):
                            name = service["name"]
                        if self.channels.has_key(sid):
                            self.channels[sid]["name"] = name
                            self.channels[sid]["transport-stream-id"] = tsid
                        else:
                            self.channels[sid] = { "name": name, \
                                "transport-stream-id": tsid }
                        if self.channel_added_cb:
                            self.channel_added_cb(sid, self.channels[sid])
                    self.sdt_arrived = True

            elif message.structure.get_name() == 'nit':
                s = message.structure
                name = s["network-id"]
                actual = s["actual-network"]
                if s.has_key("network-name"):
                    name = s["network-name"]
                transports = s["transports"]
                for transport in transports:
                    tsid = transport["transport-stream-id"]
                    if transport.has_key("delivery"):
                        delivery = transport["delivery"]
                        self.transport_streams[tsid] = dict(delivery)
                        if transport.has_key("channels"):
                            chans = transport["channels"]
                            for chan in chans:
                                if self.channels.has_key(
                                    chan["service-id"]):
                                    self.channels[chan["service-id"]]["logical-channel-number"] = chan["logical-channel-number"]
                                else:
                                    self.channels[chan["service-id"]] = { "logical-channel-number" : chan["logical-channel-number"] }
                self.nit_arrived = True
            elif message.structure.get_name() == 'pat':
                programs = message.structure["programs"]
                for p in programs:
                    sid = p["program-number"]
                    pmt = p["pid"]
                    if self.channels.has_key(sid):
                        self.channels[sid]["pmt-pid"] = pmt
                    else:
                        self.channels[sid] = { "pmt-pid":pmt }
                self.pat_arrived = True

        if self.sdt_arrived and self.nit_arrived and self.pat_arrived:
            gobject.source_remove(self.wait_for_tables_event_id)
            self.wait_for_tables()

    def scan(self, tuning_params):
        self.current_tuning_params = tuning_params
        self.sdt_arrived = False
        self.nit_arrived = False
        self.pat_arrived = False
        
        if self.adaptertype == "DVB-T":
            modulation=""
            if tuning_params["constellation"].startswith("QAM"):
                modulation="QAM %s" % tuning_params["constellation"][3:]
            elif tuning_params["constellation"] == "reserved":
                modulation = "QAM 64"
            else:
                modulation = tuning_params["constellation"]
            for param in ["code-rate-hp", "code-rate-lp"]:
                if tuning_params[param] == "reserved":
                    tuning_params[param] = "NONE"
            if tuning_params["hierarchy"] ==  0:
                tuning_params["hierarchy"] = "NONE"
            dvbsrc = self.pipeline.get_by_name("dvbsrc")
            print "Frequency: %s" % (tuning_params["frequency"],)
            dvbsrc.set_property("frequency", tuning_params["frequency"])
            dvbsrc.set_property("bandwidth", str(tuning_params["bandwidth"]))
            dvbsrc.set_property("code-rate-hp",
                str(tuning_params["code-rate-hp"]))
            dvbsrc.set_property("code-rate-lp", 
                str(tuning_params["code-rate-lp"]))
            dvbsrc.set_property("trans-mode", 
                str(tuning_params["transmission-mode"]))
            dvbsrc.set_property("guard", str(tuning_params["guard-interval"]))
            dvbsrc.set_property("hierarchy", str(tuning_params["hierarchy"]))
            dvbsrc.set_property("modulation", modulation)
        elif self.adaptertype == "DVB-S":
            if tuning_params["inner-fec"] == "reserved" or \
               tuning_params["inner-fec"] == "none":
                tuning_params["inner-fec"] = "NONE"
            dvbsrc = self.pipeline.get_by_name("dvbsrc")
            dvbsrc.set_property("frequency", tuning_params["frequency"])
            dvbsrc.set_property("polarity", tuning_params["polarization"][0])
            dvbsrc.set_property("symbol-rate", tuning_params["symbol-rate"])
            dvbsrc.set_property("code-rate-hp", tuning_params["inner-fec"])
        elif self.adaptertype == "DVB-C":
            if tuning_params["inner-fec"] == "reserved" or \
               tuning_params["inner-fec"] == "none":
                tuning_params["inner-fec"] = "NONE"

            dvbsrc = self.pipeline.get_by_name("dvbsrc")
            dvbsrc.set_property("inversion", "AUTO")
            dvbsrc.set_property("frequency", tuning_params["frequency"])
            dvbsrc.set_property("symbol-rate", tuning_params["symbol-rate"])
            dvbsrc.set_property("code-rate-hp", tuning_params["inner-fec"])
            modulation=""
            if tuning_params["modulation"].startswith("QAM"):
                modulation="QAM %s" % tuning_params["modulation"][3:]
            elif tuning_params["modulation"] == "reserved":
                modulation = "QAM 64"
            else:
                modulation = tuning_params["modulation"]
            dvbsrc.set_property("modulation", modulation)
            
        self.pipeline.set_state(gst.STATE_PLAYING)
        (statereturn, state, pending) = self.pipeline.get_state()
        self.locked = False
        if statereturn == gst.STATE_CHANGE_FAILURE:
            self.check_for_lock()
        else:
            # wait 10 seconds for lock 
            self.check_for_lock_event_id = gobject.timeout_add(10*1000, 
                self.check_for_lock)

def scan(adapterNumber, dvbType, tuningInfo):
    d = defer.Deferred()
    scanner = None
    def scanningComplete():
        print "Scanning complete"
        result = messages.Result()
        result.succeed((scanner.channels, scanner.transport_streams))
        d.callback(result)

    scanner = DVBScanner(adapter=adapterNumber, 
        scanning_complete_cb=scanningComplete)
    scanner.adaptertype = dvbType
    scanner.scan(tuningInfo)
    return d

def checkWebcam(device, id):
    """
    Probe the given device node as a webcam.

    The result is either:
     - succesful, with a None value: no device found
     - succesful, with a tuple:
                  - device name
                  - dict of mime, format, width, height, fps pair
     - failed

    @rtype: L{flumotion.common.messages.Result}
    """
    # FIXME: add code that checks permissions and ownership on errors,
    # so that we can offer helpful hints on what to do.
    def probeDevice(element):
        name = element.get_property('device-name')
        caps = element.get_pad("src").get_caps()
        log.debug('check', 'caps: %s' % caps.to_string())

        sizes = {} # (width, height) => [{'framerate': (framerate_num,
                   #                                    framerate_denom),
                   #                      'mime': str,
                   #                      'fourcc': fourcc}]

        def forAllStructValues(struct, key, proc):
            vals = struct[key]
            if isinstance(vals, list):
                for val in vals:
                    proc(struct, val)
            elif isinstance(vals, gst.IntRange):
                val = vals.low
                while val < vals.high:
                    proc(struct, val)
                    val *= 2
                proc(struct, vals.high)
            elif isinstance(vals, gst.DoubleRange):
                # hack :)
                proc(struct, vals.high)
            elif isinstance(vals, gst.FractionRange):
                # hack :)
                proc(struct, vals.high)
            else:
                # scalar
                proc(struct, vals)
        def addRatesForWidth(struct, width):
            def addRatesForHeight(struct, height):
                def addRate(struct, rate):
                    if (width, height) not in sizes:
                        sizes[(width, height)] = []
                    d = {'framerate': (rate.num, rate.denom),
                         'mime': struct.get_name()}
                    if 'yuv' in d['mime']:
                        d['format'] = struct['format'].fourcc
                    sizes[(width, height)].append(d)
                forAllStructValues(struct, 'framerate', addRate)
            forAllStructValues(struct, 'height', addRatesForHeight)
        for struct in caps:
            if 'yuv' not in struct.get_name():
                continue
            forAllStructValues(struct, 'width', addRatesForWidth)

        return (name, element.get_factory().get_name(), sizes)

    def tryV4L2():
        log.debug('webcam', 'trying v4l2')
        version = gstreamer.get_plugin_version('video4linux2')
        minVersion = (0, 10, 5, 1)
        if not version or version < minVersion:
            log.info('webcam', 'v4l2 version %r too old (need >=%r)',
                     version, minVersion)
            return defer.fail(NotImplementedError())

        pipeline = 'v4l2src name=source device=%s ! fakesink' % (device,)
        d = do_element_check(pipeline, 'source', probeDevice,
                             state=gst.STATE_PAUSED, set_state_deferred=True)
        return d

    def tryV4L1(_):
        log.debug('webcam', 'trying v4l1')
        pipeline = 'v4lsrc name=source device=%s ! fakesink' % (device,)
        d = do_element_check(pipeline, 'source', probeDevice,
                             state=gst.STATE_PAUSED, set_state_deferred=True)
        return d

    result = messages.Result()

    d = tryV4L2()
    d.addErrback(tryV4L1)
    d.addCallback(check.callbackResult, result)
    d.addErrback(check.errbackNotFoundResult, result, id, device)
    d.addErrback(check.errbackResult, result, id, device)

    return d