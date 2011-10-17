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


import gettext
import os

import gobject
from kiwi.ui.objectlist import Column
from zope.interface import implements

from flumotion.admin.assistant.interfaces import IProducerPlugin
from flumotion.admin.assistant.models import VideoProducer, AudioProducer, \
     VideoConverter, AudioEncoder, VideoEncoder
from flumotion.admin.gtk.workerstep import WorkerWizardStep
from flumotion.common import messages, errors
from flumotion.common.i18n import gettexter, N_
from flumotion.ui.wizard import WizardStep


T_ = gettexter('flumotion')
_ = gettext.gettext
D_ = gettext.dgettext

#FIXME: Fill all the possible language codes
LANGUAGES_STR = \
        {'alb': D_('iso_639_3', 'Albanian'),
         'ara': D_('iso_639_3', 'Arabic'),
         'arm': D_('iso_639_3', 'Armenian'),
         'ass': D_('iso_639_3', 'Neo-Aramaic, Assyrian'),
#		 (D_('iso_639_3', 'Bosnian'), 'bs'),
#		 (_('Brasilian Portuguese'), 'pb'),
#		 (D_('iso_639_3', 'Bulgarian'), 'bg'),
         'cat': D_('iso_639_3', 'Catalan'),
#		 (D_('iso_639_3', 'Chinese'), 'zh'),
#		 (D_('iso_639_3', 'Croatian'), 'hr'),
#		 (D_('iso_639_3', 'Czech'), 'cs'),
#		 (D_('iso_639_3', 'Danish'), 'da'),
#		 (D_('iso_639_3', 'Dutch'), 'nl'),
#		 (D_('iso_639_3', 'English'), 'en'),
#		 (D_('iso_639_3', 'Esperanto'), 'eo'),
#		 (D_('iso_639_3', 'Estonian'), 'et'),
#		 (D_('iso_639_3', 'Finnish'), 'fi'),
#		 (D_('iso_639_3', 'French'), 'fr'),
#		 (D_('iso_639_3', 'Galician'), 'gl'),
#		 (D_('iso_639_3', 'Georgian'), 'ka'),
#		 (D_('iso_639_3', 'German'), 'de'),
#		 (D_('iso_639_3', 'Greek, Modern (1453-)'), 'el'),
#		 (D_('iso_639_3', 'Hebrew'), 'he'),
#		 (D_('iso_639_3', 'Hindi'), 'hi'),
#		 (D_('iso_639_3', 'Hungarian'), 'hu'),
#		 (D_('iso_639_3', 'Icelandic'), 'is'),
#		 (D_('iso_639_3', 'Indonesian'), 'id'),
#		 (D_('iso_639_3', 'Italian'), 'it'),
#		 (D_('iso_639_3', 'Japanese'), 'ja'),
#		 (D_('iso_639_3', 'Kazakh'), 'kk'),
#		 (D_('iso_639_3', 'Korean'), 'ko'),
#		 (D_('iso_639_3', 'Latvian'), 'lv'),
#		 (D_('iso_639_3', 'Lithuanian'), 'lt'),
#		 (D_('iso_639_3', 'Luxembourgish'), 'lb'),
#		 (D_('iso_639_3', 'Macedonian'), 'mk'),
#		 (D_('iso_639_3', 'Malay (macrolanguage)'), 'ms'),
#		 (D_('iso_639_3', 'Norwegian'), 'no'),
#		 (D_('iso_639_3', 'Occitan (post 1500)'), 'oc'),
#		 (D_('iso_639_3', 'Persian'), 'fa'),
#		 (D_('iso_639_3', 'Polish'), 'pl'),
#		 (D_('iso_639_3', 'Portuguese'), 'pt'),
#		 (D_('iso_639_3', 'Romanian'), 'ro'),
#		 (D_('iso_639_3', 'Russian'), 'ru'),
#		 (D_('iso_639_3', 'Serbian'), 'sr'),
#		 (D_('iso_639_3', 'Slovak'), 'sk'),
#		 (D_('iso_639_3', 'Slovenian'), 'sl'),
         'spa': D_('iso_639_3', 'Spanish'),
#		 (D_('iso_639_3', 'Swedish'), 'sv'),
#		 (D_('iso_639_3', 'Thai'), 'th'),
#		 (D_('iso_639_3', 'Turkish'), 'tr'),
#		 (D_('iso_639_3', 'Ukrainian'), 'uk'),
#		 (D_('iso_639_3', 'Vietnamese'), 'vi'),
         'v.o': _('Original Version'),
         'a.d': _('Audio description'), }


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
        self.properties.width = 360
        self.properties.height = 288
        self.properties.framerate = 12.5

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


