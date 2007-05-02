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
"""Test the multistatus views.

$Id$
"""
__docformat__ = 'restructuredtext'

import unittest
from cStringIO import StringIO

from zope import interface
from zope.interface.verify import verifyObject
from zope import schema
from zope import component
from zope.traversing.browser.interfaces import IAbsoluteURL

import z3c.dav.publisher
from z3c.etree.testing import etreeSetup, etreeTearDown, assertXMLEqual

class IResource(interface.Interface):

    text = schema.TextLine(
        title = u"Example Text Property")

    intprop = schema.Int(
        title = u"Example Int Property")


class Resource(object):
    interface.implements(IResource)

    def __init__(self, text = u"", intprop = 0):
        self.text = text
        self.intprop = intprop


class DummyResourceURL(object):
    interface.implements(IAbsoluteURL)

    def __init__(self, context, request):
        self.context = context

    def __str__(self):
        if getattr(self.context, "__parent__", None) is not None:
            path = DummyResourceURL(self.context.__parent__, None)()
        else:
            path = ""

        if getattr(self.context, "__name__", None) is not None:
            path += "/" + self.context.__name__
        elif IResource.providedBy(self.context):
            path += "/resource"
##         elif ICollection.providedBy(self.context):
##             path += "/collection"
        else:
            raise ValueError("unknown context type")

        return path

    __call__ = __str__


class TestRequest(z3c.dav.publisher.WebDAVRequest):

    def __init__(self, properties = None, environ = {}):
        if properties is not None:
            body = """<?xml version="1.0" encoding="utf-8" ?>
<propfind xmlns:D="DAV:" xmlns="DAV:">
  %s
</propfind>
""" % properties
        else:
            body = ""

        env = environ.copy()
        env.setdefault("REQUEST_METHOD", "PROPFIND")
        env.setdefault("CONTENT_TYPE", "text/xml")
        env.setdefault("CONTENT_LENGTH", len(body))

        super(TestRequest, self).__init__(StringIO(body), env)

        # call processInputs now since we are in a unit test.
        self.processInputs()


class TestPropstatErrorView(unittest.TestCase):

    def setUp(self):
        super(TestPropstatErrorView, self).setUp()

        etreeSetup()

        gsm = component.getGlobalSiteManager()
        gsm.registerAdapter(DummyResourceURL,
                            (IResource, z3c.dav.interfaces.IWebDAVRequest))
        gsm.registerAdapter(z3c.dav.exceptions.ForbiddenError,
                            (z3c.dav.interfaces.IForbiddenError,
                             z3c.dav.interfaces.IWebDAVRequest))

    def tearDown(self):
        super(TestPropstatErrorView, self).tearDown()

        etreeTearDown()

        gsm = component.getGlobalSiteManager()
        gsm.unregisterAdapter(DummyResourceURL,
                              (IResource,
                               z3c.dav.interfaces.IWebDAVRequest))
        gsm.unregisterAdapter(z3c.dav.exceptions.ForbiddenError,
                              (z3c.dav.interfaces.IForbiddenError,
                               z3c.dav.interfaces.IWebDAVRequest))

    def test_propstat_interface(self):
        resource = Resource()
        error = z3c.dav.interfaces.WebDAVPropstatErrors(resource)
        self.assertEqual(
            verifyObject(z3c.dav.interfaces.IWebDAVPropstatErrors, error),
            True)

    def test_propstat_simple_errors(self):
        resource = Resource()
        error = z3c.dav.interfaces.WebDAVPropstatErrors(resource)
        error["{DAV:}displayname"] = z3c.dav.interfaces.ForbiddenError(
            resource, "{DAV:}displayname", message = u"readonly field")
        request = TestRequest()

        view = z3c.dav.exceptions.WebDAVPropstatErrorView(error, request)
        result = view()

        self.assertEqual(request.response.getStatus(), 207)
        self.assertEqual(request.response.getHeader("content-type"), "application/xml")
        assertXMLEqual(result, """<ns0:multistatus xmlns:ns0="DAV:">
<ns0:response>
  <ns0:href>/resource</ns0:href>
  <ns0:propstat>
    <ns0:prop>
      <ns0:displayname />
    </ns0:prop>
    <ns0:status>HTTP/1.1 403 Forbidden</ns0:status>
  </ns0:propstat>
</ns0:response></ns0:multistatus>""")


