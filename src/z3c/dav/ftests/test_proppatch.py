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
"""Collection of functional tests for PROPFIND z3c.dav

$Id$
"""

import urllib
import unittest
from cStringIO import StringIO
import transaction

from zope import component
from zope.dublincore.interfaces import IZopeDublinCore

import dav

import z3c.dav.interfaces
from z3c.dav.publisher import WebDAVRequest
from z3c.etree.testing import assertXMLEqual

class PROPPATCHTestCase(dav.DAVTestCase):

    def test_badcontent(self):
        response = self.publish("/", env = {"REQUEST_METHOD": "PROPPATCH"},
                                request_body = "some content",
                                handle_errors = True)
        self.assertEqual(response.getStatus(), 400)
        self.assert_(
            "All PROPPATCH requests needs a XML body" in response.getBody())

    def test_invalidxml_nopropertyupdate_elem(self):
        body = """<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:">
  <D:prop />
</D:propfind>
        """
        response = self.publish("/", env = {"REQUEST_METHOD": "PROPPATCH",
                                            "CONTENT_TYPE": "application/xml",
                                            "CONTENT_LENGTH": len(body)},
                                request_body = body,
                                handle_errors = True)

        self.assertEqual(response.getStatus(), 422)
        self.assertEqual(response.getBody(), "")

    def test_setdisplayname_unauthorized(self):
        self.addResource("/r", "some content", title = u"Test Resource")
        body = """<?xml version="1.0" encoding="utf-8" ?>
<D:propertyupdate xmlns:D="DAV:" xmlns="DAV:">
  <D:set><D:prop>
    <D:displayname>Test File</D:displayname>
  </D:prop></D:set>
</D:propertyupdate>"""

        response = self.publish("/r", env = {"REQUEST_METHOD": "PROPPATCH",
                                             "CONTENT_TYPE": "application/xml",
                                             "CONTENT_LENGTH": len(body)},
                                request_body = body,
                                handle_errors = True)

        # we need to be logged in to set the DAV:displayname property.
        self.assertEqual(response.getStatus(), 401)
        self.assertEqual(
            response.getHeader("WWW-Authenticate", literal = True),
            'basic realm="Zope"')

    def test_setdisplayname(self):
        set_properties = "<D:displayname>Test File</D:displayname>"
        self.addResource("/r", "some content", title = u"Test Resource")

        httpresponse = self.checkProppatch(
            "/r", basic = "mgr:mgrpw", set_properties = set_properties)

        self.assertEqual(len(httpresponse.getMSResponses()), 1)
        assertXMLEqual('<displayname xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r", "{DAV:}displayname"))

        title = IZopeDublinCore(self.getRootFolder()["r"]).title
        self.assertEqual(title, u"Test File")

    def test_readonly_property(self):
        set_properties = "<D:getcontentlength>10</D:getcontentlength>"
        self.addResource("/r", "some file content", title = u"Test Resource")

        httpresponse = self.checkProppatch(
            "/r", basic = "mgr:mgrpw", set_properties = set_properties)

        self.assertEqual(len(httpresponse.getMSResponses()), 1)
        assertXMLEqual(
            '<getcontentlength xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r", "{DAV:}getcontentlength", status = 403))

    def test_badinput(self):
        set_properties = """
        <E:exampleintprop xmlns:E="DAVtest:">BAD INT</E:exampleintprop>
        """
        resource = self.addResource("/testresource", "some resource content")

        httpresponse = self.checkProppatch(
            "/testresource", basic = "mgr:mgrpw",
            set_properties = set_properties)

        self.assertEqual(len(httpresponse.getMSResponses()), 1)
        assertXMLEqual(
            '<exampleintprop xmlns="DAVtest:" />',
            httpresponse.getMSProperty(
                "http://localhost/testresource", "{DAVtest:}exampleintprop",
                status = 409))

    def test_badinput_plus_faileddep(self):
        set_properties = """
        <E:exampleintprop xmlns:E="DAVtest:">BAD INT</E:exampleintprop>
        <E:exampletextprop xmlns:E="DAVtest:">
          Test Property
        </E:exampletextprop>
        """
        resource = self.addResource("/testresource", "some resource content")

        request = WebDAVRequest(StringIO(""), {})
        exampleStorage = component.getMultiAdapter((resource, request),
                                                   dav.IExamplePropertyStorage)
        # set up a default value to test later
        exampleStorage.exampletextprop = u"Example Text Property"
        transaction.commit()

        httpresponse = self.checkProppatch(
            "/testresource", basic = "mgr:mgrpw",
            set_properties = set_properties)

        self.assertEqual(len(httpresponse.getMSResponses()), 1)
        assertXMLEqual(
            '<exampletextprop xmlns="DAVtest:" />',
            httpresponse.getMSProperty(
                "http://localhost/testresource", "{DAVtest:}exampletextprop",
                status = 424))
        assertXMLEqual(
            '<exampleintprop xmlns="DAVtest:" />',
            httpresponse.getMSProperty(
                "http://localhost/testresource", "{DAVtest:}exampleintprop",
                status = 409))

        exampleStorage = component.getMultiAdapter((resource, request),
                                                   dav.IExamplePropertyStorage)
        self.assertEqual(exampleStorage.exampletextprop,
                         u"Example Text Property")

    def test_proppatch_opaqueproperty(self):
        set_properties = """<Z:Author xmlns:Z="http://ns.example.com/z39.50/">
Jim Whitehead
</Z:Author>
        """
        file = self.addResource("/r", "some content",
                                title = u"Test Resource")

        httpresponse = self.checkProppatch(
            "/r", basic = "mgr:mgrpw", set_properties = set_properties)

        opaqueProperties = z3c.dav.interfaces.IOpaquePropertyStorage(file)
        self.assertEqual(opaqueProperties.hasProperty(
            "{http://ns.example.com/z39.50/}Author"), True)
        assertXMLEqual(opaqueProperties.getProperty(
            "{http://ns.example.com/z39.50/}Author"),
            """<Z:Author xmlns:Z="http://ns.example.com/z39.50/">
Jim Whitehead
</Z:Author>""")

    def test_set_multiple_dead_props(self):
        set_properties = """<E:prop0 xmlns:E="example:">PROP0</E:prop0>
<E:prop1 xmlns:E="example:">PROP0</E:prop1>
<E:prop2 xmlns:E="example:">PROP0</E:prop2>
<E:prop3 xmlns:E="example:">PROP0</E:prop3>
        """

        file = self.addResource("/r", "some content", title = u"Test Resource")

        httpresponse = self.checkProppatch(
            "/r", basic = "mgr:mgrpw", set_properties = set_properties)

        opaqueProperties = z3c.dav.interfaces.IOpaquePropertyStorage(file)
        allprops = [tag for tag in opaqueProperties.getAllProperties()]
        allprops.sort()
        self.assertEqual(allprops, ["{example:}prop0", "{example:}prop1",
                                    "{example:}prop2", "{example:}prop3"])

    def test_unicode_title(self):
        teststr = u"copyright \xa9 me"
        set_properties = "<D:displayname>%s</D:displayname>" % teststr
        self.addResource("/r", "some content", title = u"Test Resource")

        httpresponse = self.checkProppatch(
            "/r", basic = "mgr:mgrpw", set_properties = set_properties)

        self.assertEqual(len(httpresponse.getMSResponses()), 1)
        assertXMLEqual(
            '<displayname xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r", "{DAV:}displayname"))

    def test_remove_live_prop(self):
        file = self.addResource("/r", "some content", title = u"Test Resource")

        opaqueProperties = z3c.dav.interfaces.IOpaquePropertyStorage(file)
        opaqueProperties.setProperty("{deadprop:}deadprop",
                                     """<X:deadprop xmlns:X="deadprop:">
This is a dead property.</X:deadprop>""")
        transaction.commit()

        httpresponse = self.checkProppatch(
            "/r", basic = "mgr:mgrpw",
            remove_properties = """<E:exampleintprop xmlns:E="DAVtest:" />""")

        self.assertEqual(len(httpresponse.getMSResponses()), 1)

        assertXMLEqual(
            '<exampleintprop xmlns="DAVtest:" />',
            httpresponse.getMSProperty(
                "http://localhost/r", "{DAVtest:}exampleintprop",
                status = 409))

    def test_remove_dead_prop(self):
        proptag = "{deadprop:}deadprop"
        file = self.addResource("/r", "some content", title = u"Test Resource")

        opaqueProperties = z3c.dav.interfaces.IOpaquePropertyStorage(file)
        opaqueProperties.setProperty(proptag,
                                     """<X:deadprop xmlns:X="deadprop:">
This is a dead property.</X:deadprop>""")
        transaction.commit()

        httpresponse = self.checkProppatch(
            "/r", basic = "mgr:mgrpw",
            remove_properties = """<X:deadprop xmlns:X="deadprop:" />""")

        self.assertEqual(len(httpresponse.getMSResponses()), 1)
        assertXMLEqual(
            '<deadprop xmlns="deadprop:" />',
            httpresponse.getMSProperty(
                "http://localhost/r", "{deadprop:}deadprop"))

        opaqueProperties = z3c.dav.interfaces.IOpaquePropertyStorage(file)
        self.assertEqual(opaqueProperties.hasProperty(proptag), False)

    def test_setting_unicode_title(self):
        teststr = u"copyright \xa9 me"
        self.addResource(u"/" + teststr, "some file content",
                         title = u"Old title")

        httpresponse = self.checkProppatch(
            "/" + teststr.encode("utf-8"), basic = "mgr:mgrpw",
            set_properties = "<D:displayname>%s</D:displayname>" % teststr)

        self.assertEqual(len(httpresponse.getMSResponses()), 1)
        assertXMLEqual(
            '<displayname xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/%s" % urllib.quote(teststr.encode("utf-8")),
                "{DAV:}displayname"))

        resourcetitle = IZopeDublinCore(self.getRootFolder()[teststr]).title
        self.assertEqual(resourcetitle, teststr)


def test_suite():
    return unittest.TestSuite((
            unittest.makeSuite(PROPPATCHTestCase),
            ))

if __name__ == "__main__":
    unittest.main(defaultTest = "test_suite")