class DVBProbeChannelsStep(WorkerWizardStep):
    name = _("Probing DVB Channels")
    sidebarName = _("Probing DVB")
    title = _("Probing DVB Channels")
    section = _('Production')

    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'wizard.glade')
    toplevel_name = "dvbprobe_window"

    def __init__(self, wizard, model):
        WorkerWizardStep.__init__(self, wizard)
        model.firstStep = self
        self.model = model
        self._shouldScan = False

        self.channels.connect('selection-changed',
                              self.on_channels__selection_changed)

    def on_channels__selection_changed(self, chan_list, channel):
        videoCType = \
                self.wizard.getStep('Production').getComponentType('video')
        chan = self.model.channels[channel.service_id]

        self.wizard.blockNext(False)
        self.wizard.clear_msg('dvb-stream-check')

        if videoCType == self.model.componentType:
            if not ('video-streams' in chan and chan['video-streams']):
                self.wizard.blockNext(True)
                msg = messages.Info(
                    T_(N_('The selected stream doesn\'t contain '
                          'a suitable video feed.')), mid='dvb-stream-check')
                self.wizard.add_msg(msg)

    def startScanning(self):
        self.model.channels = {}
        self.model.transportStreams = {}

        self.channels.clear()

        self._frequenciesToScan = []
        self._frequenciesAlreadyScanned = []
        self._pulseCallLaterId = -1

        self._shouldScan = True
        self.stop_scan.set_sensitive(True)
        self.start_scan.set_sensitive(False)
        self._runNewScan()

    # WorkerWizardStep

    def workerChanged(self, worker):
        self.model.worker = worker
        self._runChecks()

    # WizardStep

    def setup(self):
        self.progress.set_pulse_step(0.05)
        self.channels.set_columns([
            Column('service_id', title='Program number'),
            Column('name', title='Channel name', sorted=True)])

        self.adapter.data_type = object
        self.country.data_type = object

    def getNext(self):
        channel = self.channels.get_selected()
        self.model.channel = channel
        self.model.properties.program_number = channel.service_id
        tsid = channel.getTransportStreamId()
        self.model.setTuningInformation(tsid)

        return DVBConfig(self.wizard, self.model)

    # Private API

    def _runChecks(self):
        self.wizard.clear_all_msg()
        msg = messages.Info(T_(N_('Checking for DVB elements...')),
                            mid='dvb-elements-check')
        self.wizard.add_msg(msg)

        def gotElements(elements):
            self.wizard.clear_msg('dvb-elements-check')
            self.stop_scan.set_sensitive(False)
            self.start_scan.set_sensitive(len(elements) == 0)

            if elements:
                return

            msg = messages.Info(T_(N_('Checking for DVB adapters...')),
                                mid='dvb-adapter-check')
            self.wizard.add_msg(msg)

            d = self.runInWorker('flumotion.worker.checks.dvb',
                'getListOfAdaptersWithTypes')
            d.addCallback(adapterListReceived)
            return d

        def adapterListReceived(adapters):
            self._adapters = adapters
            if self._adapters:
                self.stop_scan.set_sensitive(False)
                self.start_scan.set_sensitive(True)

                d = self.runInWorker('flumotion.worker.checks.dvb',
                    'getAntennaeLocations')
                d.addCallback(locationsReceived)
                return d

            msg = messages.Error(T_(N_('No adapter found.')),
                        mid='dvb-adapter-check')
            self.wizard.add_msg(msg)

            self.stop_scan.set_sensitive(False)
            self.start_scan.set_sensitive(False)
            self.wizard.blockNext(True)

        def locationsReceived(locations):
            self.wizard.clear_msg('dvb-adapter-check')
            self._terrestrialLocations = locations["DVB-T"]
            self._satelliteLocations = locations["DVB-S"]
            self.adapter.prefill([(a[2], a) for a in self._adapters])

        d = self.wizard.requireElements(self.model.worker, 'dvbsrc',
                                        'mpegtsparse', 'mpeg2dec', 'mad',
                                        'flutsdemux', 'mpegvideoparse')
        d.addCallback(gotElements)
        return d

    def _runNewScan(self):

        def receivedInitialTuningData(initialTuning):
            self._startPulseProgressBar()
            self.debug("Initial tuning: %r", initialTuning)
            # now we need to do the scanning
            for freq in initialTuning:
                self._frequenciesToScan.append(freq)
            return self._scan()

        d = self.wizard.runInWorker(self.model.worker,
                "flumotion.worker.checks.dvb",
                "getInitialTuning", self.model.dvbtype, self.model.antenna)
        d.addCallback(receivedInitialTuningData)
        return d

    def _updateCountries(self):
        # FIXME: add specific code for dvb-s, dvb-c, atsc etc.
        # eg hide country
        adapter = self.adapter.get_selected()
        if adapter is None:
            return
        dvbType = adapter[0]
        self.debug("Adapter type: %r", adapter)
        if dvbType == 'DVB-T':
            self.country.show()
            # This code will break in python 3, need to do an explicit copy
            countries = self._terrestrialLocations.keys()
            countries.sort()
            self.country.prefill(countries)
        elif dvbType == 'DVB-S':
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

    def _pulseProgressBar(self):
        self.progress.pulse()
        return True

    def _startPulseProgressBar(self):
        self._pulseCallLaterId = \
            gobject.timeout_add(100, self._pulseProgressBar)

    def _finishedScanning(self):
        self._shouldScan = False
        self.stop_scan.set_sensitive(False)
        self.start_scan.set_sensitive(True)
        self.adapter.set_sensitive(True)
        self.country.set_sensitive(True)
        self.antenna.set_sensitive(True)

        if self._pulseCallLaterId != -1:
            gobject.source_remove(self._pulseCallLaterId)
            self._pulseCallLaterId = -1
            self.progress.set_text(_("Scan finished"))

        self.progress.set_fraction(0)
        if not self.model.channels:
            self.wizard.blockNext(True)
            self.progress.set_text(_("No channels found"))

    def _scan(self):
        if not self._frequenciesToScan or not self._shouldScan:
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

        self.progress.set_text("Scanning %s Hz" % (f["frequency"], ))

        def frequencyScanned((channels, moreFrequencies)):
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
                self._frequenciesToScan.append(tuningparams)

                self.debug("Delivery: %r\nKey: %r\n"
                           "Frequencies scanned already: %r",
                           tuningparams, key, self._frequenciesAlreadyScanned)

            for sid, channel in channels.items():
                if sid == 0:
                    continue

                chanData = self.model.channels.setdefault(sid, {})
                chanData.update(channel)
                self.channels.append(DVBChannel(sid, channel))

                self.debug("Channel %r added with data: %r", sid, chanData)
                # let us fill in missing tsid tuning data for any channels
                # that came in with this scan

                # basically, if we have the tsid for the channel
                # get the tsid of this channel
                # see if it is already filled in self.model.transportStreams
                # if not, fill it in
                if "transport-stream-id" in chanData:
                    tsid = chanData["transport-stream-id"]
                    if not tsid in self.model.transportStreams:
                        #self.debug("FILLING IN TSID %d with %r", tsid, f)
                        self.model.transportStreams[tsid] = f

            return self._scan()

        def frequencyScanError(failure):
            failure.trap(errors.RemoteRunError)
            #self.error('ERROR SCANNING FREQUENCY %s', f)
            return self._scan()

        d = self.wizard.runInWorker(self.model.worker,
                "flumotion.worker.checks.dvb", "scan",
                self.model.adapterNumber, self.model.dvbtype, f)
        d.addCallback(frequencyScanned)
        d.addErrback(frequencyScanError)
        return d

    # Callbacks

    def on_adapter__changed(self, adaptercombo):
        #self.debug('adapter, updated')
        self._updateCountries()

    def on_country__changed(self, countrycombo):
        self._updateAntenna()

    def on_channels_row_activated(self, channels, chan):
        #self.debug("%r, %r", channels, chan)
        pass

    def on_start_scan_clicked(self, button):
        if self._shouldScan:
            return

        self.adapter.set_sensitive(False)
        self.country.set_sensitive(False)
        self.antenna.set_sensitive(False)

        selectedAdapter = self.adapter.get_selected()
        self.model.adapterNumber = selectedAdapter[1]
        self.model.properties.adapter = selectedAdapter[1]
        self.model.dvbtype = selectedAdapter[0]
        self.model.antenna = self.antenna.get_selected()
        self.model.properties.dvb_type = self.model.dvbtype[-1]
        self.startScanning()

    def on_stop_scan_clicked(self, button):
        self._shouldScan = False


