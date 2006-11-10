#!/usr/bin/python
# vi:si:et:sw=4:sts=4:ts=4

import pygst
pygst.require('0.10')
import gst
import gobject

class DvbBin(gst.Bin):

    # pids we currently allow through the dvbsrc filter
    pids = []
    # current program number
    program_number = -1
    # dict keyed on the padname (corresponds to pid)
    # values are a tuple of (queue, decoder, identity) element objects
    pids_elements = {}
    # value of the following is (identity, event_probe_id)
    video_elements = None
    audio_elements = None
    # following are currently used pads for demuxer
    current_video_pad = None
    current_audio_pad = None
    # the following are tuples of: (padname, queue, decoder)
    pending_video = None
    pending_audio = None
    # This flag means that we will not receive new pads for this current
    # segment
    no_more_pads = False

    def __init__(self, tuning_params, program_number):
        gobject.GObject.__init__(self)
        self.src = gst.element_factory_make("dvbsrc")
        for param in tuning_params:
            print "Setting property %s to %r" % (param[0], param[1])
            self.src.set_property(param[0], param[1])
        self.src.set_property("pids", "16:17:18")
        self.demux = gst.element_factory_make("flutsdemux")
        self.add(self.src, self.demux)
        self.program_number = program_number
        self.src.link(self.demux)
        self.demux.connect("pad-added", self._pad_added_cb)
        self.demux.connect("pad-removed", self._pad_removed_cb)
        self.demux.connect("no-more-pads", self._no_more_pads_cb)
        self.demux.connect("notify::pat-info", self._pat_info_changed_cb)
        self.demux.connect("notify::pmt-info", self._pmt_info_changed_cb)

    def _pat_info_changed_cb(self, demux, param):
        self.debug("PAT info has changed")
        pi = demux.get_property("pat-info")
        for prog in pi:
            self.debug("PAT: Program %d on PID 0x%04x" % ( 
                prog.props.program_number, prog.props.pid))
            if prog.props.program_number == self.program_number:
                self.pids = [prog.props.pid]
                self.src.set_property("pids", "16:17:18:%d" % prog.props.pid)
                self.demux.set_property("program-number", self.program_number)

    def _pmt_info_changed_cb(self, demux, param):
        pi = demux.get_property("pmt-info")
        self.debug("PMT info for program %s has changed" % 
            pi.props.program_number)
        self.debug("PMT: PCR pid is 0x%04x" % pi.props.pcr_pid)
        for s in pi.props.stream_info:
            self.debug("PMT: Stream on pid 0x%04x" % s.props.pid)
            self.pids.append(s.props.pid)
        pid_string = "16:17:18"
        for pid in self.pids:
            pid_string = "%s:%d" % (pid_string, pid)
        self.debug ("Setting pid filter to %s" % (pid_string))
        self.src.set_property("pids", pid_string)

    def _pad_added_cb(self, demux, pad):
        padname = pad.get_name()
        caps_str = pad.get_caps().to_string()
        is_video = True
        self.debug("pad %s got added with caps: %s" % (padname, caps_str))
            
        if "video/mpeg" in caps_str:
            if self.no_more_pads:
                self.info("This pad added is in a new segment")
                if self.pending_video:
                    self.info("We already have a pending video pad, ignoring")
                else:
                    # let's create a new queue and decoder
                    queue = gst.element_factory_make("queue")
                    queue.set_property("max-size-time", 0)
                    queue.set_property("max-size-buffers", 0)
                    decoder = gst.element_factory_make("mpeg2dec")
                    self.add(queue, decoder)
                    queue.link(decoder)
                    # we will have to wait, cannot connect identity now
                    pad.link(queue.get_pad("sink"))
                    # don't set to playing yet
                    self.pending_video = (padname, queue, decoder)
            elif self.current_video_pad:
                self.info("We already have a current video pad, so ignoring")
                return
            self.current_video_pad = pad
        if "audio/mpeg" in caps_str:
            if self.no_more_pads:
                self.info("This pad added is in a new segment")
                if self.pending_audio:
                    self.info("We already have a pending video pad, ignoring")
                else:
                    # let's create a new queue and decoder
                    queue = gst.element_factory_make("queue")
                    queue.set_property("max-size-time", 0)
                    queue.set_property("max-size-buffers", 0)
                    decoder = gst.element_factory_make("mad")
                    self.add(queue, decoder)
                    queue.link(decoder)
                    # we will have to wait, cannot connect identity now
                    pad.link(queue.get_pad("sink"))
                    # don't set to playing yet
                    self.pending_audio = (padname, queue, decoder)

            if self.current_audio_pad:
                self.info("We already have a current audio pad, so ignoring")
                return
            self.current_audio_pad = pad
            is_video = False
        if padname in self.pids_elements:
            self.debug("we already have this pad, so must be soon removing")
        else:
            decoder = None
            if is_video:
                decoder = gst.element_factory_make("mpeg2dec")
            else:
                decoder = gst.element_factory_make("mad")
            
            if decoder:
                queue = gst.element_factory_make("queue")
                queue.set_property("max-size-time", 0)
                queue.set_property("max-size-buffers", 0)
                identity = None
                if is_video and self.video_elements:
                    identity = self.video_elements[0]
                elif not is_video and self.audio_elements:
                    identity = self.audio_elements[0]
                else:
                    identity = gst.element_factory_make("identity")
                    identity.set_property("single-segment", True)
                    identity.set_property("silent", True)
                    self.add(identity)
                self.add(queue, decoder)
                pad.link(queue.get_pad("sink"))
                queue.link(decoder)
                decoder.link(identity)
                queue.set_state(gst.STATE_PLAYING)
                decoder.set_state(gst.STATE_PLAYING)
                identity.set_state(gst.STATE_PLAYING)
                self.pids_elements[padname] = (queue, decoder, identity)
                if is_video and not self.video_elements:
                    event_probe_id = identity.get_pad("sink").add_event_probe(
                        self._event_probe_cb, padname)
                    self.video_elements = (identity, event_probe_id)
                elif not is_video and not self.audio_elements:
                    event_probe_id = identity.get_pad("sink").add_event_probe(
                        self._event_probe_cb, padname)
                    self.audio_elements = (identity, event_probe_id)
                identity.get_pad("src").set_blocked_async(True, 
                    self._pad_blocked_cb, padname)
                self.debug("just added decoder for this pad")
    
    def _pad_removed_cb(self, pad):
        padname = pad.get_name()
        self.debug("%s has been removed from demuxer" % padname)

    def _no_more_pads_cb(self):
        self.no_more_pads = True

    def _pad_blocked_cb(self, pad, blocked, padname):
        if blocked:
            identity_ghostpad = gst.GhostPad(padname, pad)
            self.add_pad(identity_ghostpad)
            pad.set_blocked_async (False, self._pad_blocked_cb, padname)
        else:
            self.debug("unblocked pad %s" % padname)

    def _event_probe_cb(self, pad, event, padname):
        if event.type == gst.EVENT_EOS:
            self.info("End of stream received for identity referring to %s",
                padname)
            gobject.idle_add(self._remove_elements, padname)
            return False
        return True

    def _remove_elements(self, padname):
        self.info("Removing elements for padname %s" % padname)
        element_tuple = self.pid_elements[padname]
        element_tuple[0].unlink(element_tuple[1])
        element_tuple[1].unlink(element_tuple[2])
        self.remove(element_tuple[0])
        self.remove(element_tuple[1])
        del self.pid_elements[padname]
        if "video" in padname and not self.current_audio_pad:
            # we have now removed both video and audio
            self.current_video_pad = None
            if self.pending_video:
                padname = self.pending_video[0]
                queue = self.pending_video[1]
                decoder = self.pending_video[2]
                decoder.link(element_tuple[2])
                queue.set_state(gst.STATE_PLAYING)
                decoder.set_state(gst.STATE_PLAYING)
                self.pending_video = None
            self.no_more_pads = False
        elif "audio" in padname and not self.current_video_pad:
            # we have now removed both video and audio
            self.current_audio_pad = None
            if self.pending_audio:
                padname = self.pending_video[0]
                queue = self.pending_video[1]
                decoder = self.pending_video[2]
                decoder.link(element_tuple[2])
                queue.set_state(gst.STATE_PLAYING)
                decoder.set_state(gst.STATE_PLAYING)
                self.pending_audio = None
            self.no_more_pads = False
        return False

