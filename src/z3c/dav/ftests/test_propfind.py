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
__docformat__ = 'restructuredtext'

import urllib
import unittest
from cStringIO import StringIO
import transaction

import dav
from zope import component
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

    def test_simplepropfind_textxml(self):
        body = """<?xml version="1.0" encoding="utf-8" ?>
<ff0:propfind xmlns:ff0="DAV:">
  <ff0:prop>
    <ff0:resourcetype/>
  </ff0:prop>
</ff0:propfind>"""
        httpresponse = self.checkPropfind(
            "/", env = {"DEPTH": "0", "CONTENT_TYPE": "text/xml"},
            properties = "<D:prop><D:resourcetype/></D:prop>")
        self.assertEqual(len(httpresponse.getMSResponses()), 1)

        resourcetype = httpresponse.getMSProperty(
            "http://localhost/", "{DAV:}resourcetype")
        z3c.etree.testing.assertXMLEqual(
            """<resourcetype xmlns="DAV:">
                 <collection />
               </resourcetype>""",
            resourcetype)

    def test_propnames_on_collection(self):
        collection = self.addCollection("/coll")
        
        httpresponse = self.checkPropfind(
            "/coll", env = {"DEPTH": "0"}, properties = "<D:propname />")

        self.assertEqual(len(httpresponse.getMSResponses()), 1)

        z3c.etree.testing.assertXMLEqual(
            '<resourcetype xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/coll/", "{DAV:}resourcetype"))
        z3c.etree.testing.assertXMLEqual(
            '<creationdate xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/coll/", "{DAV:}creationdate"))
        z3c.etree.testing.assertXMLEqual(
            '<displayname xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/coll/", "{DAV:}displayname"))
        z3c.etree.testing.assertXMLEqual(
            '<getlastmodified xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/coll/", "{DAV:}getlastmodified"))

    def test_propnames_on_resource(self):
        self.addResource("/r1", "some content")
        
        httpresponse = self.checkPropfind(
            "/r1", env = {"DEPTH": "0"}, properties = "<D:propname />")

        self.assertEqual(len(httpresponse.getMSResponses()), 1)

        z3c.etree.testing.assertXMLEqual(
            '<resourcetype xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r1", "{DAV:}resourcetype"))
        z3c.etree.testing.assertXMLEqual(
            '<creationdate xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r1", "{DAV:}creationdate"))
        z3c.etree.testing.assertXMLEqual(
            '<displayname xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r1", "{DAV:}displayname"))
        z3c.etree.testing.assertXMLEqual(
            '<getlastmodified xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r1", "{DAV:}getlastmodified"))
        z3c.etree.testing.assertXMLEqual(
            '<getcontenttype xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r1", "{DAV:}getcontenttype"))
        z3c.etree.testing.assertXMLEqual(
            '<getcontentlength xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r1", "{DAV:}getcontentlength"))
        z3c.etree.testing.assertXMLEqual(
            '<getcontentlanguage xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r1", "{DAV:}getcontentlanguage"))
        z3c.etree.testing.assertXMLEqual(
            '<getetag xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r1", "{DAV:}getetag"))

    def test_allprop(self):
        collection = self.addCollection("/coll", title = u"Test Collection")
        httpresponse = self.checkPropfind(
            "/coll", env = {"DEPTH": "0"}, properties = "<D:allprop />")

        self.assertEqual(len(httpresponse.getMSResponses()), 1)

        z3c.etree.testing.assertXMLEqual(
            """<resourcetype xmlns="DAV:">
                 <collection />
               </resourcetype>""",
            httpresponse.getMSProperty(
                "http://localhost/coll/", "{DAV:}resourcetype"))
        z3c.etree.testing.assertXMLEqual(
            """<displayname xmlns="DAV:">Test Collection</displayname>""",
            httpresponse.getMSProperty(
                "http://localhost/coll/", "{DAV:}displayname"))

    def test_allprop_on_resource(self):
        collection = self.addResource("/r1", "test resource content",
                                      title = u"Test Resource")

        httpresponse = self.checkPropfind(
            "/r1", env = {"DEPTH": "0"}, properties = "<D:allprop />")

        self.assertEqual(len(httpresponse.getMSResponses()), 1)

        z3c.etree.testing.assertXMLEqual(
            '<resourcetype xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r1", "{DAV:}resourcetype"))
        z3c.etree.testing.assertXMLEqual(
            '<creationdate xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r1", "{DAV:}creationdate"))
        z3c.etree.testing.assertXMLEqual(
            '<displayname xmlns="DAV:">Test Resource</displayname>',
            httpresponse.getMSProperty(
                "http://localhost/r1", "{DAV:}displayname"))
        z3c.etree.testing.assertXMLEqual(
            '<getlastmodified xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r1", "{DAV:}getlastmodified"))
        z3c.etree.testing.assertXMLEqual(
            '<getcontenttype xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r1", "{DAV:}getcontenttype"))
        z3c.etree.testing.assertXMLEqual(
            '<getcontentlength xmlns="DAV:">21</getcontentlength>',
            httpresponse.getMSProperty(
                "http://localhost/r1", "{DAV:}getcontentlength"))
        z3c.etree.testing.assertXMLEqual(
            '<getcontentlanguage xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r1", "{DAV:}getcontentlanguage"))
        z3c.etree.testing.assertXMLEqual(
            '<getetag xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r1", "{DAV:}getetag"))

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
            self.assertEqual(statusresp[0].text, "HTTP/1.1 200 OK")
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
            self.assertEqual(statusresp[0].text, "HTTP/1.1 200 OK")
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
        file = self.addResource("/r", "some file content",
                                title = u"Test resource")

        opaqueProperties = z3c.dav.interfaces.IOpaquePropertyStorage(file)
        opaqueProperties.setProperty(
            "{examplens:}testdeadprop",
            """<E:testdeadprop xmlns:E="examplens:">TEST</E:testdeadprop>""")
        transaction.commit()

        properties = """<D:prop xmlns:E="examplens:">
<D:resourcetype /><E:testdeadprop />
</D:prop>
"""
        httpresponse = self.checkPropfind(
            "/r", env = {"DEPTH": "0"}, properties = properties)

        self.assertEqual(len(httpresponse.getMSResponses()), 1)
        z3c.etree.testing.assertXMLEqual(
            '<resourcetype xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/r", "{DAV:}resourcetype"))
        z3c.etree.testing.assertXMLEqual(
            '<testdeadprop xmlns="examplens:">TEST</testdeadprop>',
            httpresponse.getMSProperty(
                "http://localhost/r", "{examplens:}testdeadprop"))

    def test_allprop_with_opaque_properties(self):
        file = self.addResource("/r", "some file content",
                                title = u"Test Resource")

        opaqueProperties = z3c.dav.interfaces.IOpaquePropertyStorage(file)
        opaqueProperties.setProperty(
            "{examplens:}testdeadprop",
            """<E:testdeadprop xmlns:E="examplens:">TEST</E:testdeadprop>""")
        transaction.commit()

        properties = "<D:allprop />"
        httpresponse = self.checkPropfind(
            "/r", env = {"DEPTH": "0"}, properties = properties)

    def test_unicode_title(self):
        teststr = u"copyright \xa9 me"
        file = self.addResource(u"/" + teststr, "some file content",
                                title = teststr)

        httpresponse = self.checkPropfind(
            "/" + teststr.encode("utf-8"), env = {"DEPTH": "0",
                                                  "CONTENT_TYPE": "text/xml"},
            properties = "<D:prop><D:displayname /></D:prop>")

        want = '<displayname xmlns="DAV:">%s</displayname>' % teststr
        z3c.etree.testing.assertXMLEqual(
            want.encode("utf-8"), # needed in order for elementtree to parse
            httpresponse.getMSProperty(
                "http://localhost/%s" % urllib.quote(teststr.encode("utf-8")),
                "{DAV:}displayname"))

    def test_allprop_with_deadprops(self):
        file = self.addResource("/r", "some content", title = u"Test Resource")

        opaqueProperties = z3c.dav.interfaces.IOpaquePropertyStorage(file)
        opaqueProperties.setProperty("{deadprop:}deadprop",
                                     """<X:deadprop xmlns:X="deadprop:">
This is a dead property.</X:deadprop>""")
        transaction.commit()

        httpresponse = self.checkPropfind(
            "/r", env = {"DEPTH": "0", "CONTENT_TYPE": "text/xml"},
            properties = "<D:allprop />")

        self.assertEqual(len(httpresponse.getMSResponses()), 1)
        z3c.etree.testing.assertXMLEqual(
            """<deadprop xmlns="deadprop:">
This is a dead property.</deadprop>""",
            httpresponse.getMSProperty(
                "http://localhost/r", "{deadprop:}deadprop"))

    def test_allprop_with_restricted(self):
        file = self.addResource("/r", "some content", title = u"Test Resource")

        examplePropStorage = component.getMultiAdapter(
            (file, dav.TestWebDAVRequest()), dav.IExamplePropertyStorage)
        examplePropStorage.exampletextprop = "EXAMPLE TEXT PROP"
        transaction.commit()

        httpresponse = self.checkPropfind(
            "/r", env = {"DEPTH": "0", "CONTENT_TYPE": "application/xml"},
            properties = "<D:allprop />")

        self.assertRaises(KeyError, httpresponse.getMSProperty,
                          "http://localhost/r", "{DAVtest:}exampletextprop")

    def test_allprop_with_include(self):
        file = self.addResource("/r", "some content", title = u"Test Resource")

        examplePropStorage = component.getMultiAdapter(
            (file, dav.TestWebDAVRequest()), dav.IExamplePropertyStorage)
        examplePropStorage.exampletextprop = "EXAMPLE TEXT PROP"
        transaction.commit()

        textprop = component.getUtility(z3c.dav.interfaces.IDAVProperty,
                                        name = "{DAVtest:}exampletextprop")
        textprop.restricted = True

        httpresponse = self.checkPropfind(
            "/r", env = {"DEPTH": "0", "CONTENT_TYPE": "application/xml"},
            properties = """<D:allprop />
<D:include>
  <Dtest:exampletextprop xmlns:Dtest="DAVtest:" />
</D:include>
""")

        z3c.etree.testing.assertXMLEqual(
            """<exampletextprop
                xmlns="DAVtest:">EXAMPLE TEXT PROP</exampletextprop>""",
            httpresponse.getMSProperty(
                "http://localhost/r", "{DAVtest:}exampletextprop"))

    def test_allprop_with_include_on_unauthorized(self):
        file = self.addResource("/r", "some content", title = u"Test Resource")

        body = """<?xml version="1.0" encoding="utf-8" ?>
<propfind xmlns:D="DAV:" xmlns="DAV:">
  <D:allprop />
  <D:include>
    <Dtest:unauthprop xmlns:Dtest="DAVtest:" />
  </D:include>
</propfind>"""

        httpresponse = self.checkPropfind(
            "/r", env = {"DEPTH": "0", "CONTENT_TYPE": "application/xml"},
            properties = """<D:allprop />
<D:include>
  <Dtest:unauthprop xmlns:Dtest="DAVtest:" />
</D:include>
""")

        self.assertEqual(len(httpresponse.getMSResponses()), 1)

        z3c.etree.testing.assertXMLEqual(
            '<unauthprop xmlns="DAVtest:" />',
            httpresponse.getMSProperty(
                "http://localhost/r", "{DAVtest:}unauthprop", status = 401))

    def test_propfind_onfile(self):
        self.addResource("/testfile", "some file content",
                         contentType = "text/plain")
        httpresponse = self.checkPropfind(
            "/testfile", env = {"DEPTH": "0"}, properties = "<D:allprop />")

        self.assertEqual(len(httpresponse.getMSResponses()), 1)

        # all properties should be defined on a file.
        z3c.etree.testing.assertXMLEqual(
            '<resourcetype xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/testfile", "{DAV:}resourcetype"))
        z3c.etree.testing.assertXMLEqual(
            '<creationdate xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/testfile", "{DAV:}creationdate"))
        z3c.etree.testing.assertXMLEqual(
            '<displayname xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/testfile", "{DAV:}displayname"))
        z3c.etree.testing.assertXMLEqual(
            '<getcontentlanguage xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/testfile", "{DAV:}getcontentlanguage"))
        z3c.etree.testing.assertXMLEqual(
            '<getcontentlength xmlns="DAV:">17</getcontentlength>',
            httpresponse.getMSProperty(
                "http://localhost/testfile", "{DAV:}getcontentlength"))
        z3c.etree.testing.assertXMLEqual(
            '<getcontenttype xmlns="DAV:">text/plain</getcontenttype>',
            httpresponse.getMSProperty(
                "http://localhost/testfile", "{DAV:}getcontenttype"))
        z3c.etree.testing.assertXMLEqual(
            '<getetag xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/testfile", "{DAV:}getetag"))
        z3c.etree.testing.assertXMLEqual(
            '<getlastmodified xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/testfile", "{DAV:}getlastmodified"))


def test_suite():
    return unittest.TestSuite((
            unittest.makeSuite(PROPFINDTests),
            ))

if __name__ == "__main__":
    unittest.main(defaultTest = "test_suite")
