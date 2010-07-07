# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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

import gst
from twisted.internet import defer

from flumotion.common import errors
from flumotion.common.i18n import N_, gettexter
from flumotion.component import feedcomponent
from flumotion.component.effects.volume import volume
from flumotion.component.effects.deinterlace import deinterlace
from flumotion.component.effects.videoscale import videoscale


T_ = gettexter('flumotion')


def get_decode_pipeline_string(props):
    has_video = props.get('has-video', True)
    video_decoder = props.get('video-decoder', 'mpeg2dec')
    audio_decoder = props.get('audio-decoder', 'mad')
    deinterlacer = props.get('deinterlacer', None)
    # we only want to scale if specifically told to in config
    framerate = props.get('framerate', (25, 2))
    fr = "%d/%d" % (framerate[0], framerate[1])
    program_number = props.get('program-number')
    audio_pid = props.get('audio-pid', 0)
    # identity to check for imperfect timestamps also for
    # use to sync to the clock when we use a file
    idsync_template = "identity check-imperfect-timestamp=true silent=true"
    audio_pid_template = ""
    if audio_pid > 0:
        # transport stream demuxer expects this as 4 digit hex
        audio_pid_template = "audio_%04x " % audio_pid
    template = 'flutsdemux name=demux program-number=%(program_number)d' \
        ' demux.%(audiopid)s ! ' \
        ' queue max-size-buffers=0 max-size-time=0' \
        ' ! %(audiodec)s name=audiodecoder ! audiorate' \
        ' ! %(identity)s name=audioid' \
        ' ! audioconvert ! level name=level ! volume name=volume' \
        ' ! tee name=t ! @feeder:audio@' % dict(
            audiopid=audio_pid_template,
            audiodec=audio_decoder,
            identity=idsync_template,
            program_number=program_number)
    if has_video:
        template = ('%(template)s demux. ! ' \
                    ' queue max-size-buffers=0 max-size-time=0 ' \
                    ' ! mpegvideoparse ! %(videodec)s name=videodecoder' \
                    '    ! videorate ! capsfilter name=ratefilter' \
                    '      caps="video/x-raw-yuv,framerate=%(fr)s"' \
                    '    ! %(identity)s name=videoid ' \
                    '    !  @feeder:video@' % dict(template=template,
                            identity=idsync_template,
                            videodec=video_decoder, fr=fr))
    else:
        template = '%s t. ! queue ! @feeder:video@' % template
    return template


# Statistics we get from DVB are:
# signal: signal strength (0 - 65535)
# snr: signal to noise ratio (0 - 65535)
# ber: bit error rate (seems to be driver specific scale)
# unc: uncorrected bits (should be cumulative but drivers do not follow spec)
# lock: locked to signal (boolean)


