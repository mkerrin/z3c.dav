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
"""Collection of functional tests for PROPFIND z3c.dav
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
        self.addCollection("/coll", title = u"Test collection")
        body = """<?xml version="1.0" encoding="utf-8" ?>
<D:propertyupdate xmlns:D="DAV:" xmlns="DAV:">
  <D:set><D:prop>
    <D:displayname>Big collection</D:displayname>
  </D:prop></D:set>
</D:propertyupdate>"""

        response = self.publish("/coll",
                                env = {"REQUEST_METHOD": "PROPPATCH",
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
        set_properties = "<D:displayname>Big collection</D:displayname>"
        self.addCollection("/coll", title = u"Test collection")

        httpresponse = self.checkProppatch(
            "/coll", basic = "mgr:mgrpw", set_properties = set_properties)

        assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/coll/</href>
  <propstat>
    <prop>
      <displayname />
    </prop>
    <status>HTTP/1.1 200 Ok</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

        title = IZopeDublinCore(self.getRootFolder()["coll"]).title
        self.assertEqual(title, u"Big collection")

    def test_readonly_property(self):
        set_properties = "<D:resourcetype><D:collection /></D:resourcetype>"
        self.addCollection("/coll", title = u"Test collection")

        httpresponse = self.checkProppatch(
            "/coll/", basic = "mgr:mgrpw", set_properties = set_properties)

        assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/coll/</href>
  <propstat>
    <prop>
      <resourcetype />
    </prop>
    <status>HTTP/1.1 403 Forbidden</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

    def test_badinput(self):
        set_properties = """
        <E:exampleintprop xmlns:E="DAVtest:">BAD INT</E:exampleintprop>
        """
        self.addCollection("/coll")

        httpresponse = self.checkProppatch(
            "/coll", basic = "mgr:mgrpw",
            set_properties = set_properties)

        assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/coll/</href>
  <propstat>
    <prop>
      <ns1:exampleintprop xmlns:ns1="DAVtest:" />
    </prop>
    <status>HTTP/1.1 409 Conflict</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

    def test_badinput_plus_faileddep(self):
        set_properties = """
        <E:exampleintprop xmlns:E="DAVtest:">BAD INT</E:exampleintprop>
        <E:exampletextprop xmlns:E="DAVtest:">
          Test Property
        </E:exampletextprop>
        """
        coll = self.addCollection("/coll")

        request = WebDAVRequest(StringIO(""), {})
        exampleStorage = component.getMultiAdapter((coll, request),
                                                   dav.IExamplePropertyStorage)
        # set up a default value to test later
        exampleStorage.exampletextprop = u"Example Text Property"
        transaction.commit()

        httpresponse = self.checkProppatch(
            "/coll", basic = "mgr:mgrpw",
            set_properties = set_properties)

        assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/coll/</href>
  <propstat>
    <prop>
      <ns1:exampletextprop xmlns:ns1="DAVtest:" />
    </prop>
    <status>HTTP/1.1 424 Failed Dependency</status>
  </propstat>
  <propstat>
    <prop>
      <ns1:exampleintprop xmlns:ns1="DAVtest:" />
    </prop>
    <status>HTTP/1.1 409 Conflict</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

        exampleStorage = component.getMultiAdapter((coll, request),
                                                   dav.IExamplePropertyStorage)
        self.assertEqual(exampleStorage.exampletextprop,
                         u"Example Text Property")

    def test_proppatch_opaqueproperty(self):
        set_properties = """<Z:Author xmlns:Z="http://ns.example.com/z39.50/">
