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

$Id$
"""
__docformat__ = 'restructuredtext'

import urllib
import unittest
from cStringIO import StringIO
import transaction

import dav
from zope import component
import zope.security.interfaces
import z3c.dav.interfaces
import z3c.etree.testing

class PROPFINDTests(dav.DAVTestCase):

    def test_badcontent(self):
        response = self.publish("/", env = {"REQUEST_METHOD": "PROPFIND"},
                                request_body = "some content",
                                handle_errors = True)
        self.assertEqual(response.getStatus(), 400)
        self.assert_("PROPFIND requires a valid XML request"
                     in response.getBody())

    def test_invaliddepth(self):
        body = """<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:">
  <D:prop xmlns:R="http://ns.example.com/boxschema/">
    <R:bigbox/>
    <R:author/>
    <R:DingALing/>
    <R:Random/>
  </D:prop>
</D:propfind>"""
        response = self.publish("/", env = {"REQUEST_METHOD": "PROPFIND",
                                            "CONTENT_TYPE": "text/xml",
                                            "DEPTH": "3",},
                                request_body = StringIO(body),
                                handle_errors = True)
        self.assertEqual(response.getStatus(), 400)
        self.assert_("Invalid Depth header supplied" in response.getBody())

    def test_invalid_xml(self):
        body = """<D:invalid xmlns:D="DAV:">Invalid</D:invalid>"""
        response = self.publish("/", env = {"REQUEST_METHOD": "PROPFIND",
                                            "CONTENT_TYPE": "text/xml",
                                            "CONTENT_LENGTH": len(body),
                                            },
                                request_body = body,
                                handle_errors = True)

        self.assertEqual(response.getStatus(), 422)

    def test_simplepropfind_for_resourcetype(self):
        body = """<?xml version="1.0" encoding="utf-8" ?>
<ff0:propfind xmlns:ff0="DAV:">
  <ff0:prop>
    <ff0:resourcetype/>
  </ff0:prop>
</ff0:propfind>"""
        httpresponse = self.checkPropfind(
            "/", env = {"DEPTH": "0", "CONTENT_TYPE": "text/xml"},
            properties = "<D:prop><D:resourcetype/></D:prop>")

        z3c.etree.testing.assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/</href>
  <propstat>
    <prop>
      <resourcetype><collection /></resourcetype>
    </prop>
    <status>HTTP/1.1 200 Ok</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

    def test_propnames_on_collection(self):
        collection = self.addCollection("/coll")
        
        httpresponse = self.checkPropfind(
            "/coll", env = {"DEPTH": "0"}, properties = "<D:propname />")

        z3c.etree.testing.assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/coll/</href>
  <propstat>
    <prop>
      <creationdate />
      <displayname />
      <ns1:exampletextprop xmlns:ns1="DAVtest:" />
      <getlastmodified />
      <resourcetype />
      <ns1:exampleintprop xmlns:ns1="DAVtest:" />
      <ns1:unauthprop xmlns:ns1="DAVtest:" />
    </prop>
    <status>HTTP/1.1 200 Ok</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

    def test_allprop(self):
        collection = self.addCollection("/coll", title = u"Test Collection")
        httpresponse = self.checkPropfind(
            "/coll", env = {"DEPTH": "0"}, properties = "<D:allprop />")

        z3c.etree.testing.assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/coll/</href>
  <propstat>
    <prop>
      <creationdate />
      <displayname>Test Collection</displayname>
      <getlastmodified />
      <resourcetype><collection /></resourcetype>
      <ns1:exampleintprop xmlns:ns1="DAVtest:">0</ns1:exampleintprop>
    </prop>
    <status>HTTP/1.1 200 Ok</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

    def test_allprop_by_default(self):
        self.addCollection("/coll")
        httpresponse = self.checkPropfind("/coll",
                                          env = {"DEPTH": "0"},
                                          properties = "<D:prop />")
        self.assertEqual(len(httpresponse.getMSResponses()), 1)

        z3c.etree.testing.assertXMLEqual(
            '<resourcetype xmlns="DAV:"><collection /></resourcetype>',
            httpresponse.getMSProperty(
                "http://localhost/coll/", "{DAV:}resourcetype"))
        z3c.etree.testing.assertXMLEqual(
            '<displayname xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/coll/", "{DAV:}displayname"))

    def test_nobody_propfind(self):
        self.addCollection("/coll", title = u"Test Collection")
        
        httpresponse = self.checkPropfind("/coll",
                                          env = {"DEPTH": "0"})

        self.assertEqual(len(httpresponse.getMSResponses()), 1)

        z3c.etree.testing.assertXMLEqual(
            '<resourcetype xmlns="DAV:"><collection /></resourcetype>',
            httpresponse.getMSProperty(
                "http://localhost/coll/", "{DAV:}resourcetype"))
        z3c.etree.testing.assertXMLEqual(
            '<displayname xmlns="DAV:">Test Collection</displayname>',
            httpresponse.getMSProperty(
                "http://localhost/coll/", "{DAV:}displayname"))

    def test_notfound_property(self):
        httpresponse = self.checkPropfind(
            "/", env = {"DEPTH": "0"},
            properties = """<D:prop>
  <D:resourcetype />
  <D:missingproperty />