class DVBTSProducer(feedcomponent.ParseLaunchComponent):

    def init(self):
        self.uiState.addKey('signal', 0)
        self.uiState.addKey('snr', 0)
        self.uiState.addKey('ber', 0)
        self.uiState.addKey('unc', 0)
        self.uiState.addKey('lock', False)
        self.uiState.addDictKey('channelnames')
        self.uiState.addDictKey('whatson')

    def do_check_dvb(self):
        props = self.config['properties']
        dvb_type = self.dvb_type = props.get('dvb-type')
        if dvb_type != 'T' and dvb_type != 'S' and dvb_type != 'FILE':
            msg = \
                "Property dvb-type can only be T (for DVB-T) or S (for DVB-S)."
            return defer.fail(errors.ConfigError(msg))
        # check if the required DVB parameters are passed
        dvb_required_parameters = {
            "T": ["modulation", "trans-mode",
                "bandwidth", "code-rate-lp", "code-rate-hp", "guard",
                "hierarchy", "frequency"],
            "S": ["polarity", "symbol-rate", "frequency"],
            "FILE": ["filename"]}
        for param in dvb_required_parameters[dvb_type]:
            if not param in props:
                msg = T_(N_(
                    "To use DVB-%s mode, you need to specify "
                    "property '%s'." % (
                    dvb_type, param)))
                self.debug("No property %s for dvb-%s", param, dvb_type)
                return defer.fail(errors.ConfigError(msg))

        dvbbasebin_element = gst.element_factory_make("dvbbasebin")
        if not dvbbasebin_element:
            msg = "You do not have the dvbbasebin element. " \
                "Please upgrade to at least gst-plugins-bad 0.10.6."
            return defer.fail(errors.ConfigError(msg))

    def do_check(self):
        return self.do_check_dvb()

    def get_dvbsrc_pipeline_string(self, props):
        dvbsrc_template = ""
        program_numbers = props.get('program-numbers')
        if not program_numbers:
            program_numbers = "%d" % props.get('program-number')
        self.program_numbers = program_numbers.split(":")
        if self.dvb_type == "T":
            modulation = props.get('modulation')
            trans_mode = props.get('trans-mode')
            if trans_mode == 2 or trans_mode == 8:
                trans_mode = "%sk" % trans_mode
            else:
                trans_mode = "AUTO"
            bandwidth = props.get('bandwidth')
            code_rate_lp = props.get('code-rate-lp')
            code_rate_hp = props.get('code-rate-hp')
            guard = props.get('guard')
            hierarchy = props.get('hierarchy')
            dvbsrc_template = '''
dvbbasebin modulation="QAM %(modulation)d"
 trans-mode=%(trans_mode)s
bandwidth=%(bandwidth)d code-rate-lp=%(code_rate_lp)s
code-rate-hp=%(code_rate_hp)s guard=%(guard)d
hierarchy=%(hierarchy)d stats-reporting-interval=5000''' % dict(
                 modulation=modulation, trans_mode=trans_mode,
                bandwidth=bandwidth, code_rate_lp=code_rate_lp,
                code_rate_hp=code_rate_hp,
                guard=guard, hierarchy=hierarchy)
        elif self.dvb_type == "S":
            polarity = props.get('polarity')
            symbol_rate = props.get('symbol-rate')
            sat = props.get('satellite-number', 0)
            code_rate_hp = props.get('code-rate-hp', None)
            dvbsrc_template = '''
dvbbasebin polarity=%(polarity)s symbol-rate=%(symbol_rate)s
 diseqc-source=%(sat)d ''' % dict(polarity=polarity, symbol_rate=symbol_rate,
    sat=sat)

            if code_rate_hp:
                dvbsrc_template = "%s code-rate-hp=%s " % (dvbsrc_template,
                    code_rate_hp)
        elif self.dvb_type == "FILE":
            filename = props.get('filename')
            dvbsrc_template = """filesrc location=%s name=src
            ! mpegtsparse program-numbers=%s""" % (filename, program_numbers)
        if self.dvb_type == "S" or self.dvb_type == "T":
            freq = props.get('frequency')
            dvbsrc_template = "%s frequency=%d program-numbers=%s name=src" % (
                dvbsrc_template, freq, program_numbers)
            adapter = props.get('adapter', 0)
            frontend = props.get('frontend', 0)
            device = props.get('device', None)
            if device and adapter == 0 and frontend == 0:
                # set adapter to be the number from /dev/dvb/adapter
                for adapnum in range(1, 8):
                    if str(adapnum) in device:
                        adapter = adapnum
                # FIXME: add a warning here
            dvbsrc_template = "%s adapter=%d frontend=%d" % (
                dvbsrc_template, adapter, frontend)
        dvbsrc_template = "%s .src%%d" % dvbsrc_template
        return dvbsrc_template

    def get_pipeline_string(self, props):
        dvbsrc_template = self.get_dvbsrc_pipeline_string(props)
        template = ('%(dvbsrc)s ! @feeder:default@'
                    % dict(dvbsrc=dvbsrc_template))
        return template

    def configure_pipeline(self, pipeline, properties):
        self.debug("Connecting to bus message handling")
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::element', self._bus_message_received_cb)

    def _bus_message_received_cb(self, bus, message):
        """
        @param bus: the message bus sending the message
        @param message: the message received
        """
        self.debug("Bus message received %r", message)
        if message.structure.get_name() == 'dvb-frontend-stats':
            # we have frontend stats, lets update ui state
            s = message.structure
            self.uiState.set('signal', s["signal"])
            self.uiState.set('snr', s["snr"])
            self.uiState.set('ber', s["ber"])
            self.uiState.set('unc', s["unc"])
            self.uiState.set('lock', s["lock"])
        elif message.structure.get_name() == 'pat':
            self.debug("PAT info received")
            s = message.structure
            for prog in s["programs"]:
                self.debug("PAT: Program %d on PID 0x%04x",
                    prog["program-number"], prog["pid"])
        elif message.structure.get_name() == 'pmt':
            s = message.structure
            self.debug("PMT info received for program %d", s["program-number"])
            for stream in s["streams"]:
                self.debug("PMT: Stream on pid 0x%04x of type: %d",
                    stream["pid"],
                    stream["stream-type"])
        elif message.structure.get_name() == "sdt":
            s = message.structure
            actual = s["actual-transport-stream"]
            if actual:
                services = s["services"]
                for service in services:
                    name = service.get_name()
                    sid = name[8:]
                    if service.has_field("name"):
                        name = service["name"]
                    if sid in self.program_numbers:
                        self.debug("Setting channel %s to have name %s",
                            sid, name)
                        self.uiState.setitem('channelnames', sid, name)
        elif message.structure.get_name() == "eit":
            s = message.structure
            self.debug("eit received for sid %d", s["service-id"])
            if str(s["service-id"]) in self.program_numbers:
                events = s["events"]
                for e in events:
                    if e["running-status"] == 4:
                        txt = "%d/%d/%d %d:%d (%d minutes)" % (
                            e["day"], e["month"], e["year"], e["hour"],
                            e["minute"], e["duration"]/60)
                        if e.has_field("name"):
                            txt = "%s %s" % (txt, e["name"])
                        if e.has_field("description"):
                            txt = "%s: %s" % (txt, e["description"])
                        self.debug("Now on channel %s: %s",
                            str(s["service-id"]), txt)
                        self.uiState.setitem('whatson', str(s["service-id"]),
                            txt)
                    name = "None"
                    if e.has_field("name"):
                        name = e["name"]
                    self.debug("event %s of running status: %d",
                        name,
                        e["running-status"])


