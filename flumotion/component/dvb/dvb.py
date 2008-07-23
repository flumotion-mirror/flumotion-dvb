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

from flumotion.component import feedcomponent
from flumotion.common import errors
from twisted.internet import defer
from flumotion.component.effects.volume import volume
import gst
from flumotion.common import messages
from flumotion.common.i18n import N_, gettexter
T_ = gettexter('flumotion')


def get_decode_pipeline_string(props):
    has_video = props.get('has-video', True)
    video_decoder = props.get('video-decoder', 'mpeg2dec')
    audio_decoder = props.get('audio-decoder', 'mad')
    deinterlacer = props.get('deinterlacer', None)
    # we only want to scale if specifically told to in config
    scaling_template = ""
    deinterlacing_template = deinterlacer
    width = props.get('width', None)
    height = props.get('height', None)
    scaled_width = 720
    if width and height:
        scaled_width = props.get('scaled-width', width)
    if not deinterlacer:
        interlaced_height = 288
        deinterlacing_template = ('videoscale method=1 ! '
            ' video/x-raw-yuv,width=%(sw)s,height=%(ih)s ' % dict(
            sw=scaled_width, ih=interlaced_height))
    else:
        deinterlacing_template = deinterlacer
    if "width" in props and "height" in props:
        par = props.get('pixel-aspect-ratio')
        if par:
            scaling_template = ('videoscale method=1 !'
                ' video/x-raw-yuv,width=%(sw)s,height=%(h)s,'
                'pixel-aspect-ratio=%(par_n)d/%(par_d)d !' % dict(
                    sw=scaled_width, 
                    h=height, par_n=par[0], par_d=par[1]))
        else:
            scaling_template = ('videoscale method=1 !'
                'video/x-raw-yuv,width=%(sw)s,height=%(h)s !' % dict(
                    sw=scaled_width,
                    h=height))
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
                    '    ! video/x-raw-yuv' \
                    '    ! videorate' \
                    '    ! video/x-raw-yuv,framerate=%(fr)s' \
                    '    ! %(deinterlacing)s' \
                    '    ! %(scaling)s %(identity)s name=videoid ' \
                    '    ! @feeder:video@' % dict(template=template, 
                            scaling=scaling_template,
                            deinterlacing=deinterlacing_template,
                            identity=idsync_template, 
                            videodec=video_decoder, fr=fr))
    else:
        template = '%s t. ! @feeder:video@' % template
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
            msg = "Property dvb-type can only be T (for DVB-T) or S (for DVB-S)."
            return defer.fail(errors.ConfigError(msg))
        # check if the required DVB parameters are passed
        dvb_required_parameters = {
            "T": ["modulation", "trans-mode", 
                "bandwidth", "code-rate-lp", "code-rate-hp", "guard",
                "hierarchy", "frequency"],
            "S": ["polarity", "symbol-rate", "frequency"],
            "FILE":  ["filename"]
        }
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
            bandwidth = props.get('bandwidth')
            code_rate_lp = props.get('code-rate-lp')
            code_rate_hp = props.get('code-rate-hp')
            guard = props.get('guard')
            hierarchy = props.get('hierarchy')
            dvbsrc_template = '''
dvbbasebin modulation="QAM %(modulation)d" 
trans-mode=%(trans_mode)dk
bandwidth=%(bandwidth)d code-rate-lp=%(code_rate_lp)s 
code-rate-hp=%(code_rate_hp)s guard=%(guard)d
hierarchy=%(hierarchy)d''' % dict(modulation=modulation, trans_mode=trans_mode,
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
                ! mpegtsparse program-numbers=%d""" % (filename,program_numbers)
        if self.dvb_type == "S" or self.dvb_type == "T":
            freq = props.get('frequency')
            dvbsrc_template = "%s frequency=%d program-numbers=%s name=src" % (
                dvbsrc_template, freq, program_numbers)
            adapter = props.get('adapter', 0)
            frontend = props.get('frontend', 0)
            device = props.get('device', None)
            if device and adapter == 0 and frontend == 0:
                # set adapter to be the number from /dev/dvb/adapter
                for adapnum in range(1,8):
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
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::element', self._bus_message_received_cb)

    def _bus_message_received_cb(self, bus, message):
        """
        @param bus: the message bus sending the message
        @param message: the message received
        """
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
                    sid =  name[8:]
                    if service.has_key("name"):
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
                        if e.has_key("name"):
                            txt = "%s %s" % (txt, e["name"])
                        if e.has_key("description"):
                            txt = "%s: %s" % (txt, e["description"])
                        self.debug("Now on channel %s: %s", 
                            str(s["service-id"]), txt)
                        self.uiState.setitem('whatson', str(s["service-id"]),
                            txt)
                    name = "None"
                    if e.has_key("name"):
                        name = e["name"]
                    self.debug("event %s of running status: %d", 
                        name,
                        e["running-status"])
                    
class DVB(DVBTSProducer):

    def do_check(self):
        return self.do_check_dvb()

    def get_pipeline_string(self, props):
        dvbsrc_template = self.get_dvbsrc_pipeline_string(props)
        decode_template = get_decode_pipeline_string(props)
        template = "%s ! tee name=mpegtst ! " \
            "queue max-size-time=0 max-size-buffers=0 ! %s" \
            " mpegtst. ! queue max-size-time=0 max-size-buffers=0 ! " \
            "@feeder:mpegts@" % (dvbsrc_template, decode_template)
        return template

    
    def configure_pipeline(self, pipeline, properties):
        super(DVBTSProducer, self).configure_pipeline(pipeline, properties)
        # add volume effect
        level = pipeline.get_by_name('level')
        vol = volume.Volume('volume', level, pipeline)
        self.addEffect(vol)
        # attach pad monitors to make sure we know when there is no
        # audio or video comming out
        audiodecoder = pipeline.get_by_name('audiodecoder')
        videodecoder = pipeline.get_by_name('videodecoder')
        if audiodecoder:
            self._pad_monitors.attach(audiodecoder.get_pad('src'), 
                "audiodecoder")
        if videodecoder:
            self._pad_monitors.attach(videodecoder.get_pad('src'), 
                "videodecoder")

    def _bus_message_received_cb(self, bus, message):
        """
        @param bus: the message bus sending the message
        @param message: the message received
        """
        if message.structure.get_name() == 'dvb-frontend-stats':
            # we have frontend stats, lets update ui state
            s = message.structure
            self.uiState.set('signal', s["signal"])
            self.uiState.set('snr', s["snr"])
            self.uiState.set('ber', s["ber"])
            self.uiState.set('unc', s["unc"])
            self.uiState.set('lock', s["lock"])
        elif message.structure.get_name() == 'imperfect-timestamp':
            identityName = message.src.get_name() 
            self.log("we have an imperfect stream from %s",
                identityName[:-2])
            # figure out the discontinuity
            s = message.structure
            expectedTimestamp = s["prev-timestamp"] + s["prev-duration"]
            message = None
            if s["cur-timestamp"] > expectedTimestamp + 10 * gst.SECOND:
                message = "We had a large ( > 10 second) difference in " \
                    "timestamps with %s" % identityName[:-2]
            elif s["cur-timestamp"] < s["prev-timestamp"]:
                message = "We went backwards in timestamp with %s" % (
                    identityName[:-2],)
            if message:
                m = messages.Warning(T_(N_(
                    message)),
                id="timestamp-discont",
                priority=40)
                self.state.append('messages', m)
        elif message.structure.get_name() == 'pat':
            self.debug("PAT info received")
            s = message.structure
            for prog in s["programs"]:
                self.debug("PAT: Program %d on PID 0x%04x",
                    prog["program_number"], prog["pid"])
        elif message.structure.get_name() == 'pmt':
            s = message.structure
            self.debug("PMT info received for program %d", s["program-number"])
            for stream in s["streams"]:
                self.debug("PMT: pid %d type: %d", stream["pid"], 
                    stream["stream-type"])

    def pat_info_cb(self, sender, demux, param):
        self.debug("PAT info received from: %s", demux.get_name())
        pi = demux.get_property("pat-info")
        for prog in pi:
            self.debug("PAT: Program %d on PID 0x%04x",
                prog.props.program_number,prog.props.pid)
        self.debug("PAT parsing finished")

    def pmt_info_cb(self, sender, demux, param):
        pi = demux.get_property("pmt-info")
        self.debug("PMT info for program: %d with version: %d", 
            pi.props.program_number, pi.props.version_number)
        self.debug("PMT: PCR on PID 0x%04x", pi.props.pcr_pid)
        for s in pi.props.stream_info:
            self.debug("PMT: Stream on PID 0x%04x", s.props.pid)
            for l in s.props.languages:
                self.debug("PMT: Language %s", l)

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
        template = "mpegtsparse program-numbers=%d .program_%d"  % (
            program_number, program_number)
        return template

class MpegTSDecoder(feedcomponent.ParseLaunchComponent):

    def init(self):
        pass

    def get_pipeline_string(self, props):
        return get_decode_pipeline_string(props)

    def configure_pipeline(self, pipeline, properties):
        # add volume effect
        level = pipeline.get_by_name('level')
        vol = volume.Volume('volume', level, pipeline)
        self.addEffect(vol)
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
