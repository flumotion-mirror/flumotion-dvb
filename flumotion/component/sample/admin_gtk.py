# -*- Mode: Python; test-case-name: flumotion.test.test_sample_admin_gtk -*-
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

import os
import gtk

from flumotion.common import errors, common

from flumotion.component.sample.common import getMethod, getBooleans
from flumotion.component.base.admin_gtk import BaseAdminGtk, BaseAdminGtkNode

_ = common.gettexter('flumotion-template')

class FlipAdminGtkNode(BaseAdminGtkNode):
    glade_file = os.path.join('flumotion', 'component', 'sample',
        'sample.glade')
    gettext_domain = "flumotion-template"

    def __init__(self, *args, **kwargs):
        BaseAdminGtkNode.__init__(self, *args, **kwargs)
        self._cbh = None
        self._cbv = None

    def error_dialog(self, message):
        # FIXME: dialogize
        print 'ERROR:', message
        
    def haveWidgetTree(self):
        self.widget = self.getWidget('sample-widget')
        self._cbh = self.getWidget('checkbutton_horizontal')
        self._cbv = self.getWidget('checkbutton_vertical')

        d = self.callRemote("getElementProperty", "videoflip", "method")
        d.addCallback(self._getMethodCallback)
        d.addErrback(self._getMethodErrback)
        return d

    def _getMethodCallback(self, result):
        self.debug('got videoflip pattern %d' % result)
        self._setToggles(result)
        self._cbh_toggled_id = self._cbh.connect('toggled', self._cb_toggled)
        self._cbv_toggled_id = self._cbv.connect('toggled', self._cb_toggled)

        return self.widget

    # set the two toggles based on the method value
    def _setToggles(self, method):
        hor, ver = getBooleans(method)
        self._cbh.set_active(hor)
        self._cbv.set_active(ver)
    
    def _getMethodErrback(self, failure):
        self.warning(failure.getErrorMessage())
        self.error_dialog(failure.getErrorMessage())

    def _cb_toggled(self, _):
        hor = self._cbh.get_active()
        ver = self._cbv.get_active()
        self.debug("toggled to %r, %r" % (hor, ver))
        method = getMethod(hor, ver)
        self.debug("toggled to value %d" % method)
        self.callRemote("setElementProperty", "videoflip", "method", method)

    def propertyChanged(self, name, value):
        self.debug("property %s changed to %r" % (name, value))
        if name == "method":
            self.debug("method changed to %r" % value)
            self._cbh.handler_block(self._cbh_toggled_id)
            self._cbv.handler_block(self._cbv_toggled_id)
            self._setToggles(value)
            self._cbh.handler_unblock(self._cbh_toggled_id)
            self._cbv.handler_unblock(self._cbv_toggled_id)

class SampleAdminGtk(BaseAdminGtk):
    gettext_domain = 'flumotion-template'

    def setup(self):
        d = BaseAdminGtk.setup(self)
        d.addCallback(lambda _: self._setupNodes())
        return d

    def _setupNodes(self):
        flip = FlipAdminGtkNode(self.state, self.admin, title=_('Flipping'))
        self.nodes['Flipping'] = flip

    def component_propertyChanged(self, name, value):
        # FIXME: tie to correct node better
        self.nodes['Flipping'].propertyChanged(name, value)

GUIClass = SampleAdminGtk
