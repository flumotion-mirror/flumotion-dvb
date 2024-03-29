# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.


import os
import string

import gobject
import gst
from twisted.internet import defer

from flumotion.common import log, messages, errors
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
        dvbelement = gst.element_factory_make("dvbsrc", "test_dvbsrc")
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
    for i in range(0, 8):
        if os.path.exists('/dev/dvb/adapter%d/frontend0' % i):
            adaptertype = get_type_of_adapter(i)
            adapterlist.append((adaptertype, i, "DVB (%s) Adapter %d" % (
                    adaptertype, i)))
    result.succeed(adapterlist)
    return result


def getAntennaeLocations():
    """
    Find from the system to find antennae where initial tuning data is
    available.
    Returns a dict with adapter type -> antennae
    where if adapter type is DVB-T antennae is:
       country -> list of (city, absolute filename)
    and if adapter type is DVB-S antennae is:
       list of satellites
    @rtype: L{twisted.internet.defer.Deferred}
    """
    # FIXME: allow translation
    # countries not taken from iso xml file because the country codes used
    #
    countries = {"at": "Austria",
                 "au": "Australia",
                 "be": "Belgium",
                 "ch": "Switzerland",
                 "cz": "Czech Republic",
                 "de": "Germany",
                 "dk": "Denmark",
                 "es": "Spain",
                 "fi": "Finland",
                 "fr": "France",
                 "gr": "Greece",
                 "hr": "Hungary",
                 "is": "Iceland",
                 "it": "Italy",
                 "lu": "Luxemburg",
                 "nl": "Netherlands",
                 "nz": "New Zealand",
                 "pl": "Poland",
                 "se": "Sweden",
                 "sk": "Slovakia",
                 "tw": "Taiwan",
                 "uk": "United Kingdom",
                 }

    def splitLocation(location):
        return string.split(location, "-", maxsplit=1)

    def camelCaseToTitleCase(location):
        # antennae are listed as eg CrystalPalace not Crystal Palace
        # so convert
        # there has to be a decent regex to convert upper camel case to
        # title case
        # We also have atannaes separated by - or _
        location = location.replace('-', '')
        location = location.replace('_', '')
        newlocation = location[0]
        for l in location[1:]:
            if l.isupper():
                newlocation = "%s %s" % (newlocation, l)
            else:
                newlocation = "%s%s" % (newlocation, l)
        return newlocation

    result = messages.Result()
    locations = {}
    terrestrialLocations = {}
    for path in ["/usr/share/dvb",
                 "/usr/share/dvb-apps",
                 "/usr/share/doc/dvb-utils/examples/scan"]:
        if os.path.exists(path):
            for f in os.listdir(os.path.join(path, 'dvb-t')):
                country = "Unknown"
                city = ""
                try:
                    country, city = splitLocation(f)
                    country = countries[country]
                    city = camelCaseToTitleCase(city)
                except Exception:
                    city = f
                log.debug('check', 'Adding country %s city %s', country, city)
                terrestrialLocations.setdefault(country, []).append(
                    (city, os.path.join(path, 'dvb-t', f)))
    locations["DVB-T"] = terrestrialLocations
    # now do satellite
    satellites = []
    for path in ["/usr/share/dvb",
                 "/usr/share/dvb-apps",
                 "/usr/share/doc/dvb-utils/examples/scan"]:
        if os.path.exists(path):
            for f in os.listdir(os.path.join(path, 'dvb-s')):
                satellites.append((f, os.path.join(path, 'dvb-s', f)))
    locations["DVB-S"] = satellites

    result.succeed(locations)
    return result