class TestMSErrorView(unittest.TestCase):

    def setUp(self):
        super(TestMSErrorView, self).setUp()

        etreeSetup()

        gsm = component.getGlobalSiteManager()
        gsm.registerAdapter(DummyResourceURL,
                            (IResource, z3c.dav.interfaces.IWebDAVRequest))
        gsm.registerAdapter(z3c.dav.exceptions.ForbiddenError,
                            (z3c.dav.interfaces.IForbiddenError,
                             z3c.dav.interfaces.IWebDAVRequest))
        gsm.registerAdapter(z3c.dav.exceptions.PropertyNotFoundError,
                            (z3c.dav.interfaces.IPropertyNotFound,
                             z3c.dav.interfaces.IWebDAVRequest))

    def tearDown(self):
        super(TestMSErrorView, self).tearDown()

        etreeTearDown()

        gsm = component.getGlobalSiteManager()
        gsm.unregisterAdapter(DummyResourceURL,
                              (IResource,
                               z3c.dav.interfaces.IWebDAVRequest))
        gsm.unregisterAdapter(z3c.dav.exceptions.ForbiddenError,
                              (z3c.dav.interfaces.IForbiddenError,
                               z3c.dav.interfaces.IWebDAVRequest))
        gsm.unregisterAdapter(z3c.dav.exceptions.PropertyNotFoundError,
                              (z3c.dav.interfaces.IPropertyNotFound,
                               z3c.dav.interfaces.IWebDAVRequest))

    def test_multi_resource_error_interface(self):
        resource = Resource()
        error = z3c.dav.interfaces.WebDAVErrors(resource)
        self.assertEqual(
            verifyObject(z3c.dav.interfaces.IWebDAVErrors, error), True)

    def test_multi_resource_error(self):
        resource = Resource()
        error = z3c.dav.interfaces.WebDAVErrors(resource)
        error.append(z3c.dav.interfaces.ForbiddenError(
            resource, "{DAV:}displayname", message = u"readonly field"))
        request = TestRequest()

        view = z3c.dav.exceptions.MultiStatusErrorView(error, request)
        result = view()

        self.assertEqual(request.response.getStatus(), 207)
        self.assertEqual(request.response.getHeader("content-type"),
                         "application/xml")

        assertXMLEqual(result, """<ns0:multistatus xmlns:ns0="DAV:">
<ns0:response>
  <ns0:href>/resource</ns0:href>
  <ns0:status>HTTP/1.1 403 Forbidden</ns0:status>
</ns0:response></ns0:multistatus>""")

    def test_simple_seen_context(self):
        resource = Resource()
        resource1 = Resource()
        resource1.__name__ = "secondresource"
        error = z3c.dav.interfaces.WebDAVErrors(resource)
        error.append(z3c.dav.interfaces.ForbiddenError(
            resource, "{DAV:}displayname", message = u"readonly field"))
        error.append(z3c.dav.interfaces.PropertyNotFound(
            resource1, "{DAV:}getcontentlength", message = u"readonly field"))
        request = TestRequest()

        view = z3c.dav.exceptions.MultiStatusErrorView(error, request)
        result = view()

        self.assertEqual(request.response.getStatus(), 207)
        self.assertEqual(request.response.getHeader("content-type"),
                         "application/xml")

        assertXMLEqual(result, """<ns0:multistatus xmlns:ns0="DAV:">
<ns0:response>
  <ns0:href>/resource</ns0:href>
  <ns0:status>HTTP/1.1 403 Forbidden</ns0:status>
</ns0:response>
<ns0:response>
  <ns0:href>/secondresource</ns0:href>
  <ns0:status>HTTP/1.1 404 Not Found</ns0:status>
</ns0:response></ns0:multistatus>""")

    def test_simple_not_seen_context(self):
        # multi-status responses should contain a entry for the context
        # corresponding to the request-uri.
        resource = Resource()
        resource1 = Resource()
        resource1.__name__ = "secondresource"
        error = z3c.dav.interfaces.WebDAVErrors(resource)
        error.append(z3c.dav.interfaces.PropertyNotFound(
            resource1, "{DAV:}getcontentlength", message = u"readonly field"))
        request = TestRequest()

        view = z3c.dav.exceptions.MultiStatusErrorView(error, request)
        result = view()

        self.assertEqual(request.response.getStatus(), 207)
        self.assertEqual(request.response.getHeader("content-type"),
                         "application/xml")

        assertXMLEqual(result, """<ns0:multistatus xmlns:ns0="DAV:">
<ns0:response>
  <ns0:href>/secondresource</ns0:href>
  <ns0:status>HTTP/1.1 404 Not Found</ns0:status>
</ns0:response>
<ns0:response>
  <ns0:href>/resource</ns0:href>
  <ns0:status>HTTP/1.1 424 Failed Dependency</ns0:status>
</ns0:response></ns0:multistatus>""")


def test_suite():
    suite = unittest.TestSuite((
        unittest.makeSuite(TestPropstatErrorView),
        unittest.makeSuite(TestMSErrorView),
        ))
    return suite
