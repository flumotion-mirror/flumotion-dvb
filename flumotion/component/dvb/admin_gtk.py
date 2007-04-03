# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

from gettext import gettext as _

from flumotion.component.base import admin_gtk
from flumotion.component.effects.volume import admin_gtk as vadmin_gtk

class DVBAdminGtkNode(admin_gtk.BaseAdminGtkNode):
    logCategory = 'dvb'
    glade_file = 'flumotion/component/dvb/dvb.glade'
    uiStateHandlers = None

    def haveWidgetTree(self):
        self.widget = self.wtree.get_widget('widget-dvb')
        self._signal = self.wtree.get_widget('value-signal')
        self._snr = self.wtree.get_widget('value-snr')
        self._ber = self.wtree.get_widget('value-ber')
        self._unc = self.wtree.get_widget('value-unc')

    def setUIState(self, state):
        admin_gtk.BaseAdminGtkNode.setUIState(self, state)
        if not self.uiStateHandlers:
            self.uiStateHandlers = {'signal': self.signalSet,
                                    'snr': self.snrSet,
                                    'ber': self.berSet,
                				    'unc': self.uncSet}
        for k, handler in self.uiStateHandlers.items():
            handler(state.get(k))
                                    
    def stateSet(self, state, key, value):
        handler = self.uiStateHandlers.get(key, None)
        if handler:
            handler(value)

    def wave_changed_cb(self, widget):
        waveName = widget.get_active()
        d = self.callRemote("setWave", waveName)
        d.addErrback(self.warningFailure)
        
    def signalSet(self, signal):
    	if self._signal:
            self._signal.set_text(str(signal))
        
    def snrSet(self, snr):
    	if self._snr:
            self._snr.set_text(str(snr))

    def berSet(self, ber):
        if self._ber:
            self._ber.set_text(str(ber))

    def uncSet(self, unc):
        if self._unc:
            self._unc.set_text(str(unc))

class DVBAdminGtk(admin_gtk.BaseAdminGtk):
    def setup(self):
        dvbnode = DVBAdminGtkNode(self.state, self.admin,
                                  title="DVB")
        self.nodes['DVB'] = dvbnode
        volume = vadmin_gtk.VolumeAdminGtkNode(self.state, self.admin,
                                               'volume', title=_("Volume"))
        self.nodes['Volume'] = volume

        return admin_gtk.BaseAdminGtk.setup(self)
