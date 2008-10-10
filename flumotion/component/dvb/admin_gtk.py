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

from flumotion.component.base.admin_gtk import BaseAdminGtk
from flumotion.component.base.baseadminnode import BaseAdminGtkNode
from flumotion.component.effects.volume import admin_gtk as vadmin_gtk
from kiwi.ui.objectlist import Column, ObjectList

# Copied from component/base/admin_gtk.py


class _StateWatcher(object):

    def __init__(self, state, setters, appenders, removers,
            setitemers=None, delitemers=None):
        self.state = state
        self.setters = setters
        self.appenders = appenders
        self.removers = removers
        self.setitemers = setitemers
        self.delitemers = delitemers
        self.shown = False

        state.addListener(self, set=self.onSet, append=self.onAppend,
                          remove=self.onRemove, setitem=self.onSetItem,
                          delitem=self.onDelItem)

        for k in appenders:
            for v in state.get(k):
                self.onAppend(state, k, v)

        for k in setters:
            for v in state.get(k):
                self.onSet(state, k, v)

    def hide(self):
        if self.shown:
            for k in self.setters:
                self.onSet(self.state, k, None)
            self.shown = False

    def show(self):
        # "show" the watcher by triggering all the registered setters
        if not self.shown:
            self.shown = True
            for k in self.setters:
                self.onSet(self.state, k, self.state.get(k))

    def onSet(self, obj, k, v):
        if self.shown and k in self.setters:
            self.setters[k](self.state, v)

    def onAppend(self, obj, k, v):
        if k in self.appenders:
            self.appenders[k](self.state, v)

    def onRemove(self, obj, k, v):
        if k in self.removers:
            self.removers[k](self.state, v)

    def onSetItem(self, obj, k, sk, v):
        if self.shown and k in self.setitemers:
            self.setitemers[k](self.state, sk, v)

    def onDelItem(self, obj, k, sk, v):
        if self.shown and k in self.setitemers:
            self.setitemers[k](self.state, sk, v)

    def unwatch(self):
        if self.state:
            self.hide()
            for k in self.removers:
                for v in self.state.get(k):
                    self.onRemove(self.state, k, v)
                self.state.removeListener(self)
                self.state = None


class SignalStatisticsAdminGtkNode(BaseAdminGtkNode):
    logCategory = 'dvb'
    gladeFile = 'flumotion/component/dvb/dvb.glade'
    uiStateHandlers = None

    def haveWidgetTree(self):
        self.widget = self.wtree.get_widget('widget-dvb')
        self._signal = self.wtree.get_widget('value-signal')
        self._snr = self.wtree.get_widget('value-snr')
        self._ber = self.wtree.get_widget('value-ber')
        self._unc = self.wtree.get_widget('value-unc')
        self._lock = self.wtree.get_widget('value-lock')

    def setUIState(self, state):
        BaseAdminGtkNode.setUIState(self, state)
        if not self.uiStateHandlers:
            self.uiStateHandlers = {'signal': self.signalSet,
                                    'snr': self.snrSet,
                                    'ber': self.berSet,
                                    'unc': self.uncSet,
                                    'lock': self.lockSet}
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

    def lockSet(self, locked):
        if self._lock:
            self._lock.set_text(str(locked))


class DVBChannel:

    def __init__(self, programnumber, name):
        self.programnumber = programnumber
        self.name = name
        self.whatson = ""

    def set_name(self, name):
        self.name = name

    def set_whatson(self, whatson):
        self.whatson = whatson


class DVBServiceInformationAdminGtkNode(BaseAdminGtkNode):
    channels = {}
    siwidget = None

    def render(self):

        def returnWidget(res):
            return self.siwidget
        self.siwidget = ObjectList([Column('programnumber',
            'Program Number', data_type=str),
            Column('name', data_type=str),
            Column('whatson', 'What\'s On', data_type=str)])
        whatsontvcolumn = self.siwidget.get_treeview_column(\
            self.siwidget.get_column_by_name('whatson'))
        import pango
        for renderer in whatsontvcolumn.get_cell_renderers():
            renderer.set_property('wrap-width', 200)
            renderer.set_property('wrap-mode', pango.WRAP_WORD)
        self.widget = self.siwidget
        d = BaseAdminGtkNode.render(self)
        d.addCallback(returnWidget)
        return d

    def setUIState(self, state):
        BaseAdminGtkNode.setUIState(self, state)
        self._watcher = _StateWatcher(state,
           {
                'channelnames': self._setChannelName,
                'whatson': self._setWhatsOn,
           },
           {},
           {},
           setitemers={
                'channelnames': self._setChannelNameItem,
                'whatson': self._setWhatsOnItem,
           },
           delitemers={
                'channelnames': self._delChannelNameItem,
                'whatson': self._delWhatsOnItem,
           })
        self._watcher.show()
        for chan in self.channels:
            self.siwidget.append(chan)

    def _setChannelName(self, state, value):
        if value is None:
            return
        for k, v in value.items():
            self._setChannelNameItem(state, k, v)

    def _setChannelNameItem(self, state, key, value):
        self.debug("set channel name item %s:%s", key, value)
        if key in self.channels:
            chan = self.channels[key]
            chan.set_name(value)
        else:
            self.channels[key] = DVBChannel(key, value)
            if self.siwidget:
                self.siwidget.append(self.channels[key])

    def _delChannelNameItem(self, state, key, value):
        pass

    def _setWhatsOn(self, state, value):
        if value is None:
            return
        for k, v in value.items():
            self._setWhatsOnItem(state, k, v)

    def _setWhatsOnItem(self, state, key, value):
        if key in self.channels:
            chan = self.channels[key]
            chan.set_whatson(value)
        else:
            chan = DVBChannel(key, "")
            chan.set_whatson(value)
            self.channels[key] = chan
            if self.siwidget:
                self.siwidget.append(chan)

    def _delWhatsOnItem(self, state, key, value):
        pass


class DVBBaseAdminGtk(BaseAdminGtk):

    def setup(self):
        dvbnode = SignalStatisticsAdminGtkNode(self.state, self.admin,
                                  title="Signal Statistics")
        self.nodes['Signal Statistics'] = dvbnode
        channelsnode = DVBServiceInformationAdminGtkNode(self.state,
            self.admin, title="Channel Information")
        self.nodes["Channel Information"] = channelsnode
        return BaseAdminGtk.setup(self)


class DVBAdminGtk(DVBBaseAdminGtk):

    def setup(self):
        volume = vadmin_gtk.VolumeAdminGtkNode(self.state, self.admin,
                                               'volume', title=_("Volume"))
        self.nodes['Volume'] = volume

        return DVBBaseAdminGtk.setup(self)


class MpegTSDecoderAdminGtk(BaseAdminGtk):

    def setup(self):
        volume = vadmin_gtk.VolumeAdminGtkNode(self.state, self.admin,
                                               'volume', title=_("Volume"))
        self.nodes['Volume'] = volume

        return BaseAdminGtk.setup(self)


class MpegTSSplitterAdminGtk(BaseAdminGtk):

    def setup(self):
        return BaseAdminGtk.setup(self)
