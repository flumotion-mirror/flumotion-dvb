# -*- Mode: Python; test-case-name: flumotion.test.test_sample_admin_gtk -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.
# flumotion-ground-control - Advanced Administration

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

import common

from twisted.trial import unittest

import os
import gobject
import gtk

from flumotion.common import common, componentui, log
from flumotion.test import gtkunit

from twisted.internet import defer

_thisdir = os.path.dirname(os.path.abspath(__file__))

state = {
    'name': 'test'
}

# FIXME: move this to base flumotion and test some ui's there too
class TestBundleLoader(log.Loggable):
    logCategory = 'testbundleloader'

    def getFile(self, file):
        self.debug("getting file %s" % file)
        return defer.succeed(os.path.abspath(os.path.join(
            _thisdir, '..', '..', file)))

    def getBundleByName(self, bundleName):
        return defer.succeed(os.path.abspath(os.path.join(
            _thisdir, '..', '..')))
    
class TestAdminModel(log.Loggable):
    logCategory = 'testadminmodel'
    
    def __init__(self):
        self._uiState = componentui.AdminComponentUIState()
        self._videoflip_method = 5
        self.bundleLoader = TestBundleLoader()

    def componentCallRemote(self, componentName, methodName, *args, **kwargs):
        self.debug("componentName %s, methodName %s" % (componentName, 
            methodName))
        if hasattr(self, 'local_' + methodName):
            return getattr(self, 'local_' + methodName)(*args, **kwargs)

        raise NotImplementedError, "local_" + methodName

    def local_getUIState(self):
        return defer.succeed(self._uiState)

    def local_getElementProperty(self, elementName, propertyName):
        self.debug("getting %s.%s" % (elementName, propertyName))
        return defer.succeed(getattr(self,
            '_%s_%s' % (elementName, propertyName)))

    def local_setElementProperty(self, elementName, propertyName, value):
        self.debug("setting %s.%s to %r" % (elementName, propertyName,
            value))
        setattr(self, '_%s_%s' % (elementName, propertyName), value)

class SampleFlipNodeTest(gtkunit.GtkTestCase):
    def setUp(self):
        from flumotion.component.sample import admin_gtk

        self.admin = TestAdminModel()
        self.node = admin_gtk.FlipAdminGtkNode(state, self.admin)
        d = self.node.render()
        d.addCallback(lambda widget: self.set_widget(widget))
        return d
        
    def testToggle(self):
        self.assertEquals(self.admin._videoflip_method, 5)

        self.toggle('checkbutton_vertical')
        self.assertEquals(self.admin._videoflip_method, 0)

        self.toggle('checkbutton_horizontal')
        self.assertEquals(self.admin._videoflip_method, 4)

        self.toggle('checkbutton_vertical')
        self.assertEquals(self.admin._videoflip_method, 2)

        self.toggle('checkbutton_horizontal')
        self.assertEquals(self.admin._videoflip_method, 5)

    def testPropertyChanged(self):
        self.node.propertyChanged('method', 5)
        self.assertEquals(self.admin._videoflip_method, 5)

class SampleAdminTest(gtkunit.GtkTestCase):
    def setUp(self):
        from flumotion.component.sample import admin_gtk

        self.adminModel = TestAdminModel()
        self.adminGtk = admin_gtk.SampleAdminGtk(state, self.adminModel)
        return self.adminGtk.setup()

    def testConstructor(self):
        pass

    # FIXME: for this test, we need to make the base admin class do
    # more on its own, like create the notebook and such
    def notestPropertyChanged(self):
        self.adminGtk.component_propertyChanged('method', 5)
        self.assertEquals(self.adminGtk.nodes['Flipping']._videoflip_method, 5)
