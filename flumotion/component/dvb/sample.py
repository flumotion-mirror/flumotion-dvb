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

from flumotion.common import log

from flumotion.component import feedcomponent

from flumotion.component.sample.common import getMethod

class SampleMedium(feedcomponent.FeedComponentMedium):
    __pychecker__ = "no-argsused" # we want to explicitly name unused args
    
    def __init__(self, comp):
        feedcomponent.FeedComponentMedium.__init__(self, comp)

    def setup(self, config):
        # connect to method notify
        videoflip = self.comp.get_element('videoflip')
        videoflip.connect('notify::method', self._cb_method_notify)

    def _cb_method_notify(self, object, pspec):
        method = object.get_property('method')
        self.debug('method changed to %d, notifying admins' % method)
        self.callRemote('adminCallRemote', 'propertyChanged', 'method',
            int(method))

# this is a sample converter component for video that will use videoflip
# FIXME: check for videoflip plugin on worker
class Sample(feedcomponent.ParseLaunchComponent):

    component_medium_class = SampleMedium
    
    def get_pipeline_string(self, properties):
        hor = properties.get('horizontal', False)
        ver = properties.get('vertical', False)
        method = getMethod(hor, ver)
        
        return ("ffmpegcolorspace ! videoflip name=videoflip method=%r ! "
                "ffmpegcolorspace " % method)
