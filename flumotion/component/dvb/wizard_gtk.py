# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

import gettext
import os

from kiwi.ui.objectlist import Column, ObjectList
from zope.interface import implements

from flumotion.common import messages
from flumotion.common.i18n import gettexter, N_
from flumotion.ui.wizard import WizardStep
from flumotion.wizard.interfaces import IProducerPlugin
from flumotion.wizard.models import VideoProducer, AudioProducer, \
     VideoConverter, AudioEncoder, VideoEncoder
from flumotion.wizard.basesteps import VideoProducerStep

T_ = gettexter('flumotion')
_ = gettext.gettext


class DVBProducer(AudioProducer, VideoProducer):
    componentType = 'dvb-producer'
    def __init__(self):
        super(DVBProducer, self).__init__()

        self.properties.adapter = 0
        self.properties.frontend = 0
        # FIXME: find the elements that we can use, not hardcode
        self.properties.video_decoder = 'mpeg2dec'
        self.properties.audio_decoder = 'mad'
        self.properties.deinterlacer = 'ffdeinterlace'
        self.properties.width = 360
        self.properties.height = 288
        self.properties.framerate = 12.5
        self.properties.has_video = True

    def getFeederName(self, component):
        if isinstance(component, AudioEncoder):
            return 'audio'
        elif isinstance(component, (VideoEncoder, VideoConverter)):
            return 'video'
        # Disker should be linked to mpegts feeder
        else:
            raise AssertionError

    def setTuningInformation(self, tsid):
        ts = self.transportStreams[tsid]
        self.properties.frequency = ts["frequency"]
        if self.properties.dvb_type == 'T':
            modulation=""
            if ts["constellation"].startswith("QAM"):
                modulation = int(ts["constellation"][3:])
            elif ts["constellation"] == "reserved":
                modulation = 64
            else:
                #modulation = ts["constellation"]
                modulation = 64
            self.properties.modulation = modulation
            for param in ["code-rate-hp", "code-rate-lp"]:
                if ts[param] == "reserved":
                    ts[param] = "NONE"
            self.properties.bandwidth = ts["bandwidth"]
            self.properties.code_rate_hp = ts["code-rate-hp"]
            self.properties.code_rate_lp = ts["code-rate-lp"]
            self.properties.trans_mode = int(ts["transmission-mode"][0]) 
            self.properties.guard = ts["guard-interval"]
            self.properties.hierarchy = ts["hierarchy"]
            self.properties.modulation = modulation
        elif self.adaptertype == "DVB-S":
            if ts["inner-fec"] == "reserved" or \
               ts["inner-fec"] == "none":
                ts["inner-fec"] = "NONE"
            self.properties.polarity = ts["polarization"]
            self.properties.symbol_rate = ts["symbol-rate"]
            self.properties.code_rate_hp = ts["inner-fec"]
        elif self.adaptertype == "DVB-C":
            if ts["inner-fec"] == "reserved" or \
               ts["inner-fec"] == "none":
                ts["inner-fec"] = "NONE"

            self.properties.inversion = "AUTO"
            self.properties.symbol_rate = ts["symbol-rate"]
            self.properties.code_rate_hp = ts["inner-fec"]
            modulation=""
            if ts["modulation"].startswith("QAM"):
                modulation="QAM %s" % ts["modulation"][3:]
            elif tuning_params["modulation"] == "reserved":
                modulation = "QAM 64"
            else:
                modulation = ts["modulation"]
            self.properties.modulation = modulation

class DVBAntennaStep(VideoProducerStep):
    name = _('DVB Antenna Selection')
    sidebarName = _('DVB Antenna')
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
        'dvb-antenna.glade')
    section = _('Production')


    def __init__(self, wizard, model):
        super(DVBAntennaStep, self).__init__(wizard, model)
        # evil hack to remove need to duplicate getNext code in VideoProducer
        # for last step in producer
        model.firstStep = self

    def workerChanged(self, worker):
        self.model.worker = worker
        self._runChecks()

    def _runChecks(self):
        msg = messages.Info(T_(N_('Checking for DVB adapters...')),
            id='dvb-adapter-check')
        self.wizard.add_msg(msg)

        d = self.runInWorker('flumotion.component.dvb.dvbchecks', 
            'getListOfAdaptersWithTypes')
        def adapterListReceived(adapters):
            locationsd = self.runInWorker('flumotion.component.dvb.dvbchecks',
                'getTerrestrialLocations')
            self._adapters = adapters
            locationsd.addCallback(locationsReceived)
            return locationsd
        def locationsReceived(locations):
            self.wizard.clear_msg('dvb-adapter-check')
            self._terrestrialLocations = locations
            self.adapter.prefill([(a[2], a) for a in self._adapters])
        d.addCallback(adapterListReceived)
        return d 
        
    def on_adapter__changed(self, adaptercombo):
        # FIXME: add specific code for dvb-s, dvb-c, atsc etc.
        # eg hide country
        # FIXME: get friendly country names
        adapter = adaptercombo.get_selected()
        if adapter is None:
            return
        dvbType = adapter[0]
        print "Adapter type: %r" % (adapter,)
        if dvbType == 'DVB-T':
            # This code will break in python 3, need to do an explicit copy
            countries = self._terrestrialLocations.keys()
            countries.sort()
            self.country.prefill(countries)

    def on_country__changed(self, countrycombo):
        # FIXME: transform camel case titles to have spaces
        country = countrycombo.get_selected()
        if country is None:
            return
        antennae = self._terrestrialLocations[country]
        antennae.sort()
        self.antenna.prefill(antennae)

    # WizardStep
    def getNext(self):
        selectedAdapter = self.adapter.get_selected()
        self.model.adapterNumber = selectedAdapter[1]
        self.model.properties.adapter = selectedAdapter[1]
        self.model.dvbtype = selectedAdapter[0]
        self.model.antenna = self.antenna.get_selected()
        self.model.properties.dvb_type = self.model.dvbtype[-1]
        return DVBProbeChannelsStep(self.wizard, self.model)