Jim Whitehead
</Z:Author>
        """
        coll = self.addCollection("/coll", title = u"Test collection")

        httpresponse = self.checkProppatch(
            "/coll", basic = "mgr:mgrpw", set_properties = set_properties)

        assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/coll/</href>
  <propstat>
    <prop>
      <ns1:Author xmlns:ns1="http://ns.example.com/z39.50/" />
    </prop>
    <status>HTTP/1.1 200 Ok</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

        opaqueProperties = z3c.dav.interfaces.IOpaquePropertyStorage(coll)
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

        coll = self.addCollection("/coll", title = u"Test collection")

        httpresponse = self.checkProppatch(
            "/coll", basic = "mgr:mgrpw", set_properties = set_properties)

        assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/coll/</href>
  <propstat>
    <prop>
      <ns1:prop0 xmlns:ns1="example:" />
      <ns1:prop1 xmlns:ns1="example:" />
      <ns1:prop2 xmlns:ns1="example:" />
      <ns1:prop3 xmlns:ns1="example:" />
    </prop>
    <status>HTTP/1.1 200 Ok</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

        opaqueProperties = z3c.dav.interfaces.IOpaquePropertyStorage(coll)
        allprops = [tag for tag in opaqueProperties.getAllProperties()]
        allprops.sort()
        self.assertEqual(allprops, ["{example:}prop0", "{example:}prop1",
                                    "{example:}prop2", "{example:}prop3"])

    def test_unicode_title(self):
        teststr = u"copyright \xa9 me"
        set_properties = "<D:displayname>%s</D:displayname>" % teststr
        coll = self.addCollection("/coll", title = u"Test Resource")

        httpresponse = self.checkProppatch(
            "/coll", basic = "mgr:mgrpw", set_properties = set_properties)

        assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/coll/</href>
  <propstat>
    <prop>
      <displayname />
    </prop>
    <status>HTTP/1.1 200 Ok</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

        self.assertEqual(IZopeDublinCore(coll).title, teststr)

    def test_remove_live_prop(self):
        coll = self.addCollection("/coll", title = u"Test collection")

        opaqueProperties = z3c.dav.interfaces.IOpaquePropertyStorage(coll)
        opaqueProperties.setProperty("{deadprop:}deadprop",
                                     """<X:deadprop xmlns:X="deadprop:">
This is a dead property.</X:deadprop>""")
        transaction.commit()

        httpresponse = self.checkProppatch(
            "/coll", basic = "mgr:mgrpw",
            remove_properties = """<E:exampleintprop xmlns:E="DAVtest:" />""")

        assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/coll/</href>
  <propstat>
    <prop>
      <ns1:exampleintprop xmlns:ns1="DAVtest:" />
    </prop>
    <status>HTTP/1.1 409 Conflict</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

    def test_remove_dead_prop(self):
        proptag = "{deadprop:}deadprop"
        coll = self.addCollection("/coll", title = u"Test collection")

        opaqueProperties = z3c.dav.interfaces.IOpaquePropertyStorage(coll)
        opaqueProperties.setProperty(proptag,
                                     """<X:deadprop xmlns:X="deadprop:">
This is a dead property.</X:deadprop>""")
        transaction.commit()

        httpresponse = self.checkProppatch(
            "/coll", basic = "mgr:mgrpw",
            remove_properties = """<X:deadprop xmlns:X="deadprop:" />""")

        assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/coll/</href>
  <propstat>
    <prop>
      <ns1:deadprop xmlns:ns1="deadprop:" />
    </prop>
    <status>HTTP/1.1 200 Ok</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

        opaqueProperties = z3c.dav.interfaces.IOpaquePropertyStorage(coll)
        self.assertEqual(opaqueProperties.hasProperty(proptag), False)

    def test_setting_unicode_title(self):
        teststr = u"copyright \xa9 me"
        coll = self.addCollection(u"/" + teststr, title = u"Old title")

        httpresponse = self.checkProppatch(
            "/" + teststr.encode("utf-8"), basic = "mgr:mgrpw",
            set_properties = "<D:displayname>%s</D:displayname>" % teststr,
            handle_errors = False)

        assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/copyright%20%C2%A9%20me/</href>
  <propstat>
    <prop>
      <displayname />
    </prop>
    <status>HTTP/1.1 200 Ok</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

        resourcetitle = IZopeDublinCore(self.getRootFolder()[teststr]).title
        self.assertEqual(resourcetitle, teststr)


def test_suite():
    return unittest.TestSuite((
            unittest.makeSuite(PROPPATCHTestCase),
            ))
