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
"""Collection of functional tests for PROPFIND zope.webdav

$Id$
"""
__docformat__ = 'restructuredtext'

import unittest
from cStringIO import StringIO
import transaction

import dav
from zope import component
import zope.webdav.interfaces

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
        httpresponse, xmlbody = self.checkPropfind(
            "/", env = {"DEPTH": "0", "CONTENT_TYPE": "text/xml"},
            properties = "<D:prop><D:resourcetype/></D:prop>")
        hrefs = xmlbody.findall("{DAV:}response/{DAV:}href")
        self.assertEqual(len(hrefs), 1)
        self.assertEqual(hrefs[0].text, "http://localhost/")

        props = xmlbody.findall("{DAV:}response/{DAV:}propstat/{DAV:}prop")
        self.assertEqual(len(props), 1) # only one prop element
        propel = props[0]

        self.assertEqual(len(propel), 1) # only one property defined
        self.assertEqual(propel[0].tag, "{DAV:}resourcetype")
        self.assertEqual(propel[0].text, None)
        self.assertEqual(len(propel[0]), 1)
        self.assertEqual(propel[0][0].tag, "{DAV:}collection")

    def test_propnames_on_collection(self):
        collection = self.addCollection("/coll")
        
        httpresponse, xmlbody = self.checkPropfind(
            "/coll", env = {"DEPTH": "0"}, properties = "<D:propname />")

        responses = xmlbody.findall("{DAV:}response")
        self.assertEqual(len(responses), 1)
        response = responses[0]
        hrefs = response.findall("{DAV:}href")
        self.assertEqual(len(hrefs), 1)
        self.assertEqual(hrefs[0].text, "http://localhost/coll/")

        props = response.findall("{DAV:}propstat/{DAV:}prop")
        self.assertEqual(len(props), 1)
        propel = props[0]

        self.assertMSPropertyValue(response, "{DAV:}resourcetype")
        self.assertMSPropertyValue(response, "{DAV:}creationdate")
        self.assertMSPropertyValue(response, "{DAV:}displayname")
        self.assertMSPropertyValue(response, "{DAV:}getlastmodified")

    def test_propnames_on_resource(self):
        self.addResource("/r1", "some content")
        
        httpresponse, xmlbody = self.checkPropfind(
            "/r1", env = {"DEPTH": "0"}, properties = "<D:propname />")

        responses = xmlbody.findall("{DAV:}response")
        self.assertEqual(len(responses), 1)
        response = responses[0]
        hrefs = response.findall("{DAV:}href")
        self.assertEqual(len(hrefs), 1)
        self.assertEqual(hrefs[0].text, "http://localhost/r1")

        props = response.findall("{DAV:}propstat/{DAV:}prop")
        self.assertEqual(len(props), 1)

        ## See README.txt for a list of properties defined for these tests.
        self.assertMSPropertyValue(response, "{DAV:}resourcetype")
        self.assertMSPropertyValue(response, "{DAV:}creationdate")
        self.assertMSPropertyValue(response, "{DAV:}displayname")
        self.assertMSPropertyValue(response, "{DAV:}getlastmodified")
        self.assertMSPropertyValue(response, "{DAV:}getcontenttype")
        self.assertMSPropertyValue(response, "{DAV:}getcontentlength")
        self.assertMSPropertyValue(response, "{DAV:}getcontentlanguage")
        self.assertMSPropertyValue(response, "{DAV:}getetag")

    def test_allprop(self):
        collection = self.addCollection("/coll", title = u"Test Collection")
        httpresponse, xmlbody = self.checkPropfind(
            "/coll", env = {"DEPTH": "0"}, properties = "<D:allprop />")

        responses = xmlbody.findall("{DAV:}response")
        self.assertEqual(len(responses), 1)
        response = responses[0]
        hrefs = response.findall("{DAV:}href")
        self.assertEqual(len(hrefs), 1)
        self.assertEqual(hrefs[0].text, "http://localhost/coll/")

        props = response.findall("{DAV:}propstat/{DAV:}prop")
        self.assertEqual(len(props), 1) # only one prop element

        ## See README.txt for a list of properties defined for these tests.
        self.assertMSPropertyValue(response, "{DAV:}resourcetype",
                                   tag = "{DAV:}collection", text_value = None)
        self.assertMSPropertyValue(response, "{DAV:}displayname",
                                   text_value = "Test Collection")

    def test_allprop_on_resource(self):
        collection = self.addResource("/r1", "test resource content",
                                      title = u"Test Resource")

        httpresponse, xmlbody = self.checkPropfind(
            "/r1", env = {"DEPTH": "0"}, properties = "<D:allprop />")

        responses = xmlbody.findall("{DAV:}response")
        self.assertEqual(len(responses), 1)
        response = responses[0]
        hrefs = response.findall("{DAV:}href")
        self.assertEqual(len(hrefs), 1)
        self.assertEqual(hrefs[0].text, "http://localhost/r1")

        props = response.findall("{DAV:}propstat/{DAV:}prop")
        self.assertEqual(len(props), 1) # only one prop element

        ## See README.txt for a list of properties defined for these tests.
        self.assertMSPropertyValue(response, "{DAV:}resourcetype")
        self.assertMSPropertyValue(response, "{DAV:}creationdate")
        self.assertMSPropertyValue(response, "{DAV:}displayname",
                                   text_value = "Test Resource")
        self.assertMSPropertyValue(response, "{DAV:}getlastmodified")
        self.assertMSPropertyValue(response, "{DAV:}getcontenttype")
        self.assertMSPropertyValue(response, "{DAV:}getcontentlength",
                                   text_value = "21")
        self.assertMSPropertyValue(response, "{DAV:}getcontentlanguage")
        self.assertMSPropertyValue(response, "{DAV:}getetag")

    def test_allprop_by_default(self):
        self.addCollection("/coll")
        httpresponse, xmlbody = self.checkPropfind("/coll",
                                                   env = {"DEPTH": "0"},
                                                   properties = "<D:prop />")
        # the rest is copied from the previous code.
        responses = xmlbody.findall("{DAV:}response")
        self.assertEqual(len(responses), 1)
        response = responses[0]
        hrefs = response.findall("{DAV:}href")
        self.assertEqual(len(hrefs), 1)
        self.assertEqual(hrefs[0].text, "http://localhost/coll/")

        props = response.findall("{DAV:}propstat/{DAV:}prop")
        self.assertEqual(len(props), 1) # only one prop element

        ## See README.txt for a list of properties defined for these tests.
        self.assertMSPropertyValue(response, "{DAV:}resourcetype",
                                   tag = "{DAV:}collection", text_value = None)
        self.assertMSPropertyValue(response, "{DAV:}displayname")

    def test_nobody_propfind(self):
        self.addCollection("/coll", title = u"Test Collection")
        
        httpresponse, xmlbody = self.checkPropfind("/coll",
                                                   env = {"DEPTH": "0"})
        # the rest is copied from the previous code.
        responses = xmlbody.findall("{DAV:}response")
        self.assertEqual(len(responses), 1)
        response = responses[0]
        hrefs = response.findall("{DAV:}href")
        self.assertEqual(len(hrefs), 1)
        self.assertEqual(hrefs[0].text, "http://localhost/coll/")

        props = response.findall("{DAV:}propstat/{DAV:}prop")
        self.assertEqual(len(props), 1) # only one prop element

        ## See README.txt for a list of properties defined for these tests.
        self.assertMSPropertyValue(response, "{DAV:}resourcetype",
                                   tag = "{DAV:}collection")
        self.assertMSPropertyValue(response, "{DAV:}displayname",
                                   text_value = "Test Collection")

    def test_notfound_property(self):
        httpresponse, xmlbody = self.checkPropfind(
            "/", env = {"DEPTH": "0"},
            properties = """<D:prop>
  <D:resourcetype />
  <D:missingproperty />
</D:prop>""")
        responses = xmlbody.findall("{DAV:}response")
        self.assertEqual(len(responses), 1)
        response = responses[0]
        hrefs = response.findall("{DAV:}href")
        self.assertEqual(len(hrefs), 1)
        self.assertEqual(hrefs[0].text, "http://localhost/")

        self.assertMSPropertyValue(response, "{DAV:}resourcetype",
                                   tag = "{DAV:}collection")
        self.assertMSPropertyValue(response, "{DAV:}missingproperty",
                                   status = 404)

    def test_depthinf(self):
        self.createCollectionResourceStructure()

        httpresponse, xmlbody = self.checkPropfind(
            "/", env = {"DEPTH": "infinity"},
            properties = "<D:prop><D:resourcetype /></D:prop>")

        responses = xmlbody.findall("{DAV:}response")
        self.assertEqual(len(responses), 7)

        # make sure we have all 200 status codes, and the hrefs differ
        for response in responses:
            propstats  = response.findall("{DAV:}propstat")
            self.assertEqual(len(propstats), 1)
            statusresp = response.findall("{DAV:}propstat/{DAV:}status")
            self.assertEqual(len(statusresp), 1)
            self.assertEqual(statusresp[0].text, "HTTP/1.1 200 OK")

        hrefs = [href.text for href in
                 xmlbody.findall("{DAV:}response/{DAV:}href")]
        hrefs.sort()
        self.assertEqual(hrefs, ["http://localhost/",
                                 "http://localhost/++etc++site/",
                                 "http://localhost/a/",
                                 "http://localhost/a/r2",
                                 "http://localhost/a/r3",
                                 "http://localhost/b/",
                                 "http://localhost/r1"])

    def test_depthone(self):
        self.createCollectionResourceStructure()

        httpresponse, xmlbody = self.checkPropfind(
            "/", env = {"DEPTH": "1"},
            properties = "<D:prop><D:resourcetype /></D:prop>")

        responses = xmlbody.findall("{DAV:}response")
        self.assertEqual(len(responses), 5)

        # make sure we have all 200 status codes, and the hrefs differ
        for response in responses:
            propstats  = response.findall("{DAV:}propstat")
            self.assertEqual(len(propstats), 1)
            statusresp = response.findall("{DAV:}propstat/{DAV:}status")
            self.assertEqual(len(statusresp), 1)
            self.assertEqual(statusresp[0].text, "HTTP/1.1 200 OK")

        hrefs = [href.text for href in
                 xmlbody.findall("{DAV:}response/{DAV:}href")]
        hrefs.sort()
        self.assertEqual(hrefs, ["http://localhost/",
                                 "http://localhost/++etc++site/",
                                 "http://localhost/a/",
                                 "http://localhost/b/",
                                 "http://localhost/r1"])

    def test_opaque_properties(self):
        file = self.addResource("/r", "some file content",
                                title = u"Test resource")

        opaqueProperties = zope.webdav.interfaces.IOpaquePropertyStorage(file)
        opaqueProperties.setProperty(
            "{examplens:}testdeadprop",
            """<E:testdeadprop xmlns:E="examplens:">TEST</E:testdeadprop>""")
        transaction.commit()

        properties = """<D:prop xmlns:E="examplens:">
<D:resourcetype /><E:testdeadprop />
</D:prop>
"""
        httpresponse, xmlbody = self.checkPropfind(
            "/r", env = {"DEPTH": "0"}, properties = properties)

        responses = xmlbody.findall("{DAV:}response")
        self.assertEqual(len(responses), 1)
        response = responses[0]

        hrefs = response.findall("{DAV:}href")
        self.assertEqual(len(hrefs), 1)
        self.assertEqual(hrefs[0].text, "http://localhost/r")

        propstats = response.findall("{DAV:}propstat")
        self.assertEqual(len(propstats), 1)
        props = propstats[0].findall("{DAV:}prop")
        self.assertEqual(len(props), 1)

        self.assertMSPropertyValue(response, "{DAV:}resourcetype")
        self.assertMSPropertyValue(response, "{examplens:}testdeadprop",
                                   text_value = "TEST")

    def test_allprop_with_opaque_properties(self):
        file = self.addResource("/r", "some file content",
                                title = u"Test Resource")

        opaqueProperties = zope.webdav.interfaces.IOpaquePropertyStorage(file)
        opaqueProperties.setProperty(
            "{examplens:}testdeadprop",
            """<E:testdeadprop xmlns:E="examplens:">TEST</E:testdeadprop>""")
        transaction.commit()

        properties = "<D:allprop />"
        httpresponse, xmlbody = self.checkPropfind(
            "/r", env = {"DEPTH": "0"}, properties = properties)

    def test_unicode_title(self):
        teststr = u"copyright \xa9 me"
        file = self.addResource(u"/" + teststr, "some file content",
                                title = teststr)

        httpresponse, xmlbody = self.checkPropfind(
            "/" + teststr.encode("utf-8"), env = {"DEPTH": "0",
                                                  "CONTENT_TYPE": "text/xml"},
            properties = "<D:prop><D:displayname /></D:prop>")

        responses = xmlbody.findall("{DAV:}response")
        self.assertEqual(len(responses), 1)
        response = responses[0]

        self.assertMSPropertyValue(response, "{DAV:}displayname",
                                   text_value = teststr)

    def test_allprop_with_deadprops(self):
        file = self.addResource("/r", "some content", title = u"Test Resource")

        opaqueProperties = zope.webdav.interfaces.IOpaquePropertyStorage(file)
        opaqueProperties.setProperty("{deadprop:}deadprop",
                                     """<X:deadprop xmlns:X="deadprop:">
This is a dead property.</X:deadprop>""")
        transaction.commit()

        httpresponse, xmlbody = self.checkPropfind(
            "/r", env = {"DEPTH": "0", "CONTENT_TYPE": "text/xml"},
            properties = "<D:allprop />")

        responses = xmlbody.findall("{DAV:}response")
        self.assertEqual(len(responses), 1)
        response = responses[0]

        self.assertMSPropertyValue(response, "{deadprop:}deadprop",
                                   text_value = """
This is a dead property.""")

    def test_allprop_with_restricted(self):
        file = self.addResource("/r", "some content", title = u"Test Resource")

        examplePropStorage = component.getMultiAdapter(
            (file, dav.TestWebDAVRequest()), dav.IExamplePropertyStorage)
        examplePropStorage.exampletextprop = "EXAMPLE TEXT PROP"
        transaction.commit()

        httpresponse, xmlbody = self.checkPropfind(
            "/r", env = {"DEPTH": "0", "CONTENT_TYPE": "application/xml"},
            properties = "<D:allprop />")

        hrefs = xmlbody.findall("{DAV:}response/{DAV:}href")
        self.assertEqual(len(hrefs), 1)
        self.assertEqual(hrefs[0].text, "http://localhost/r")

        props = xmlbody.findall("{DAV:}response/{DAV:}propstat/{DAV:}prop")
        self.assertEqual(len(props), 1) # only one prop element

        self.assertEqual([prop.tag for prop in
                          props[0] if prop.tag == "{DAVtest:}exampletextprop"],
                         [])

    def test_allprop_with_include(self):
        file = self.addResource("/r", "some content", title = u"Test Resource")

        examplePropStorage = component.getMultiAdapter(
            (file, dav.TestWebDAVRequest()), dav.IExamplePropertyStorage)
        examplePropStorage.exampletextprop = "EXAMPLE TEXT PROP"
        transaction.commit()

        textprop = component.getUtility(zope.webdav.interfaces.IDAVProperty,
                                        name = "{DAVtest:}exampletextprop")
        textprop.restricted = True

        httpresponse, xmlbody = self.checkPropfind(
            "/r", env = {"DEPTH": "0", "CONTENT_TYPE": "application/xml"},
            properties = """<D:allprop />
<D:include>
  <Dtest:exampletextprop xmlns:Dtest="DAVtest:" />
</D:include>
""")

        hrefs = xmlbody.findall("{DAV:}response/{DAV:}href")
        self.assertEqual(len(hrefs), 1)
        self.assertEqual(hrefs[0].text, "http://localhost/r")

        responses = xmlbody.findall("{DAV:}response")
        self.assertEqual(len(responses), 1)
        response = responses[0]

        self.assertMSPropertyValue(response, "{DAVtest:}exampletextprop",
                                   text_value = "EXAMPLE TEXT PROP")

    def test_allprop_with_include_on_unauthorized(self):
        file = self.addResource("/r", "some content", title = u"Test Resource")

        body = """<?xml version="1.0" encoding="utf-8" ?>
<propfind xmlns:D="DAV:" xmlns="DAV:">
  <D:allprop />
  <D:include>
    <Dtest:unauthprop xmlns:Dtest="DAVtest:" />
  </D:include>
</propfind>"""

        httpresponse, xmlbody = self.checkPropfind(
            "/r", env = {"DEPTH": "0", "CONTENT_TYPE": "application/xml"},
            properties = """<D:allprop />
<D:include>
  <Dtest:unauthprop xmlns:Dtest="DAVtest:" />
</D:include>
""")

        responses = xmlbody.findall("{DAV:}response")
        self.assertEqual(len(responses), 1)
        response = responses[0]

        hrefs = response.findall("{DAV:}href")
        self.assertEqual(len(hrefs), 1)
        self.assertEqual(hrefs[0].text, "http://localhost/r")

        propstats = response.findall("{DAV:}propstat")
        self.assertEqual(len(propstats), 2)
        props = propstats[0].findall("{DAV:}prop")
        self.assertEqual(len(props), 1)

        self.assertMSPropertyValue(response, "{DAVtest:}unauthprop",
                                   status = 401)

    def test_propfind_onfile(self):
        self.addResource("/testfile", "some file content",
                         contentType = "text/plain")
        httpresponse, xmlbody = self.checkPropfind(
            "/testfile", env = {"DEPTH": "0"}, properties = "<D:allprop />")

        responses = xmlbody.findall("{DAV:}response")
        self.assertEqual(len(responses), 1)
        response = responses[0]

        hrefs = response.findall("{DAV:}href")
        self.assertEqual(len(hrefs), 1)
        self.assertEqual(hrefs[0].text, "http://localhost/testfile")

        propstats = response.findall("{DAV:}propstat")
        self.assertEqual(len(propstats), 1)
        props = propstats[0].findall("{DAV:}prop")
        self.assertEqual(len(props), 1)

        # all properties should be defined on a file.
        self.assertMSPropertyValue(response, "{DAV:}resourcetype")
        self.assertMSPropertyValue(response, "{DAV:}creationdate")
        self.assertMSPropertyValue(response, "{DAV:}displayname")
        self.assertMSPropertyValue(response, "{DAV:}getcontentlanguage")
        self.assertMSPropertyValue(response, "{DAV:}getcontentlength",
                                   text_value = "17")
        self.assertMSPropertyValue(response, "{DAV:}getcontenttype",
                                   text_value = "text/plain")
        self.assertMSPropertyValue(response, "{DAV:}getetag")
        self.assertMSPropertyValue(response, "{DAV:}getlastmodified")


def test_suite():
    return unittest.TestSuite((
            unittest.makeSuite(PROPFINDTests),
            ))

if __name__ == "__main__":
    unittest.main(defaultTest = "test_suite")
