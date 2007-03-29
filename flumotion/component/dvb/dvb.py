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

from flumotion.common import messages
from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')

class DVB(feedcomponent.ParseLaunchComponent):
    
    def do_check(self):
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
            "S": ["polarity", "symbol-rate", "satellite-number", "frequency"],
            "FILE":  ["filename"]
        }
        for param in dvb_required_parameters[dvb_type]:
            if not param in props:
                msg = T_(N_(
                    "To use DVB-%s mode, you need to specify "
                    "property '%s'." % (
                    dvb_type, param)))
                return defer.fail(errors.ConfigError(msg))

    def get_pipeline_string(self, props):
        dvbsrc_template = ""
        if self.dvb_type == "T":
            modulation = props.get('modulation')
            trans_mode = props.get('trans-mode')
            bandwidth = props.get('bandwidth')
            code_rate_lp = props.get('code-rate-lp')
            code_rate_hp = props.get('code-rate-hp')
            guard = props.get('guard')
            hierarchy = props.get('hierarchy')
            device = props.get('device', '/dev/dvb/adapter0')
            dvbsrc_template = '''
dvbsrc device=%(device)s modulation="QAM %(modulation)d" 
trans-mode=%(trans_mode)dk
bandwidth=%(bandwidth)d code-rate-lp=%(code_rate_lp)s 
code-rate-hp=%(code_rate_hp)s guard=%(guard)d
hierarchy=%(hierarchy)d''' % dict(modulation=modulation, trans_mode=trans_mode,
                bandwidth=bandwidth, code_rate_lp=code_rate_lp,
                code_rate_hp="%d/%d" % (code_rate_hp[0], code_rate_hp[1]),
                guard=guard, hierarchy=hierarchy, device=device)
        elif self.dvb_type == "S":
            polarity = props.get('polarity')
            symbol_rate = props.get('symbol-rate')
            sat = props.get('satellite-number')
            device = props.get('device', '/dev/dvb/adapter0')
            dvbsrc_template = '''
dvbsrc device=%(device)s pol=%(polarity)s srate=%(symbol_rate)s
diseqc-src=%(sat)d''' % dict(polarity=polarity, symbol_rate=symbol_rate, 
    sat=sat, device=device)
        elif self.dvb_type == "FILE":
            filename = props.get('filename')
            dvbsrc_template = 'filesrc location=%s ! video/mpegts' % filename
        has_video = props.get('has-video', True)
        video_decoder = props.get('video-decoder', 'mpeg2dec')
        audio_decoder = props.get('audio-decoder', 'mad')
        # we only want to scale if specifically told to in config
        scaling_template = ""
        if "width" in props and "height" in props:
            width = props.get('width')
            height = props.get('height')
            scaled_width = props.get('scaled-width', width)
            if height > 288:
                interlaced_height = 576
            else:
                interlaced_height = 288
            par = props.get('pixel-aspect-ratio', (1,1))
            scaling_template = ('videoscale method=1 ! '
                ' video/x-raw-yuv,width=%(sw)s,height=%(ih)s !'
                ' videoscale method=1 !'
                ' video/x-raw-yuv,width=%(sw)s,height=%(h)s,'
                'pixel-aspect-ratio=%(par_n)d/%(par_d)d !' % dict(
                    sw=scaled_width, ih=interlaced_height, 
                    h=height, par_n=par[0], par_d=par[1]))
        framerate = props.get('framerate', (25, 2))
        fr = "%d/%d" % (framerate[0], framerate[1])
        pids = props.get('pids')
        audio_pid = props.get('audio-pid', 0)
        idsync_template = ""
        if self.dvb_type == "S" or self.dvb_type == "T":
            freq = props.get('frequency')
            dvbsrc_template = "%s freq=%d pids=%s" % (dvbsrc_template,
                freq, pids)
        elif self.dvb_type == "FILE":
            idsync_template = "identity sync=true silent=true !"
        audio_pid_template = ""
        if audio_pid > 0:
            # transport stream demuxer expects this as 4 digit hex
            audio_pid_template = "audio_%04x " % audio_pid
        template = ('%(dvbsrc)s'
                    ' ! tee name=t ! flutsdemux name=demux'
                    ' demux.%(audiopid)s ! '
                    ' queue max-size-buffers=0 max-size-time=0'
                    ' ! %(audiodec)s ! audiorate ! %(identity)s '
                    ' @feeder::audio@'
                    ' t. ! queue max-size-buffers=0 max-size-time=0 !'
                    ' @feeder::mpegts@'
                    % dict(pids=pids, audiopid=audio_pid_template, 
                           dvbsrc=dvbsrc_template, audiodec=audio_decoder,
                           identity=idsync_template))
        if has_video:
            template = ('%(template)s demux. ! '
                        ' queue max-size-buffers=0 max-size-time=0 '
                        ' ! %(videodec)s '
                        '    ! video/x-raw-yuv'
                        '    ! videorate'
                        '    ! video/x-raw-yuv,framerate=%(fr)s'
                        '    ! %(scaling)s %(identity)s @feeder::video@'
                        % dict(template=template, scaling=scaling_template,
                               identity=idsync_template, 
                               videodec=video_decoder, fr=fr))
        return template

    def configure_pipeline(self, pipeline, properties):
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::element', self._bus_message_received_cb)
        pipeline.connect("deep-notify::pat-info", self.pat_info_cb)
        pipeline.connect("deep-notify::pmt-info", self.pmt_info_cb)

    def _bus_message_received_cb(self, bus, message):
        """
        @param bus: the message bus sending the message
        @param message: the message received
        """
        if message.structure.get_name() == 'dvb-frontend-stats':
            # we have frontend stats, lets log
            s = message.structure
            self.debug("DVB Stats: signal: 0x%x snr: 0x%x ber: 0x%x unc: 0x%x lock: %d",
                s["signal"], s["snr"], s["ber"], s["unc"], s["lock"])

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
