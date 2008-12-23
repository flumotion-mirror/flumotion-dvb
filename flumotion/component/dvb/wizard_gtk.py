# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2008 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

import gobject
from kiwi.ui.objectlist import Column, ObjectList
from twisted.internet import reactor
from zope.interface import implements

from flumotion.admin.assistant.interfaces import IProducerPlugin
from flumotion.admin.assistant.models import VideoProducer, AudioProducer, \
     VideoConverter, AudioEncoder, VideoEncoder
from flumotion.common import messages
from flumotion.common.i18n import gettexter, N_
from flumotion.ui.wizard import WizardStep
from flumotion.admin.gtk.basesteps import VideoProducerStep

T_ = gettexter('flumotion')
_ = gettext.gettext


class DVBChannel:

    def __init__(self, sid, chandata):
        self.service_id = sid
        self.name = chandata.get('name', 'Unknown')
        self._chandata = chandata

    def getTransportStreamId(self):
        return self._chandata["transport-stream-id"]


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

    # Component

    def getFeederName(self, component):
        if isinstance(component, AudioEncoder):
            return 'audio'
        elif isinstance(component, (VideoEncoder, VideoConverter)):
            return 'video'
        # Disker should be linked to mpegts feeder
        else:
            raise AssertionError

    # Public API

    def setTuningInformation(self, tsid):
        # Should qualify that the tsid exists
        # Not sure what we should do if it does not!
        if not tsid in self.transportStreams:
            print "We are in deep shit because we do not have %d" % tsid
            for ts_id in self.transportStreams:
                print "However we do have: %d" % ts_id
        ts = self.transportStreams[tsid]
        self.properties.frequency = ts["frequency"]
        dvbType = self.properties.dvb_type
        if dvbType == 'T':
            self.properties.bandwidth = ts["bandwidth"]
            self.properties.guard = ts["guard-interval"]
            self.properties.hierarchy = ts["hierarchy"]
            self.properties.trans_mode = \
                    self._parseTransmissionMode(ts["transmission-mode"])
            self.properties.code_rate_hp = self._parseCodeRate(
                ts["code-rate-hp"])
            self.properties.code_rate_lp = self._parseCodeRate(
                ts["code-rate-lp"])
        elif dvbType == "S":
            self.properties.polarity = ts["polarization"]
        elif dvbType == "C":
            self.properties.inversion = "AUTO"

        if dvbType != 'S':
            self.properties.modulation = self._parseModulation(
                ts["constellation"])

        if dvbType != 'T':
            self.properties.symbol_rate = ts["symbol-rate"]
            self.properties.code_rate_hp = self._parseCodeRate(ts["inner-fec"])

    # Private

    def _parseModulation(self, constellation):
        if constellation.startswith("QAM"):
            modulation = int(constellation[3:])
        elif constellation == "reserved":
            modulation = 64
        else:
            #modulation = ts["constellation"]
            modulation = 64
        return modulation

    def _parseCodeRate(self, codeRate):
        if codeRate == "reserved":
            codeRate = "NONE"
        return codeRate

    def _parseTransmissionMode(self, transmode):
        if transmode == "reserved":
            transmode = "AUTO"
        elif transmode[0] == "2" or transmode[0] == "8":
            transmode = transmode[0]
        return transmode


class DVBAntennaStep(VideoProducerStep):
    name = _('DVB Antenna Selection')
    sidebarName = _('DVB Antenna')
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
        'dvb-antenna.glade')
    section = _('Production')

    def __init__(self, wizard, model):
        # evil hack to remove need to duplicate getNext code in VideoProducer
        # for last step in producer
        model.firstStep = self
        super(DVBAntennaStep, self).__init__(wizard, model)

    # WizardStep

    def workerChanged(self, worker):
        self.model.worker = worker
        self._runChecks()

    def getNext(self):
        selectedAdapter = self.adapter.get_selected()
        self.model.adapterNumber = selectedAdapter[1]
        self.model.properties.adapter = selectedAdapter[1]
        self.model.dvbtype = selectedAdapter[0]
        self.model.antenna = self.antenna.get_selected()
        self.model.properties.dvb_type = self.model.dvbtype[-1]
        return DVBProbeChannelsStep(self.wizard, self.model)

    # Private

    def _runChecks(self):
        msg = messages.Info(T_(N_('Checking for DVB adapters...')),
            id='dvb-adapter-check')
        self.wizard.add_msg(msg)

        def adapterListReceived(adapters):
            locationsd = self.runInWorker('flumotion.component.dvb.dvbchecks',
                'getAntennaeLocations')
            self._adapters = adapters
            locationsd.addCallback(locationsReceived)
            return locationsd

        def locationsReceived(locations):
            self.wizard.clear_msg('dvb-adapter-check')
            self._terrestrialLocations = locations["DVB-T"]
            self._satelliteLocations = locations["DVB-S"]
            self.adapter.prefill([(a[2], a) for a in self._adapters])

        d = self.runInWorker('flumotion.component.dvb.dvbchecks',
            'getListOfAdaptersWithTypes')
        d.addCallback(adapterListReceived)

        return d

    def _updateCountries(self):
        # FIXME: add specific code for dvb-s, dvb-c, atsc etc.
        # eg hide country
        adapter = self.adapter.get_selected()
        if adapter is None:
            return
        dvbType = adapter[0]
        print "Adapter type: %r" % (adapter, )
        if dvbType == 'DVB-T':
            self.countrylabel.show()
            self.country.show()
            # This code will break in python 3, need to do an explicit copy
            countries = self._terrestrialLocations.keys()
            countries.sort()
            self.country.prefill(countries)
        elif dvbType == 'DVB-S':
            self.countrylabel.hide()
            self.country.hide()
            self._updateAntenna()

    def _updateAntenna(self):
        adapter = self.adapter.get_selected()
        if adapter is None:
            return
        dvbType = adapter[0]
        if dvbType == 'DVB-T':
            country = self.country.get_selected()
            if country is None:
                return
            antennae = self._terrestrialLocations[country]
            antennae.sort()
            self.antenna.prefill(antennae)
        elif dvbType == 'DVB-S':
            antennae = self._satelliteLocations
            antennae.sort()
            self.antenna.prefill(antennae)

    # Callbacks

    def on_adapter__changed(self, adaptercombo):
        self._updateCountries()

    def on_country__changed(self, countrycombo):
        self._updateAntenna()


