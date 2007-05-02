##############################################################################
#
# Copyright (c) 2006 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Run all doctests contained within zope.webdav.

$Id$
"""
import unittest
import UserDict

from zope.testing import doctest

import zope.event
from zope import component
from zope import interface
import zope.schema.interfaces
from zope.annotation.interfaces import IAttributeAnnotatable
from zope.app.container.interfaces import IContained, IContainer
from zope.app.testing import placelesssetup
import zope.app.keyreference.interfaces
from zope.component.interfaces import IComponentLookup
from zope.app.component.site import SiteManagerAdapter
from zope.security.testing import Principal, Participation
from zope.security.management import newInteraction, endInteraction, \
     queryInteraction
from zope.traversing.browser.interfaces import IAbsoluteURL

import zope.etree.testing
import zope.webdav.widgets
import zope.webdav.interfaces


class IDemo(IContained):
    "a demonstration interface for a demonstration class"


class IDemoFolder(IContained, IContainer):
    "a demostration interface for a demostration folder class"


class Demo(object):
    interface.implements(IDemo, IAttributeAnnotatable)

    __parent__ = __name__ = None


class DemoFolder(UserDict.UserDict):
    interface.implements(IDemoFolder)

    __parent__ = __name__ = None

    def __init__(self, parent = None, name = u''):
        UserDict.UserDict.__init__(self)
        self.__parent__ = parent
        self.__name__   = name

    def __setitem__(self, key, value):
        value.__name__ = key
        value.__parent__ = self
        self.data[key] = value


class DemoKeyReference(object):
    _class_counter = 0
    interface.implements(zope.app.keyreference.interfaces.IKeyReference)

    def __init__(self, context):
        self.context = context
        class_ = type(self)
        self._id = getattr(context, "__demo_key_reference__", None)
        if self._id is None:
            self._id = class_._class_counter
            context.__demo_key_reference__ = self._id
            class_._class_counter += 1

    key_type_id = "zope.app.dav.lockingutils.DemoKeyReference"

    def __call__(self):
        return self.context

    def __hash__(self):
        return (self.key_type_id, self._id)

    def __cmp__(self, other):
        if self.key_type_id == other.key_type_id:
            return cmp(self._id, other._id)
        return cmp(self.key_type_id, other.key_type_id)


class DemoAbsoluteURL(object):
    interface.implements(IAbsoluteURL)

    def __init__(self, context, request):
        self.context = context

    def __str__(self):
        ob = self.context
        url = ""
        while ob is not None:
            url += "/dummy"
            ob = ob.__parent__
        if IDemoFolder.providedBy(self.context):
            url += "/"
        return url

    __call__ = __str__


def contentSetup(test):
    test.globs["Demo"] = Demo
    test.globs["DemoFolder"] = DemoFolder


def contentTeardown(test):
    del test.globs["Demo"]
    del test.globs["DemoFolder"]


def lockingSetUp(test):
    placelesssetup.setUp(test)
    zope.etree.testing.etreeSetup(test)

    # create principal
    participation = Participation(Principal('michael'))
    if queryInteraction() is not None:
        queryInteraction().add(participation)
    else:
        newInteraction(participation)

    events = test.globs["events"] = []
    zope.event.subscribers.append(events.append)

    gsm = component.getGlobalSiteManager()

    gsm.registerAdapter(DemoKeyReference,
                        (IDemo,),
                        zope.app.keyreference.interfaces.IKeyReference)
    gsm.registerAdapter(DemoKeyReference, (IDemoFolder,),
                        zope.app.keyreference.interfaces.IKeyReference)
    gsm.registerAdapter(SiteManagerAdapter,
                        (interface.Interface,), IComponentLookup)
    gsm.registerAdapter(DemoAbsoluteURL,
                        (IDemo, interface.Interface),
                        IAbsoluteURL)
    gsm.registerAdapter(DemoAbsoluteURL,
                        (IDemoFolder, interface.Interface),
                        IAbsoluteURL)

    # register some IDAVWidgets so that we can render the activelock and
    # supportedlock widgets.
    gsm.registerAdapter(zope.webdav.widgets.ListDAVWidget,
                        (zope.schema.interfaces.IList,
                         zope.webdav.interfaces.IWebDAVRequest))
    gsm.registerAdapter(zope.webdav.widgets.ObjectDAVWidget,
                        (zope.schema.interfaces.IObject,
                         zope.webdav.interfaces.IWebDAVRequest))
    gsm.registerAdapter(zope.webdav.widgets.TextDAVWidget,
                        (zope.schema.interfaces.IText,
                         zope.webdav.interfaces.IWebDAVRequest))
    gsm.registerAdapter(zope.webdav.properties.OpaqueWidget,
                        (zope.webdav.properties.DeadField,
                         zope.webdav.interfaces.IWebDAVRequest))
    gsm.registerAdapter(zope.webdav.widgets.TextDAVWidget,
                        (zope.schema.interfaces.IURI,
                         zope.webdav.interfaces.IWebDAVRequest))

    # expose these classes to the test
    test.globs["Demo"] = Demo
    test.globs["DemoFolder"] = DemoFolder


def lockingTearDown(test):
    placelesssetup.tearDown(test)
    zope.etree.testing.etreeTearDown(test)

    events = test.globs.pop("events")
    assert zope.event.subscribers.pop().__self__ is events
    del events[:] # being paranoid

    del test.globs["Demo"]
    del test.globs["DemoFolder"]

    gsm = component.getGlobalSiteManager()

    gsm.unregisterAdapter(DemoKeyReference,
                          (IDemo,),
                          zope.app.keyreference.interfaces.IKeyReference)
    gsm.unregisterAdapter(DemoKeyReference, (IDemoFolder,),
                          zope.app.keyreference.interfaces.IKeyReference)
    gsm.unregisterAdapter(SiteManagerAdapter,
                          (interface.Interface,), IComponentLookup)
    gsm.unregisterAdapter(DemoAbsoluteURL,
                          (IDemo, interface.Interface), IAbsoluteURL)
    gsm.unregisterAdapter(DemoAbsoluteURL,
                          (IDemoFolder, interface.Interface),
                          IAbsoluteURL)

    gsm.unregisterAdapter(zope.webdav.widgets.ListDAVWidget,
                          (zope.schema.interfaces.IList,
                           zope.webdav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(zope.webdav.widgets.ObjectDAVWidget,
                          (zope.schema.interfaces.IObject,
                           zope.webdav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(zope.webdav.widgets.TextDAVWidget,
                          (zope.schema.interfaces.IText,
                           zope.webdav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(zope.webdav.properties.OpaqueWidget,
                          (zope.webdav.properties.DeadField,
                           zope.webdav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(zope.webdav.widgets.TextDAVWidget,
                          (zope.schema.interfaces.IURI,
                           zope.webdav.interfaces.IWebDAVRequest))

    endInteraction()


def test_suite():
    return unittest.TestSuite((
        doctest.DocTestSuite("zope.webdav.properties",
                             setUp = contentSetup, tearDown = contentTeardown),
        doctest.DocTestSuite("zope.webdav.utils",
                             checker = zope.etree.testing.xmlOutputChecker,
                             setUp = zope.etree.testing.etreeSetup,
                             tearDown = zope.etree.testing.etreeTearDown),
        doctest.DocTestSuite("zope.webdav.coreproperties",
                             checker = zope.etree.testing.xmlOutputChecker,
                             setUp = zope.etree.testing.etreeSetup,
                             tearDown = zope.etree.testing.etreeTearDown),
        doctest.DocFileSuite("datamodel.txt", package = "zope.webdav",
                             checker = zope.etree.testing.xmlOutputChecker,
                             setUp = zope.etree.testing.etreeSetup,
                             tearDown = zope.etree.testing.etreeTearDown),
        doctest.DocTestSuite("zope.webdav.lockingutils",
                             checker = zope.etree.testing.xmlOutputChecker,
                             setUp = lockingSetUp,
                             tearDown = lockingTearDown),
        doctest.DocTestSuite("zope.webdav.deadproperties"),
        doctest.DocTestSuite("zope.webdav.adapters"),
        doctest.DocTestSuite("zope.webdav.locking",
                             checker = zope.etree.testing.xmlOutputChecker,
                             setUp = zope.etree.testing.etreeSetup,
                             tearDown = zope.etree.testing.etreeTearDown),
        doctest.DocFileSuite("locking.txt", package = "zope.webdav",
                             checker = zope.etree.testing.xmlOutputChecker,
                             setUp = zope.etree.testing.etreeSetup,
                             tearDown = zope.etree.testing.etreeTearDown),
        doctest.DocTestSuite("zope.webdav.mkcol"),
        ))