class DVBProbeChannelsStep(WizardStep):
    name = _("Probing DVB Channels")
    sidebarName = _("Probing DVB")
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
        'dvb-probe-channels.glade')
    section = _('Production')
    
    def __init__(self, wizard, model):
        self.model = model
        super(DVBProbeChannelsStep, self).__init__(wizard)
        self._frequencies_to_scan = []
        self._frequencies_already_scanned = []
        self.model.channels = {}
        self.model.transportStreams = {}
        self._runChecks()

    def _runChecks(self):
        # FIXME: pulse regularly, change label to say what we are doing
        print "Worker %s" % self.model.worker
        print "Adapter %r" % (self.model.adapterNumber,)
        print "Antenna %r" % (self.model.antenna,)
        d = self.wizard.runInWorker(self.model.worker, 
            "flumotion.component.dvb.dvbchecks", "getInitialTuning", 
            self.model.dvbtype, self.model.antenna)
        def receivedInitialTuningData(initialTuning):
            self.progress.pulse()
            print "Initial tuning: %r" % (initialTuning,)
            # now we need to do the scanning
            for freq in initialTuning:
                self._frequencies_to_scan.append(freq)
            return self._scan()
        d.addCallback(receivedInitialTuningData)
        return d

    def _scan(self):
        if not self._frequencies_to_scan:
            print "Finished scanning"
            return
        f = None
        while True:
            if not self._frequencies_to_scan:
                break
            f = self._frequencies_to_scan.pop()
            key = f["frequency"], f.get("polarization")
            if not key in self._frequencies_already_scanned:
                break
            f = None
        if not f:
            print "Finished scanning"
            return
        print "..Frequencies scanned already: %r" % (
                    self._frequencies_already_scanned,)
        print "Scanning %r" % (f,)
        d = self.wizard.runInWorker(self.worker, "flumotion.component.dvb.dvbchecks",
            "scan", self.model.adapterNumber, self.model.dvbtype, f)
        def frequencyScanned((channels, moreFrequencies)):
            print "Frequency scanned"
            for sid, channel in channels.items():
                chanData = self.model.channels.setdefault(sid, {})
                chanData.update(channel)
                print "Channel %r added with data: %r" % (sid,chanData)
            # add frequency just scanned to frequencies_already_scanned
            key = f["frequency"], f.get('polarization')
            self._frequencies_already_scanned.append(key)
            for tsid, freq in moreFrequencies.items():
                self.model.transportStreams[tsid] = freq
                key = freq["frequency"], freq.get('polarization')
                if key in self._frequencies_already_scanned:
                    continue
                print "Delivery: %r" % (freq,)
                print "Key: %r" % (key,)
                print "Frequencies scanned already: %r" % (
                    self._frequencies_already_scanned,)
                self._frequencies_to_scan.append(freq)
            print ".Frequencies scanned already: %r" % (
                    self._frequencies_already_scanned,)

            return self._scan()
        d.addCallback(frequencyScanned)
        
    def getNext(self):
        return DVBSelectChannelStep(self.wizard, self.model)

# for kiwi ObjectList
class DVBChannel:
    def __init__(self, sid, chandata):
        self.service_id = sid
        self.name = chandata.get('name', 'Unknown')
        self.chandata = chandata
    
    def getTransportStreamId(self):
        return self.chandata["transport-stream-id"]


class DVBSelectChannelStep(WizardStep):
    name = _("Choose Channel")
    sidebarName = _("Choose Channel")
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
        'dvb-select-channel.glade')
    section = _('Production')

    def __init__(self, wizard, model):
        self.model = model
        super(DVBSelectChannelStep, self).__init__(wizard)

    def setup(self):
        self.channels = ObjectList([
            Column('service_id', title='Program number'), 
            Column('name', title='Channel name', sorted=True)])
        for sid,chandata in self.model.channels.items():
            self.channels.append(DVBChannel(sid, chandata))
        self.main_vbox.add(self.channels)
        self.channels.show()
        self.channels.select(self.channels[0])

    def getNext(self):
        channel = self.channels.get_selected()
        self.model.channel = channel
        self.model.properties.program_number = channel.service_id
        tsid = channel.getTransportStreamId()
        self.model.setTuningInformation(tsid)        
        return DVBVideoConfig(self.wizard, self.model)

class DVBVideoConfig(WizardStep):
    name = _("Video Configuration")
    sidebarName = _("Video Config")
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
        'dvb-video-config.glade')
    section = _('Production')


    def __init__(self, wizard, model):
        self.model = model
        super(DVBVideoConfig, self).__init__(wizard)

    def setup(self):
        self.framerate.data_type = float

        self.add_proxy(self.model.properties,
                       ['width', 'height', 'framerate'])

    def getNext(self):
        return VideoProducerStep.getNext(self.model.firstStep)

class DVBWizardPlugin(object):
    implements(IProducerPlugin)

    def __init__(self, wizard):
        self.wizard = wizard
        self.model = DVBProducer()
    
    def getProductionStep(self, type):
        return DVBAntennaStep(self.wizard, self.model)