</D:prop>""")

        self.assertEqual(len(httpresponse.getMSResponses()), 1)
        z3c.etree.testing.assertXMLEqual(
            '<resourcetype xmlns="DAV:"><collection /></resourcetype>',
            httpresponse.getMSProperty(
                "http://localhost/", "{DAV:}resourcetype"))
        z3c.etree.testing.assertXMLEqual(
            '<missingproperty xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/", "{DAV:}missingproperty", status = 404))

    def test_depthinf(self):
        self.createCollectionResourceStructure()

        httpresponse = self.checkPropfind(
            "/", env = {"DEPTH": "infinity"},
            properties = "<D:prop><D:resourcetype /></D:prop>")

        responses = httpresponse.getMSResponses()
        self.assertEqual(len(responses), 7)

        # make sure we have all 200 status codes, and collect all hrefs
        allhrefs = []
        for response in responses:
            propstats  = response.findall("{DAV:}propstat")
            self.assertEqual(len(propstats), 1)
            statusresp = response.findall("{DAV:}propstat/{DAV:}status")
            self.assertEqual(len(statusresp), 1)
            self.assertEqual(statusresp[0].text, "HTTP/1.1 200 Ok")
            hrefs = response.findall("{DAV:}href")
            self.assertEqual(len(hrefs), 1)
            allhrefs.append(hrefs[0].text)

        allhrefs.sort()

        self.assertEqual(allhrefs, ["http://localhost/",
                                    "http://localhost/++etc++site/",
                                    "http://localhost/a/",
                                    "http://localhost/a/r2",
                                    "http://localhost/a/r3",
                                    "http://localhost/b/",
                                    "http://localhost/r1"])

    def test_etcsite(self):
        # By all means this test is a bit stupid but it does highlight a fact.
        # We get unauthorized errors when we enter try and access a resource
        # which doesn't give the admin access to folder listing. But as
        # the previous test shows we can get the problem resource to display
        # in the depth infinity folder listing. As long as the problem resource
        # is not the request resource then no errors should be raised.
        self.assertRaises(zope.security.interfaces.Unauthorized,
                          self.publish, "/++etc++site/", basic = "mrg:mgrpw",
                          env = {"REQUEST_METHOD": "PROPFIND"})

    def test_depthone(self):
        self.createCollectionResourceStructure()

        httpresponse = self.checkPropfind(
            "/", env = {"DEPTH": "1"},
            properties = "<D:prop><D:resourcetype /></D:prop>")

        responses = httpresponse.getMSResponses()
        self.assertEqual(len(responses), 5)

        # make sure we have all 200 status codes, and collect all hrefs
        allhrefs = []
        for response in responses:
            propstats  = response.findall("{DAV:}propstat")
            self.assertEqual(len(propstats), 1)
            statusresp = response.findall("{DAV:}propstat/{DAV:}status")
            self.assertEqual(len(statusresp), 1)
            self.assertEqual(statusresp[0].text, "HTTP/1.1 200 Ok")
            hrefs = response.findall("{DAV:}href")
            self.assertEqual(len(hrefs), 1)
            allhrefs.append(hrefs[0].text)

        allhrefs.sort()

        self.assertEqual(allhrefs, ["http://localhost/",
                                    "http://localhost/++etc++site/",
                                    "http://localhost/a/",
                                    "http://localhost/b/",
                                    "http://localhost/r1"])

    def test_opaque_properties(self):
        coll = self.addCollection("/coll", title = u"Test resource")

        opaqueProperties = z3c.dav.interfaces.IOpaquePropertyStorage(coll)
        opaqueProperties.setProperty(
            "{examplens:}testdeadprop",
            """<E:testdeadprop xmlns:E="examplens:">TEST</E:testdeadprop>""")
        transaction.commit()

        properties = """<D:prop xmlns:E="examplens:">