def dvb_pad_added(element, pad, dvbsrc, pipeline, what_we_have):
    if element == dvbsrc:
        if what_we_have["video"] and "video" in pad.get_name():
            print "We already have video, bye"
        elif "video" in pad.get_name():
            what_we_have["video"] = True
            print "we do not have video, connecting fakesink"
            fakesink = gst.element_factory_make("fakesink")
            fakesink.set_proprty("silent", True)
            fakesink.set_property("sync", False)
            pipeline.add(fakesink)
            pad.link(fakesink.get_pad("sink"))
            fakesink.set_state(gst.STATE_PLAYING)

        elif what_we_have["audio"] and "audio" in pad.get_name():
            print "We already have audio bye"
        elif "audio" in pad.get_name():
            what_we_have["audio"] = True
            print "we do not have audio, connecting fakesink"
            fakesink = gst.element_factory_make("fakesink")
            fakesink.set_property("silent", True)
            fakesink.set_property("sync", False)
            pipeline.add(fakesink)
            pad.link(fakesink.get_pad("sink"))
            fakesink.set_state(gst.STATE_PLAYING)

def bus_watch_func(bus, message):
    t = message.type
    src = message.src

    # print 'message:', t, src and src.get_name() or '(no source)'
    if t == gst.MESSAGE_STATE_CHANGED:
        old, new, pending = message.parse_state_changed()
        print "state change: %r %s->%s pending: %s" % (src, old.value_nick, 
            new.value_nick, pending.value_nick) 

gobject.threads_init()
pipeline = gst.Pipeline()
bus=pipeline.get_bus()
bus.add_signal_watch()
bus.connect("message", bus_watch_func)
tuning_params = [ ("modulation", "QAM 64"), ("trans-mode", "8k"), 
    ("bandwidth", "8"), ("freq", 794000000), ("code-rate-lp", "AUTO"),
    ("code-rate-hp", "2/3"), ("guard", "4") ]
dvbsrc = DvbBin(tuning_params, 801)
what_we_have = { "audio": False, "video": False }
dvbsrc.connect("pad-added", dvb_pad_added, dvbsrc, pipeline, what_we_have)
pipeline.add(dvbsrc)
pipeline.set_state(gst.STATE_PLAYING)
mainloop = gobject.MainLoop()
try:
    mainloop.run()
except KeyboardInterrupt:
    print "keyboard interrupted"
