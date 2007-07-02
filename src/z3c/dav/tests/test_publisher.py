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
"""Test utility for interfacing with the zope.locking package from ZC

$Id$
"""

import unittest
import types
from cStringIO import StringIO

from zope.interface.verify import verifyObject

from z3c.dav.publisher import WebDAVRequest
from z3c.dav.interfaces import IWebDAVRequest, IWebDAVResponse, BadRequest

from z3c.etree.testing import etreeSetup
from z3c.etree.testing import etreeTearDown

def create_request(body = None, env = {}):
    if isinstance(body, types.StringTypes):
        body = StringIO(body)
    elif body is None:
        body = StringIO('')
    return WebDAVRequest(body, env)


class TestWebDAVPublisher(unittest.TestCase):

    def setUp(self):
        self.etree = etreeSetup()

    def tearDown(self):
        etreeTearDown()

    def test_noinput(self):
        request = create_request()
        self.assert_(verifyObject(IWebDAVRequest, request))
        self.assertEqual(request.content_type, None)
        self.assertEqual(request.xmlDataSource, None)

    def test_textinput(self):
        body = "This is some text"
        request = create_request(body, {"CONTENT_TYPE": "text/plain",
                                        "CONTENT_LENGTH": len(body)})
        request.processInputs()
        self.assertEqual(request.content_type, "text/plain")
        self.assertEqual(request.xmlDataSource, None)

    def test_unicodeInput(self):
        body = "This is some text"
        request = create_request(body,
                                 {"CONTENT_TYPE": "text/plain;charset=cp1252",
                                  "CONTENT_LENGTH": len(body)})
        request.processInputs()
        self.assertEqual(request.content_type, "text/plain")
        self.assertEqual(request.xmlDataSource, None)

    def test_textxml(self):
        body = """<?xml version="1.0" encoding="utf-8" ?>
        <somedoc>This is some xml document</somedoc>
        """
        request = create_request(body, {"CONTENT_TYPE": "text/xml",
                                        "CONTENT_LENGTH": len(body)})
        request.processInputs()

        self.assertEqual(request.content_type, "text/xml")
        self.assert_(request.xmlDataSource is not None)

    def test_applicationxml(self):
        body = """<?xml version="1.0" encoding="utf-8" ?>
        <somedoc>This is some xml document</somedoc>
        """
        request = create_request(body, {"CONTENT_TYPE": "application/xml",
                                        "CONTENT_LENGTH": len(body)})
        request.processInputs()

        self.assertEqual(request.content_type, "application/xml")
        self.assert_(request.xmlDataSource is not None)

    def test_xml_nobody(self):
        request = create_request("", {"CONTENT_TYPE": "text/xml"})
        request.processInputs()
        self.assertEqual(request.xmlDataSource, None)

    def test_response(self):
        request = create_request()
        self.assert_(verifyObject(IWebDAVResponse, request.response))

    def test_nonxmlbody_type(self):
        body = """<?xml version="1.0" encoding="utf-8" ?>
        <somedoc>Bad End Tag</anotherdoc>
        """
        request = create_request(body, {"CONTENT_TYPE": "application/badxml",
                                        "CONTENT_LENGTH": len(body)})
        request.processInputs()

        self.assertEqual(request.content_type, "application/badxml")
        self.assertEqual(request.xmlDataSource, None)

    def test_invalidxml(self):
        body = """<?xml version="1.0" encoding="utf-8" ?>
        <somedoc>Bad End Tag</anotherdoc>
        """
        request = create_request(body, {"CONTENT_TYPE": "application/xml",
                                        "CONTENT_LENGTH": len(body)})
        self.assertRaises(BadRequest, request.processInputs)
        self.assertEqual(request.content_type, None)

    def test_contentLength(self):
        request = create_request("", {"CONTENT_TYPE": "text/xml",
                                      "CONTENT_LENGTH": "0"})
        request.processInputs()

        self.assertEqual(request.content_type, "text/xml")
        self.assertEqual(request.xmlDataSource, None)

    def test_contentLength2(self):
        body = """<?xml version="1.0" encoding="utf-8" ?>
        <somedoc>This is some xml document</somedoc>
        """
        request = create_request(body, {"CONTENT_TYPE": "text/xml",
                                        "CONTENT_LENGTH": str(len(body))})
        request.processInputs()

        self.assertEqual(request.content_type, "text/xml")
        self.assert_(request.xmlDataSource is not None)


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(TestWebDAVPublisher),
        ))
