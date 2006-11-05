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

class DVB(feedcomponent.ParseLaunchComponent):
    
    def do_check(self):
        props = self.config['properties']
        dvb_type = self.dvb_type = props.get('dvb-type')
        if dvb_type != 'T' and dvb_type != 'S':
            msg = "Property dvb-type can only be T (for DVB-T) or S (for DVB-S)."
            return defer.fail(errors.ConfigError(msg))
        # check if the required DVB parameters are passed
        dvb_required_parameters = {
            "T": ["modulation", "trans-mode", 
                "bandwidth", "code-rate-lp", "code-rate-hp", "guard",
                "hierarchy", "device"],
            "S": ["polarity", "symbol-rate", "satellite-number", "device"],
            "FILE":  ["filename"]
        }
        for param in dvb_required_parameters[dvb_type]:
            if not param in props:
                msg = "DVB-%s mode is missing property '%s'." % (dvb_type, 
                    param)
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
            dvbsrc_template = '''filesrc location=%s''' % filename
        # we only want to scale if specifically told to in config
        scaling_template = ""
        if "width" in props and "height" in props:
            width = props.get('width')
            height = props.get('height')
            par = props.get('pixel-aspect-ratio', (1,1))
            scaling_template = ('videoscale method=1 ! '
                                'video/x-raw-yuv,width=%d, height=%d, '
                                'pixel-aspect-ratio=%d/%d !' % (
                                    width, height, par[0], par[1]))
        framerate = props.get('framerate', (25, 2))
        fr = "%d/%d" % (framerate[0], framerate[1])
        freq = props.get('frequency')
        pids = props.get('pids')
        template = ('%(dvbsrc)s freq=%(freq)d pids=%(pids)s'
                    ' ! tee name=t ! flutsdemux name=demux es-pids=%(pids)s'
                    ' demux. ! queue max-size-buffers=0 max-size-time=0 '
                    ' ! video/mpeg ! mpeg2dec'
                    '    ! video/x-raw-yuv,format=(fourcc)I420'
                    '    ! videorate'
                    '    ! video/x-raw-yuv,framerate=%(fr)s'
                    '    ! %(scaling)s @feeder::video@'
                    ' demux. ! queue max-size-buffers=0 max-size-time=0'
                    '    ! audio/mpeg ! mad ! audiorate ! @feeder::audio@'
                    ' t. ! @feeder::mpegts@'
                    % dict(freq=freq, pids=pids, 
                           fr=fr, dvbsrc=dvbsrc_template, 
                           scaling=scaling_template))
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
            # we have frontend stats, lets log
            s = message.structure
            self.log("DVB Stats: signal: 0x%x snr: 0x%x ber: 0x%x unc: 0x%x lock: %d",
                s["signal"], s["snr"], s["ber"], s["unc"], s["lock"])