<D:resourcetype /><E:testdeadprop />
</D:prop>
"""
        httpresponse = self.checkPropfind(
            "/coll", env = {"DEPTH": "0"}, properties = properties)

        z3c.etree.testing.assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/coll/</href>
  <propstat>
    <prop>
      <resourcetype><collection /></resourcetype>
      <ns1:testdeadprop xmlns:ns1="examplens:">TEST</ns1:testdeadprop>
    </prop>
    <status>HTTP/1.1 200 Ok</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

    def test_allprop_with_opaque_properties(self):
        coll = self.addCollection("/coll", title = u"Test collection")

        opaqueProperties = z3c.dav.interfaces.IOpaquePropertyStorage(coll)
        opaqueProperties.setProperty(
            "{examplens:}testdeadprop",
            """<E:testdeadprop xmlns:E="examplens:">TEST</E:testdeadprop>""")
        transaction.commit()

        properties = "<D:allprop />"
        httpresponse = self.checkPropfind(
            "/coll", env = {"DEPTH": "0"}, properties = properties)

        z3c.etree.testing.assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/coll/</href>
  <propstat>
    <prop>
      <creationdate />
      <displayname>Test collection</displayname>
      <getlastmodified />
      <resourcetype><collection /></resourcetype>
      <ns1:exampleintprop xmlns:ns1="DAVtest:">0</ns1:exampleintprop>
      <ns1:testdeadprop xmlns:ns1="examplens:">TEST</ns1:testdeadprop>
    </prop>
    <status>HTTP/1.1 200 Ok</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

    def test_unicode_title(self):
        teststr = u"copyright \xa9 me"
        self.addCollection(u"/" + teststr, title = teststr)

        httpresponse = self.checkPropfind(
            "/" + teststr.encode("utf-8"), env = {"DEPTH": "0",
                                                  "CONTENT_TYPE": "text/xml"},
            properties = "<D:prop><D:displayname /></D:prop>")

        z3c.etree.testing.assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/copyright%20%C2%A9%20me/</href>
  <propstat>
    <prop>
      <displayname>copyright \xc2\xa9 me</displayname>
    </prop>
    <status>HTTP/1.1 200 Ok</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

    def test_allprop_with_deadprops(self):
        coll = self.addCollection("/coll", title = u"Test collection")

        opaqueProperties = z3c.dav.interfaces.IOpaquePropertyStorage(coll)
        opaqueProperties.setProperty("{deadprop:}deadprop",
                                     """<X:deadprop xmlns:X="deadprop:">