class DVBConfig(WizardStep): #VideoProducerStep, AudioProducerStep):
    name = _("DVB A/V Configuration")
    title = _("DVB A/V Configuration")
    sidebarName = _("DVB A/V")
    section = _('Production')

    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'wizard.glade')
    toplevel_name = "dvbconfig_window"

    docSection = 'help-configuration-assistant-producer-video-dvb'
    docAnchor = ''
    docVersion = 'local'

    def __init__(self, wizard, model):
        self.model = model
        WizardStep.__init__(self, wizard)

    # WizardStep

    def setup(self):
        self.video_frame.hide()
        self.audio_frame.hide()

        chan = self.model.channels[self.model.properties.program_number]
        # Audio-only chanel, maybe we shouldn't let the wizard get to here if
        # in production step DVB audio/video is selected
        if not 'video-streams' in chan or not chan['video-streams']:
            self.model.properties.has_video = False

        audioType = self.wizard.getStep('Production').getComponentType('audio')
        videoType = self.wizard.getStep('Production').getComponentType('video')

        if (self.model.properties.has_video and
            videoType == self.model.componentType):
            # FIXME: Try to figure out the video size and put it here.
            self.video_frame.show()

            self.framerate.data_type = float
            self.width.data_type = int
            self.height.data_type = int

            self._proxy = self.add_proxy(self.model.properties,
                                         ['width', 'height', 'framerate'])
            self.wizard.getStep('Production').setVideoProducer(self.model)

        if ('audio-streams' in chan and chan['audio-streams'] and
            audioType == self.model.componentType):
            self.model.properties.audio_pid = None
            self.audio_frame.show()

            self.audio_pid.data_type = int

            for stream in chan['audio-streams']:
                self.audio_pid.append_item(
                    LANGUAGES_STR.get(stream[0], stream[0]), stream[1])

            self.add_proxy(self.model.properties, ['audio-pid'])
            self.audio_pid.select_item_by_position(0)
            self.wizard.getStep('Production').setAudioProducer(self.model)

        return self._runChecks()

    def _runChecks(self):
        self.wizard.clear_all_msg()
        msg = messages.Info(T_(N_('Checking for DVB elements...')),
                            mid='dvb-check')
        self.wizard.add_msg(msg)

        p = self.model.getProperties()
        props = dict(dvb_type=p.get('dvb-type'),
                     modulation=p.get('modulation'),
                     trans_mode=p.get('trans-mode'),
                     bandwidth=p.get('bandwidth'),
                     code_rate_lp=p.get('code-rate-lp'),
                     code_rate_hp=p.get('code-rate-hp'),
                     guard=p.get('guard'),
                     hierarchy=p.get('hierarchy'),
                     polarity=p.get('polarity'),
                     symbol_rate=p.get('symbol-rate'),
                     satellite_number=p.get('satellite-number'),
                     frequency=p.get('frequency'),
                     adapter=p.get('adapter'),
                     frontend=p.get('frontend'),
                     program_number=p.get('program-number'))

        trans_mode = p.get('trans-mode')
        if trans_mode == 2 or trans_mode == 8:
            props['trans_mode'] = "%sk" % trans_mode
        else:
            props['trans_mode'] = "AUTO"

        def gotCaps(caps):
            self.model.properties.width = caps['width']
            self.model.properties.height = caps['height']
            self.model.properties.framerate = \
                    float(caps['framerate'][0])/float(caps['framerate'][1])
            self._proxy.update_many(['width', 'height', 'framerate'])

        d = self.wizard.runInWorker(self.model.worker,
                                    'flumotion.worker.checks.dvb',
                                    'checkDVBVideo', props)
        d.addCallback(gotCaps)
        return d

    def getNext(self):
        audioType = \
                self.wizard.getStep('Production').getComponentType('audio')
        if audioType != self.model.componentType:
            return self.wizard.getStep('Production').getAudioStep()

        return None


class DVBWizardPlugin(object):
    implements(IProducerPlugin)

    def __init__(self, wizard):
        self.wizard = wizard

    def getProductionStep(self, producer_type):
        self.model = DVBProducer()
        self.model.properties.has_video = producer_type == 'video'
        return DVBProbeChannelsStep(self.wizard, self.model)
