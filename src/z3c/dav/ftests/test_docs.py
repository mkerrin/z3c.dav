##############################################################################
#
# Copyright (c) 2008 Zope Foundation and Contributors.
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

import unittest
import doctest

import z3c.etree.testing
import z3c.dav.testing
import z3c.dav

def test_suite():
    properties = doctest.DocFileSuite(
        "zopefolder.txt",
        setUp = z3c.dav.testing.functionalSetUp,
        tearDown = z3c.dav.testing.functionalTearDown,
        checker = z3c.etree.testing.xmlOutputChecker,
        )
    properties.layer = z3c.dav.testing.WebDAVLayer(z3c.dav)

    return unittest.TestSuite((
        properties,
        ))