class DVB(DVBTSProducer):

    def do_check(self):
        return self.do_check_dvb()

    def check_properties(self, props, addMessage):
        if props.get('scaled-width', None) is not None:
            self.warnDeprecatedProperties(['scaled-width'])

    def get_pipeline_string(self, props):
        dvbsrc_template = self.get_dvbsrc_pipeline_string(props)
        decode_template = get_decode_pipeline_string(props)
        template = "%s ! tee name=mpegtst ! " \
            "queue max-size-time=0 max-size-buffers=0 ! %s" \
            " mpegtst. ! queue max-size-time=0 max-size-buffers=0 ! " \
            "@feeder:mpegts@" % (dvbsrc_template, decode_template)
        return template

    def configure_pipeline(self, pipeline, props):
        super(DVB, self).configure_pipeline(pipeline, props)
        # add volume effect
        level = pipeline.get_by_name('level')
        vol = volume.Volume('volume', level, pipeline)
        self.addEffect(vol)
        # add deinterlacer effect
        ratefilter = pipeline.get_by_name("ratefilter")
        deinterlacer = deinterlace.Deinterlace('deinterlace',
                ratefilter.get_pad("src"), pipeline, "auto", "ffmpeg")
        self.addEffect(deinterlacer)
        deinterlacer.plug()
        # add videoscaler
        videoscaler = videoscale.Videoscale('videoscale', self,
            deinterlacer.effectBin.get_pad("src"), pipeline,
            props.get('width', 0), props.get('height', 0),
            props.get('is-square', False))
        self.addEffect(videoscaler)
        videoscaler.plug()

        # attach pad monitors to make sure we know when there is no
        # audio or video coming out
        audiodecoder = pipeline.get_by_name('audiodecoder')
        videodecoder = pipeline.get_by_name('videodecoder')
        if audiodecoder:
            self._pad_monitors.attach(audiodecoder.get_pad('src'),
                "audiodecoder")
        if videodecoder:
            self._pad_monitors.attach(videodecoder.get_pad('src'),
                "videodecoder")

    def setVolume(self, value):
        self.debug("Volume set to %d" % value)
        element = self.get_element('volume')
        element.set_property('volume', value)

    def getVolume(self):
        element = self.get_element('volume')
        return element.get_property('volume')


class MpegTSSplitter(DVBTSProducer):

    def init(self):
        self.uiState.addDictKey('channelnames')
        self.uiState.addDictKey('whatson')

    def do_check_dvb(self):
        tsparse_element = gst.element_factory_make("mpegtsparse")
        if not tsparse_element:
            msg = "You do not have the mpegtsparse element. " \
                "Please upgrade to at least gst-plugins-bad 0.10.6."
            return defer.fail(errors.ConfigError(msg))

    def get_pipeline_string(self, props):
        program_number = props.get("program-number")
        template = "mpegtsparse program-numbers=%d .program_%d" % (
            program_number, program_number)
        return template


class MpegTSDecoder(feedcomponent.ParseLaunchComponent):

    def init(self):
        pass

    def check_properties(self, props, addMessage):
        if props.get('scaled-width', None) is not None:
            self.warnDeprecatedProperties(['scaled-width'])

    def get_pipeline_string(self, props):
        return get_decode_pipeline_string(props)

    def configure_pipeline(self, pipeline, props):
        # add volume effect
        level = pipeline.get_by_name('level')
        vol = volume.Volume('volume', level, pipeline)
        self.addEffect(vol)
        # add deinterlacer effect
        ratefilter = pipeline.get_by_name("ratefilter")
        deinterlacer = deinterlace.Deinterlace('deinterlace',
                ratefilter.get_pad("src"), pipeline, "auto", "ffmpeg")
        self.addEffect(deinterlacer)
        deinterlacer.plug()
        # add videoscaler
        videoscaler = videoscale.Videoscale('videoscale', self,
            deinterlacer.effectBin.get_pad("src"), pipeline,
            props.get('width', 0), props.get('height', 0),
            props.get('is-square', False))
        self.addEffect(videoscaler)
        videoscaler.plug()

        # attach pad monitors to make sure we know when there is no
        # audio or video coming out
        audiodecoder = pipeline.get_by_name('audiodecoder')
        videodecoder = pipeline.get_by_name('videodecoder')
        if audiodecoder:
            self._pad_monitors.attach(audiodecoder.get_pad('src'),
                "audiodecoder")
        if videodecoder:
            self._pad_monitors.attach(videodecoder.get_pad('src'),
                "videodecoder")

    def setVolume(self, value):
        self.debug("Volume set to %d" % value)
        element = self.get_element('volume')
        element.set_property('volume', value)

    def getVolume(self):
        element = self.get_element('volume')
        return element.get_property('volume')