def getInitialTuning(adapterType, initialTuningFile):
    """
    Provide initial tuning parameters.
    Returns a dict with tuning parameters.
    """
    result = messages.Result()
    ret = []
    if not os.path.exists(initialTuningFile):
        result.succeed(ret)
        return result

    for line in open(initialTuningFile, "r"):
        log.debug('check', 'line in file: %s' % line)

        if not line:
            break
        if line[0] == '#':
            continue
        params = line[:-1].split(" ")

        if params[0] == "T" and adapterType == "DVB-T":
            if len(params) < 9:
                continue
            d = {"frequency": int(params[1]),
                 "bandwidth": int(params[2][0]),
                 "code-rate-hp": params[3],
                 "code-rate-lp": params[4],
                 "constellation": params[5],
                 "transmission-mode": params[6],
                 "guard-interval": int(params[7].split("/")[1]),
                 "hierarchy": params[8]}
            ret.append(d)
        elif params[0] == "S" and adapterType == "DVB-S":
            if len(params) != 5:
                continue
            d = {"frequency": int(params[1]),
                 "symbol-rate": int(params[3])/1000,
                 "inner-fec": params[4],
                 }
            if params[2] == "V":
                d["polarization"] = "vertical"
            else:
                d["polarization"] = "horizontal"
            ret.append(d)
        elif params[0] == "C" and adapterType == "DVB-C":
            if len(params) != 5:
                continue
            d = {"frequency": int(params[1]),
                 "symbol-rate": int(params[2])/1000,
                 "inner-fec": params[3],
                 "modulation": params[4],
                 }
            ret.append(d)

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
        self.pmt_arrived = False
        self.check_for_lock_event_id = None
        self.wait_for_tables_event_id = None
        self.tables_arrived = False
        self.scanning_complete_cb = scanning_complete_cb
        self.channel_added_cb = channel_added_cb

        self.pipeline = gst.parse_launch(
            "dvbsrc name=dvbsrc adapter=%d frontend=%d "
            "stats-reporting-interval=0 ! mpegtsparse ! "
            "fakesink silent=true" % (self.adapter, self.frontend))
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.bus_watch_func)
        self.pipeline.set_state(gst.STATE_READY)
        self.pipeline.get_state()

    def wait_for_tables(self):
        if not self.tables_arrived:
            self.tables_arrived = True
            self.pipeline.set_state(gst.STATE_READY)
            log.debug('dvbscanner', 'Setting pipeline to ready!!')
            self.pipeline.get_state()
            log.debug('dvbscanner', 'Pipeline SET to ready!!')
            self.locked = False
            self.scanned = False
            if self.wait_for_tables_event_id:
                gobject.source_remove(self.wait_for_tables_event_id)
                self.wait_for_tables_event_id = None
                if self.scanning_complete_cb:
                    self.scanning_complete_cb()
        else:
            log.debug('dvbscanner', 'TABLES HAVE ARRIVED!!!')

    def check_for_lock(self):
        if not self.locked:
            log.debug('check', 'Don\'t have lock!')
            self.pipeline.set_state(gst.STATE_READY)
            # block until state change completed
            self.pipeline.get_state()
            log.debug('check', 'Pipeline now ready')
            self.scanned = False

            self.scanning_complete_cb()
            return False

    def have_dvb_adapter_type(self, atype):
        self.adaptertype = atype
        log.debug('check', 'Adapter type is %s', atype)

    def bus_watch_func(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_ELEMENT:
            if message.structure.get_name() == 'dvb-adapter':
                s = message.structure
                self.have_dvb_adapter_type(s["type"])
            elif message.structure.get_name() == 'dvb-frontend-stats':
                s = message.structure
                if s["lock"] and not self.locked:
                    log.debug('check', 'Have locked!')
                    self.locked = True
                    gobject.source_remove(self. check_for_lock_event_id)
                    self.check_for_lock_event_id = None
                    self.wait_for_tables_event_id = gobject.timeout_add(
                        10*1000,
                        self.wait_for_tables)
            elif message.structure.get_name() == 'dvb-read-failure':
                log.debug("dvbscanner",
                          "DVB READ FAILURE! Time to stop pipeline")
                if self.check_for_lock_event_id:
                    gobject.source_remove(self.check_for_lock_event_id)
                    self.check_for_lock_event_id = None
                self.wait_for_tables()
            elif message.structure.get_name() == 'sdt':
                log.debug('check', 'Received SDT')
                s = message.structure
                services = s["services"]
                tsid = s["transport-stream-id"]
                actual = s["actual-transport-stream"]
                if actual:
                    for service in services:
                        name = service.get_name()
                        log.debug('check', 'Name: %s Structure: %r',
                                  name, service)
                        sid = int(name[8:])
                        if service.has_field("name"):
                            name = service["name"]
                        if sid in self.channels:
                            self.channels[sid]["name"] = name
                            self.channels[sid]["transport-stream-id"] = tsid
                        else:
                            self.channels[sid] = {
                                "name": name,
                                "transport-stream-id": tsid,
                                }
                        if self.channel_added_cb:
                            self.channel_added_cb(sid, self.channels[sid])
                    self.sdt_arrived = True

            elif message.structure.get_name() == 'nit':
                log.debug('check', 'Received NIT')
                s = message.structure
                name = s["network-id"]
                actual = s["actual-network"]
                if s.has_field("network-name"):
                    name = s["network-name"]
                transports = s["transports"]
                for transport in transports:
                    tsid = transport["transport-stream-id"]
                    if not transport.has_field("delivery"):
                        continue
                    delivery = transport["delivery"]
                    self.transport_streams[tsid] = dict(delivery)
                    if not transport.has_field("channels"):
                        continue
                    chans = transport["channels"]
                    for chan in chans:
                        serviceId = chan["service-id"]
                        chanKey = "logical-channel-number"
                        logicalChannel = chan[chanKey]
                        if chan["service-id"] in self.channels:
                            self.channels[serviceId][chanKey] = logicalChannel
                        else:
                            self.channels[serviceId] = {
                                chanKey: logicalChannel}
                self.nit_arrived = True
            elif message.structure.get_name() == 'pat':
                log.debug('check', 'Received PAT')
                programs = message.structure["programs"]
                for p in programs:
                    sid = p["program-number"]
                    pmt = p["pid"]
                    if sid in self.channels:
                        self.channels[sid]["pmt-pid"] = pmt
                    else:
                        self.channels[sid] = {"pmt-pid": pmt}
                self.pat_arrived = True
            elif message.structure.get_name() == 'pmt':
                log.debug('check', 'Received PMT')
                sid = message.structure['program-number']
                streams = message.structure['streams']
                if sid not in self.channels and streams:
                    self.channels[sid] = {}
                if 'audio-streams' not in self.channels[sid]:
                    self.channels[sid]['audio-streams'] = []
                if 'video-streams' not in self.channels[sid]:
                    self.channels[sid]['video-streams'] = []

                for s in streams:
                    st = s['stream-type']
                    if st in [1, 2]:
                        self.channels[sid]['video-streams'].append(s['pid'])
                    elif st in [3, 4]:
                        lang = ('pid-%s' % s['pid'], s['pid'])
                        if s.has_field('lang-code'):
                            lang = (s['lang-code'], s['pid'])

                        self.channels[sid]['audio-streams'].append(lang)
                self.pmt_arrived = True


        if (self.sdt_arrived and self.nit_arrived and
            self.pat_arrived and self.pmt_arrived):
            self.wait_for_tables()

    def scan(self, tuning_params):
        self.current_tuning_params = tuning_params
        self.sdt_arrived = False
        self.nit_arrived = False
        self.pat_arrived = False
        self.pmt_arrived = False

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
            if tuning_params["hierarchy"] == 0:
                tuning_params["hierarchy"] = "NONE"
            if tuning_params["transmission-mode"] == "reserved":
                tuning_params["transmission-mode"] = "AUTO"
            dvbsrc = self.pipeline.get_by_name("dvbsrc")
            log.debug('check', 'Frequency: %s', tuning_params["frequency"])
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
            dvbsrc.set_property("modulation", str(modulation))
        elif self.adaptertype == "DVB-S":
            if (tuning_params["inner-fec"] == "reserved" or
                tuning_params["inner-fec"] == "none"):
                tuning_params["inner-fec"] = "NONE"
            dvbsrc = self.pipeline.get_by_name("dvbsrc")
            dvbsrc.set_property("frequency", tuning_params["frequency"])
            dvbsrc.set_property("polarity", tuning_params["polarization"][0])
            dvbsrc.set_property("symbol-rate", tuning_params["symbol-rate"])
            dvbsrc.set_property("code-rate-hp", tuning_params["inner-fec"])
        elif self.adaptertype == "DVB-C":
            if (tuning_params["inner-fec"] == "reserved" or
                tuning_params["inner-fec"] == "none"):
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
        log.debug('check', 'Scanning complete')
        result = messages.Result()
        log.debug('check', 'Channels: %r ts: %r',
                  scanner.channels, scanner.transport_streams)
        result.succeed((scanner.channels, scanner.transport_streams))
        d.callback(result)

    scanner = DVBScanner(adapter=adapterNumber,
        scanning_complete_cb=scanningComplete)
    scanner.adaptertype = dvbType
    scanner.scan(tuningInfo)
    return d


def checkDVBVideo(p, mid='check-dvb-video'):
    """
    @rtype: L{twisted.internet.defer.Deferred}
    """
    result = messages.Result()

    def get_dvb_video_params(element):
        pad = element.get_pad('src')

        if pad.get_negotiated_caps() == None:
            raise errors.GStreamerError('Pipeline failed to negotiate?')

        caps = pad.get_negotiated_caps()
        s = caps[0]
        w = s['width']
        h = s['height']
        par = s['pixel-aspect-ratio']
        fr = s['framerate']
        result = dict(width=w, height=h, par=(par.num, par.denom),
                      framerate=(fr.num, fr.denom))

        log.debug('check', 'returning dict %r' % result)
        return result


    if p.get('dvb_type') == "T":
        pipeline = ("dvbsrc modulation=\"QAM %(modulation)d\" "
                    "trans-mode=%(trans_mode)s bandwidth=%(bandwidth)d "
                    "code-rate-lp=%(code_rate_lp)s "
                    "code-rate-hp=%(code_rate_hp)s "
                    "guard=%(guard)d hierarchy=%(hierarchy)d ") % p
    elif p.get('dvb_type') == "S":
        pipeline = ("dvbsrc polarity=%(polarity)s symbol-rate=%(symbol_rate)s "
                    "diseqc-source=%(sat)d ") % p
        if p.get('code-rate-hp'):
            pipeline += " code-rate-hp=%s" % p.get('code_rate_hp')
    elif p.get('dvb_type') == "C":
        pipeline = ("dvbsrc modulation=\"QAM %(modulation)d\" "
                    "code-rate-hp=%(code_rate_hp)s ") % p

    if p.get('dvb_type') in ["S", "T", "C"]:
        pipeline += ("frequency=%d adapter=%d frontend=%d " %
                     (p.get('frequency'), p.get('adapter'), p.get('frontend')))


    pipeline += ("! mpegtsdemux program-number=%d "
                 "! mpegvideoparse name=parser ! fakesink" %
                 p.get('program_number'))

    log.debug('check', 'Using pipeline: %s', pipeline)

    d = do_element_check(pipeline, 'parser', get_dvb_video_params)
    d.addCallback(check.callbackResult, result)
    return d