class DVBProbeChannelsStep(WizardStep):
    name = _("Probing DVB Channels")
    sidebarName = _("Probing DVB")
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
        'dvb-probe-channels.glade')
    section = _('Production')

    def __init__(self, wizard, model):
        self.model = model
        self._frequenciesToScan = []
        self._frequenciesAlreadyScanned = []
        self._pulseCallLaterId = -1
        super(DVBProbeChannelsStep, self).__init__(wizard)

    # WizardStep

    def setup(self):
        self.model.channels = {}
        self.model.transportStreams = {}

        self.progress.set_pulse_step(0.05)
        self._runChecks()

    def getNext(self):
        return DVBSelectChannelStep(self.wizard, self.model)

    # Private API

    def _runChecks(self):
        # FIXME: change label to say what we are doing
        print "Worker %s" % self.model.worker
        print "Adapter %r" % (self.model.adapterNumber, )
        print "Antenna %r" % (self.model.antenna, )
        d = self.wizard.runInWorker(self.model.worker,
            "flumotion.component.dvb.dvbchecks", "getInitialTuning",
            self.model.dvbtype, self.model.antenna)

        def receivedInitialTuningData(initialTuning):
            self._startPulseProgressBar()
            print "Initial tuning: %r" % (initialTuning, )
            # now we need to do the scanning
            for freq in initialTuning:
                self._frequenciesToScan.append(freq)
            return self._scan()
        d.addCallback(receivedInitialTuningData)
        return d

    def _pulseProgressBar(self):
        self.progress.pulse()
        return True

    def _startPulseProgressBar(self):
        self._pulseCallLaterId = gobject.timeout_add(
            100, self._pulseProgressBar)

    def _finishedScanning(self):
        if self._pulseCallLaterId != -1:
            gobject.source_remove(self._pulseCallLaterId)
            self._pulseCallLaterId = -1

        self.progress.set_fraction(0)
        if not self.model.channels:
            self.wizard.blockNext(True)
            self.label.set_text(_("No channels found"))

    def _scan(self):
        if not self._frequenciesToScan:
            self._finishedScanning()
            return
        f = None
        while True:
            if not self._frequenciesToScan:
                break
            f = self._frequenciesToScan.pop()
            key = f["frequency"], f.get("polarization")
            if not key in self._frequenciesAlreadyScanned:
                break
            f = None
        if not f:
            self._finishedScanning()
            return
        print "..Frequencies scanned already: %r" % (
                    self._frequenciesAlreadyScanned, )
        print "Scanning %r" % (f, )
        self.statuslabel.set_text("Scanning frequency %s" % (f["frequency"], ))
        d = self.wizard.runInWorker(
            self.worker,
            "flumotion.component.dvb.dvbchecks",
            "scan", self.model.adapterNumber, self.model.dvbtype, f)

        def frequencyScanned((channels, moreFrequencies)):
            print "Frequency scanned"
            # add frequency just scanned to frequencies_already_scanned
            key = f["frequency"], f.get('polarization')
            self._frequenciesAlreadyScanned.append(key)
            for tsid in moreFrequencies:
                tuningparams = moreFrequencies[tsid]
                self.model.transportStreams[tsid] = tuningparams
                key = tuningparams["frequency"], \
                    tuningparams.get('polarization')
                if key in self._frequenciesAlreadyScanned:
                    continue
                print "Delivery: %r" % (tuningparams, )
                print "Key: %r" % (key, )
                print "Frequencies scanned already: %r" % (
                    self._frequenciesAlreadyScanned, )
                self._frequenciesToScan.append(tuningparams)

            for sid, channel in channels.items():
                chanData = self.model.channels.setdefault(sid, {})
                chanData.update(channel)
                print "Channel %r added with data: %r" % (sid, chanData)
                # let us fill in missing tsid tuning data for any channels
                # that came in with this scan

                # basically, if we have the tsid for the channel
                # get the tsid of this channel
                # see if it is already filled in self.model.transportStreams
                # if not, fill it in
                if "transport-stream-id" in chanData:
                    tsid = chanData["transport-stream-id"]
                    if not tsid in self.model.transportStreams:
                        print "FILLING IN TSID %d with %r" % (tsid, f)
                        self.model.transportStreams[tsid] = f

            print ".Frequencies scanned already: %r" % (
                    self._frequenciesAlreadyScanned, )

            return self._scan()
        d.addCallback(frequencyScanned)


class DVBSelectChannelStep(WizardStep):
    name = _("Choose Channel")
    sidebarName = _("Choose Channel")
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
        'dvb-select-channel.glade')
    section = _('Production')

    def __init__(self, wizard, model):
        self.model = model
        super(DVBSelectChannelStep, self).__init__(wizard)

    # WizardStep

    def setup(self):
        self.channels = ObjectList([
            Column('service_id', title='Program number'),
            Column('name', title='Channel name', sorted=True)])
        for sid, chandata in self.model.channels.items():
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

    # WizardStep

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