This is a dead property.</X:deadprop>""")
        transaction.commit()

        httpresponse = self.checkPropfind(
            "/coll", env = {"DEPTH": "0", "CONTENT_TYPE": "text/xml"},
            properties = "<D:allprop />")

        z3c.etree.testing.assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/coll/</href>
  <propstat>
    <prop>
      <creationdate />
      <displayname>Test collection</displayname>
      <getlastmodified />
      <resourcetype><collection /></resourcetype>
      <ns1:exampleintprop xmlns:ns1="DAVtest:">0</ns1:exampleintprop>
      <ns1:deadprop xmlns:ns1="deadprop:">
This is a dead property.</ns1:deadprop>
    </prop>
    <status>HTTP/1.1 200 Ok</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

    def test_allprop_with_restricted(self):
        file = self.addCollection("/coll", title = u"Test collection")

        examplePropStorage = component.getMultiAdapter(
            (file, dav.TestWebDAVRequest()), dav.IExamplePropertyStorage)
        examplePropStorage.exampletextprop = "EXAMPLE TEXT PROP"
        transaction.commit()

        httpresponse = self.checkPropfind(
            "/coll", env = {"DEPTH": "0", "CONTENT_TYPE": "application/xml"},
            properties = "<D:allprop />")

        self.assertRaises(KeyError, httpresponse.getMSProperty,
                          "http://localhost/coll/",
                          "{DAVtest:}exampletextprop")

    def test_allprop_with_include(self):
        coll = self.addCollection("/coll", title = u"Test collection")

        examplePropStorage = component.getMultiAdapter(
            (coll, dav.TestWebDAVRequest()), dav.IExamplePropertyStorage)
        examplePropStorage.exampletextprop = "EXAMPLE TEXT PROP"
        transaction.commit()

        textprop = component.getUtility(z3c.dav.interfaces.IDAVProperty,
                                        name = "{DAVtest:}exampletextprop")
        textprop.restricted = True

        httpresponse = self.checkPropfind(
            "/coll", env = {"DEPTH": "0", "CONTENT_TYPE": "application/xml"},
            properties = """<D:allprop />
<D:include>
  <Dtest:exampletextprop xmlns:Dtest="DAVtest:" />
</D:include>
""")

        z3c.etree.testing.assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/coll/</href>
  <propstat>
    <prop>
      <creationdate />
      <displayname>Test collection</displayname>
      <ns1:exampletextprop xmlns:ns1="DAVtest:">EXAMPLE TEXT PROP</ns1:exampletextprop>
      <getlastmodified />
      <resourcetype><collection /></resourcetype>
      <ns1:exampleintprop xmlns:ns1="DAVtest:">0</ns1:exampleintprop>
    </prop>
    <status>HTTP/1.1 200 Ok</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())

    def test_allprop_with_include_on_unauthorized(self):
        self.addCollection("/coll", title = u"Test collection")

        body = """<?xml version="1.0" encoding="utf-8" ?>
<propfind xmlns:D="DAV:" xmlns="DAV:">
  <D:allprop />
  <D:include>
    <Dtest:unauthprop xmlns:Dtest="DAVtest:" />
  </D:include>
</propfind>"""

        httpresponse = self.checkPropfind(
            "/coll/", env = {"DEPTH": "0", "CONTENT_TYPE": "application/xml"},
            properties = """<D:allprop />
<D:include>
  <Dtest:unauthprop xmlns:Dtest="DAVtest:" />
</D:include>
""")

        z3c.etree.testing.assertXMLEqual(
            """<multistatus xmlns="DAV:">
<response>
  <href>http://localhost/coll/</href>
  <propstat>
    <prop>
      <creationdate />
      <displayname>Test collection</displayname>
      <getlastmodified />
      <resourcetype><collection /></resourcetype>
      <ns1:exampleintprop xmlns:ns1="DAVtest:">0</ns1:exampleintprop>
    </prop>
    <status>HTTP/1.1 200 Ok</status>
  </propstat>
  <propstat>
    <prop>
      <ns1:unauthprop xmlns:ns1="DAVtest:" />
    </prop>
    <status>HTTP/1.1 401 Unauthorized</status>
  </propstat>
</response>
</multistatus>""",
            httpresponse.getBody())


def test_suite():
    return unittest.TestSuite((
            unittest.makeSuite(PROPFINDTests),
            ))
