##############################################################################
#
# Copyright (c) 2006 Zope Foundation and Contributors.
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
"""Run all doctests contained within z3c.dav.

$Id$
"""
import unittest
import UserDict

from zope.testing import doctest

from zope import component
from zope import interface
from zope.annotation.interfaces import IAttributeAnnotatable
from zope.app.container.interfaces import IContained, IContainer

import z3c.etree.testing


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


def contentSetup(test):
    z3c.etree.testing.etreeSetup(test)
    test.globs["Demo"] = Demo
    test.globs["DemoFolder"] = DemoFolder


def contentTeardown(test):
    z3c.etree.testing.etreeTearDown(test)
    del test.globs["Demo"]
    del test.globs["DemoFolder"]


def test_suite():
    return unittest.TestSuite((
        doctest.DocTestSuite("z3c.dav.properties",
                             checker = z3c.etree.testing.xmlOutputChecker,
                             setUp = contentSetup,
                             tearDown = contentTeardown),
        doctest.DocTestSuite("z3c.dav.utils",
                             checker = z3c.etree.testing.xmlOutputChecker,
                             setUp = z3c.etree.testing.etreeSetup,
                             tearDown = z3c.etree.testing.etreeTearDown),
        doctest.DocTestSuite("z3c.dav.coreproperties",
                             checker = z3c.etree.testing.xmlOutputChecker,
                             setUp = z3c.etree.testing.etreeSetup,
                             tearDown = z3c.etree.testing.etreeTearDown),
        doctest.DocFileSuite("datamodel.txt", package = "z3c.dav",
                             checker = z3c.etree.testing.xmlOutputChecker,
                             setUp = z3c.etree.testing.etreeSetup,
                             tearDown = z3c.etree.testing.etreeTearDown),
        doctest.DocTestSuite("z3c.dav.adapters"),
        doctest.DocTestSuite("z3c.dav.locking",
                             checker = z3c.etree.testing.xmlOutputChecker,
                             setUp = z3c.etree.testing.etreeSetup,
                             tearDown = z3c.etree.testing.etreeTearDown),
        doctest.DocFileSuite("locking.txt", package = "z3c.dav",
                             checker = z3c.etree.testing.xmlOutputChecker,
                             setUp = z3c.etree.testing.etreeSetup,
                             tearDown = z3c.etree.testing.etreeTearDown),
        doctest.DocTestSuite("z3c.dav.mkcol"),
        doctest.DocTestSuite("z3c.dav.testing",
                             checker = z3c.etree.testing.xmlOutputChecker,
                             setUp = z3c.etree.testing.etreeSetup,
                             tearDown = z3c.etree.testing.etreeTearDown),
        doctest.DocTestSuite("z3c.dav.ifvalidator"),
        ))
