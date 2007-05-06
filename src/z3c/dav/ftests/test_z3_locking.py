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
"""Collection of functional tests for the LOCK method.

$Id$
"""
__docformat__ = 'restructuredtext'

import unittest
import datetime
import transaction
from cStringIO import StringIO
import os.path

import z3c.dav.testing
import z3c.dav.ftests.dav

from zope import component
from zope.app.publication.http import MethodNotAllowed
from zope.app.testing.setup import addUtility
import zope.locking.interfaces
from zope.locking.utility import TokenUtility
from zope.locking import tokens
import zope.locking.utils
from zope.security.interfaces import Unauthorized

from z3c.dav.interfaces import IDAVLockmanager
import z3c.dav.publisher
import z3c.etree
from z3c.etree.testing import assertXMLEqual

here = os.path.dirname(os.path.realpath(__file__))
WebDAVLockingLayer = z3c.dav.testing.WebDAVLayerClass(
   os.path.join(here, "ftesting-locking.zcml"), __name__, "WebDAVLockingLayer")


class LOCKNotAllowedTestCase(z3c.dav.ftests.dav.DAVTestCase):

    layer = WebDAVLockingLayer

    def test_lock_file(self):
        file = self.addResource("/testfilenotallowed", "some file content",
                                contentType = "text/plain")
        self.assertRaises(MethodNotAllowed, self.publish,
            "/testfilenotallowed", basic = "mgr:mgrpw")

    def test_options(self):
        file = self.addResource("/testfilenotallowed", "some file content",
                                contentType = "text/plain")
        response = self.publish("/testfilenotallowed", basic = "mgr:mgrpw",
                                handle_errors = True)

        allowed = [allow.strip() for allow in
                   response.getHeader("Allow").split(",")]
        self.assert_("LOCK" not in allowed)
        self.assert_("UNLOCK" not in allowed)

    def test_lockingprops_noutility(self):
        self.addResource("/testfile", "some file content",
                         contentType = "text/plain")

        httpresponse = self.checkPropfind(
            "/testfile", env = {"DEPTH": "0"},
            properties = """<D:prop>
<D:supportedlock />
<D:lockdiscovery />
</D:prop>""")

        self.assertEqual(len(httpresponse.getMSResponses()), 1)
        assertXMLEqual(
            '<supportedlock xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/testfile", "{DAV:}supportedlock",
                status = 404))
        assertXMLEqual(
            '<lockdiscovery xmlns="DAV:" />',
            httpresponse.getMSProperty(
                "http://localhost/testfile", "{DAV:}lockdiscovery",
                status = 404))


class LOCKTestCase(z3c.dav.ftests.dav.DAVTestCase):

    layer = WebDAVLockingLayer

    def _setup(self):
        z3c.dav.ftests.dav.DAVTestCase.setUp(self)

        self.oldnow = zope.locking.utils.now
        def now():
            return datetime.datetime(2006, 7, 27, 1, 9, 25)
        zope.locking.utils.now = now

    def setUp(self):
        self._setup()

        sitemanager = component.getSiteManager(self.getRootFolder())
        self.utility = addUtility(sitemanager, "",
                                  zope.locking.interfaces.ITokenUtility,
                                  TokenUtility())
        transaction.commit()

    def _teardown(self):
        zope.locking.utils.now = self.oldnow
        del self.oldnow

        z3c.dav.ftests.dav.DAVTestCase.tearDown(self)

    def tearDown(self):
        self._teardown()

        sitemanager = component.getSiteManager(self.getRootFolder())
        sitemanager.unregisterUtility(self.utility,
                                      zope.locking.interfaces.ITokenUtility,
                                      "")
        del self.utility

    def test_options(self):
        file = self.addResource("/testfilenotallowed", "some file content",
                                contentType = "text/plain")
        response = self.publish("/testfilenotallowed", basic = "mgr:mgrpw",
                                handle_errors = True)

        allowed = [allow.strip() for allow in
                   response.getHeader("Allow").split(",")]
        self.assert_("LOCK" in allowed)
        self.assert_("UNLOCK" in allowed)

    def test_lock_file_unauthorized(self):
        file = self.addResource("/testfile", "some file content",
                                contentType = "text/plain")

        lockmanager = IDAVLockmanager(file)
        self.assertEqual(lockmanager.islocked(), False)

        body ="""<?xml version="1.0" encoding="utf-8" ?>
<D:lockinfo xmlns:D='DAV:'>
  <D:lockscope><D:exclusive/></D:lockscope>
  <D:locktype><D:write/></D:locktype>
  <D:owner>
    <D:href>http://example.org/~ejw/contact.html</D:href>
  </D:owner>
</D:lockinfo>"""

        self.assertRaises(Unauthorized, self.publish, "/testfile",
                          env = {"REQUEST_METHOD": "LOCK",
                                 "DEPTH": "0",
                                 "TIMEOUT": "Second-4100000000",
                                 "CONTENT_TYPE": "text/xml"},
                          request_body = body)

    def test_invalid_xml(self):
        body = """<?xml version="1.0" encoding="utf-8" ?>
<D:invalid xmlns:D="DAV:">Invalid XML</D:invalid>
        """

        response = self.publish(
            "/", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "LOCK",
                   "DEPTH": "0",
                   "TIMEOUT": "Infinite, Second-4100000000",
                   "CONTENT_TYPE": "text/xml"},
            request_body = body,
            handle_errors = True)

        self.assertEqual(response.getStatus(), 422)

    def test_lock_file(self):
        file = self.addResource("/testfile", "some file content",
                                contentType = "text/plain")

        lockmanager = IDAVLockmanager(file)
        self.assertEqual(lockmanager.islocked(), False)

        body ="""<?xml version="1.0" encoding="utf-8" ?>
<D:lockinfo xmlns:D='DAV:'>
  <D:lockscope><D:exclusive/></D:lockscope>
  <D:locktype><D:write/></D:locktype>
  <D:owner>
    <D:href>http://example.org/~ejw/contact.html</D:href>
  </D:owner>
</D:lockinfo>"""

        response = self.publish(
            "/testfile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "LOCK",
                   "DEPTH": "0",
                   "TIMEOUT": "Second-4100000000",
                   "CONTENT_TYPE": "text/xml"},
            request_body = body)

        self.assertEqual(response.getStatus(), 200)
        self.assertEqual(response.getHeader("content-type"), "application/xml")
        locktoken = response.getHeader("lock-token")
        self.assert_(locktoken and locktoken[0] == "<" and locktoken[-1] == ">")

        expectedbody = """<ns0:prop xmlns:ns0="DAV:">
<ns0:lockdiscovery>
  <ns0:activelock>
    <ns0:lockscope><ns0:exclusive /></ns0:lockscope>
    <ns0:locktype><ns0:write /></ns0:locktype>
    <ns0:depth>0</ns0:depth>
    <ns0:owner>
      <ns0:href>http://example.org/~ejw/contact.html</ns0:href>
    </ns0:owner>
    <ns0:timeout>Second-60800</ns0:timeout>
    <ns0:locktoken>
      <ns0:href>%s</ns0:href>
    </ns0:locktoken>
    <ns0:lockroot>http://localhost/testfile</ns0:lockroot>
  </ns0:activelock>
</ns0:lockdiscovery></ns0:prop>""" % locktoken[1:-1]

        respbody = response.getBody()
        assertXMLEqual(respbody, expectedbody)

        lockmanager = IDAVLockmanager(file)
        self.assertEqual(lockmanager.islocked(), True)

    def test_already_exclusive_locked_file(self):
        file = self.addResource("/testlockedfile", "some file content",
                                contentType = "text/plain")

        token = tokens.ExclusiveLock(file, "mgr")
        token.duration = datetime.timedelta(seconds = 100)
        self.utility.register(token)

        lockmanager = IDAVLockmanager(file)
        self.assertEqual(lockmanager.islocked(), True)
        transaction.commit()

        body ="""<?xml version="1.0" encoding="utf-8" ?>
<D:lockinfo xmlns:D='DAV:'>
  <D:lockscope><D:exclusive/></D:lockscope>
  <D:locktype><D:write/></D:locktype>
  <D:owner>
    <D:href>http://example.org/~ejw/contact.html</D:href>
  </D:owner>
</D:lockinfo>"""

        response = self.publish(
            "/testlockedfile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "LOCK",
                   "DEPTH": "0",
                   "TIMEOUT": "Second-4100000000",
                   "CONTENT_TYPE": "text/xml"},
            request_body = body,
            handle_errors = True)

        self.assertEqual(response.getStatus(), 207)
        self.assertEqual(response.getHeader("content-type"), "application/xml")

        expectedbody = """<ns0:multistatus xmlns:ns0="DAV:">
<ns0:response>
  <ns0:href>http://localhost/testlockedfile</ns0:href>
  <ns0:status>HTTP/1.1 423 Locked</ns0:status>
</ns0:response></ns0:multistatus>"""

        respbody = response.getBody()
        assertXMLEqual(respbody, expectedbody)

        lockmanager = IDAVLockmanager(file)
        self.assertEqual(lockmanager.islocked(), True)

    def test_lock_folder_depth_inf(self):
        ## Test that when we lock a folder with depth infinity we the folder
        ## and all sub resources lock tokens contain the same locktoken, and
        ## lockroot.
        self.createFolderFileStructure()

        lockmanager = IDAVLockmanager(self.getRootFolder())
        self.assertEqual(lockmanager.islocked(), False)

        body ="""<?xml version="1.0" encoding="utf-8" ?>
<D:lockinfo xmlns:D='DAV:'>
  <D:lockscope><D:exclusive/></D:lockscope>
  <D:locktype><D:write/></D:locktype>
  <D:owner>
    <D:href>http://example.org/~ejw/contact.html</D:href>
  </D:owner>
</D:lockinfo>"""

        response = self.publish(
            "/", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "LOCK",
                   "DEPTH": "infinity",
                   "TIMEOUT": "Second-4100000000",
                   "CONTENT_TYPE": "text/xml"},
            request_body = body)

        self.assertEqual(response.getStatus(), 200)
        self.assertEqual(response.getHeader("content-type"), "application/xml")
        locktoken = response.getHeader("lock-token")
        self.assert_(locktoken and locktoken[0] == "<" and locktoken[-1] == ">")
        locktoken = locktoken[1:-1] # remove the <> characters

        token = self.utility.get(self.getRootFolder())
        self.assertEqual(
            token.annotations["z3c.dav.lockingutils.info"]["token"],
            locktoken)
        token = self.utility.get(self.getRootFolder()["a"])
        self.assertEqual(
            token.annotations["z3c.dav.lockingutils.info"]["token"],
            locktoken)

        root = self.getRootFolder()
        self.assertEqual(
            IDAVLockmanager(root).getActivelock().locktoken[0], locktoken)
        self.assertEqual(
            IDAVLockmanager(root["a"]["r2"]).getActivelock().locktoken[0],
            locktoken)

        request = z3c.dav.publisher.WebDAVRequest(
            StringIO(""), {"HTTP_HOST": "localhost"})

        lockroot = IDAVLockmanager(root).getActivelock(request).lockroot
        self.assertEqual(lockroot, "http://localhost")
        lockroot = IDAVLockmanager(root["a"]["r3"]).getActivelock(
            request).lockroot
        self.assertEqual(lockroot, "http://localhost")

    def test_lock_collection_depth_inf_withlockedsubitem(self):
        self.login()
        self.createFolderFileStructure()

        lockmanager = IDAVLockmanager(self.getRootFolder()["a"]["r2"])
        lockmanager.lock("exclusive", "write", """<D:owner>
<D:href>http://webdav.org/</D:href></D:owner>""",
                         duration = datetime.timedelta(100), depth = "0")
        transaction.commit()
        self.logout()

        body ="""<?xml version="1.0" encoding="utf-8" ?>
<D:lockinfo xmlns:D='DAV:'>
  <D:lockscope><D:exclusive/></D:lockscope>
  <D:locktype><D:write/></D:locktype>
  <D:owner>
    <D:href>http://example.org/~ejw/contact.html</D:href>
  </D:owner>
</D:lockinfo>"""

        httpresponse = self.publish(
            "/a", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "LOCK",
                   "DEPTH": "infinity",
                   "TIMEOUT": "Second-4100000000",
                   "CONTENT_TYPE": "text/xml"},
            request_body = body,
            handle_errors = True)

        etree = z3c.etree.getEngine()
        xmlbody = etree.fromstring(httpresponse.getBody())

        self.assertEqual(httpresponse.getStatus(), 207)
        self.assertEqual(
            httpresponse.getHeader("content-type"), "application/xml")

        responses = xmlbody.findall("{DAV:}response")
        self.assertEqual(len(responses), 2)

        for response in responses:
            hrefs = response.findall("{DAV:}href")
            self.assertEqual(len(hrefs), 1)
            statusresp = response.findall("{DAV:}status")
            self.assertEqual(len(statusresp), 1)
            statusresp = statusresp[0].text

            if hrefs[0].text == "http://localhost/a/":
                self.assertEqual(
                    statusresp, "HTTP/1.1 424 Failed Dependency")
            elif hrefs[0].text == "http://localhost/a/r2":
                self.assertEqual(
                    statusresp, "HTTP/1.1 423 Locked")
            else:
                self.fail("unexpected reponse with href: %s" % hrefs[0].text)

        lockmanager = IDAVLockmanager(self.getRootFolder()["a"])
        self.assertEqual(lockmanager.islocked(), False)

        # this object was already locked.
        lockmanager = IDAVLockmanager(self.getRootFolder()["a"]["r2"])
        self.assertEqual(lockmanager.islocked(), True)

    def test_lock_file_then_propfind(self):
        ## Test that the locking properties get updated correctly whenever a
        ## resource is locked. We do this by performing a PROPFIND on the
        ## locked resource.
        self.createFolderFileStructure()

        body ="""<?xml version="1.0" encoding="utf-8" ?>
<D:lockinfo xmlns:D='DAV:'>
  <D:lockscope><D:exclusive/></D:lockscope>
  <D:locktype><D:write/></D:locktype>
  <D:owner>
    <D:href>http://example.org/~ejw/contact.html</D:href>
  </D:owner>
</D:lockinfo>"""

        response = self.publish(
            "/a", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "LOCK",
                   "DEPTH": "infinity",
                   "TIMEOUT": "Second-4100000000",
                   "CONTENT_TYPE": "text/xml"},
            request_body = body)

        self.assertEqual(response.getStatus(), 200)
        self.assertEqual(response.getHeader("content-type"), "application/xml")
        locktoken = response.getHeader("lock-token")
        self.assert_(locktoken and locktoken[0] == "<" and locktoken[-1] == ">")

        httpresponse = self.checkPropfind(
            "/a/r2", env = {"DEPTH": "0", "CONTENT_TYPE": "text/xml"},
            properties = "<D:allprop />")

        supportedlock = httpresponse.getMSProperty(
            "http://localhost/a/r2", "{DAV:}supportedlock")
        assertXMLEqual(supportedlock, """<ns0:supportedlock xmlns:ns0="DAV:">
<ns0:lockentry xmlns:ns0="DAV:">
  <ns0:lockscope xmlns:ns0="DAV:"><ns0:exclusive xmlns:ns0="DAV:"/></ns0:lockscope>
  <ns0:locktype xmlns:ns0="DAV:"><ns0:write xmlns:ns0="DAV:"/></ns0:locktype>
</ns0:lockentry>
<ns0:lockentry xmlns:ns0="DAV:">
  <ns0:lockscope xmlns:ns0="DAV:"><ns0:shared xmlns:ns0="DAV:"/></ns0:lockscope>
  <ns0:locktype xmlns:ns0="DAV:"><ns0:write xmlns:ns0="DAV:"/></ns0:locktype>
</ns0:lockentry></ns0:supportedlock>""")

        lockdiscovery = httpresponse.getMSProperty(
            "http://localhost/a/r2", "{DAV:}lockdiscovery")
        assertXMLEqual(lockdiscovery, """<ns0:lockdiscovery xmlns:ns0="DAV:">
<ns0:activelock xmlns:ns0="DAV:">
  <ns0:lockscope xmlns:ns0="DAV:"><ns0:exclusive xmlns:ns0="DAV:"/></ns0:lockscope>
  <ns0:locktype xmlns:ns0="DAV:"><ns0:write xmlns:ns0="DAV:"/></ns0:locktype>
  <ns0:depth xmlns:ns0="DAV:">infinity</ns0:depth>
  <ns0:owner xmlns:D="DAV:">
    <ns0:href>http://example.org/~ejw/contact.html</ns0:href>
  </ns0:owner>
  <ns0:timeout xmlns:ns0="DAV:">Second-60800</ns0:timeout>
  <ns0:locktoken xmlns:ns0="DAV:">
    <ns0:href xmlns:ns0="DAV:">%s</ns0:href>
  </ns0:locktoken>
  <ns0:lockroot xmlns:ns0="DAV:">http://localhost/a</ns0:lockroot>
</ns0:activelock></ns0:lockdiscovery>""" % locktoken[1:-1])

    def test_recursive_lock(self):
        self.createFolderFileStructure()

        body ="""<?xml version="1.0" encoding="utf-8" ?>
<D:lockinfo xmlns:D='DAV:'>
  <D:lockscope><D:exclusive/></D:lockscope>
  <D:locktype><D:write/></D:locktype>
  <D:owner>
    <D:href>http://example.org/~ejw/contact.html</D:href>
  </D:owner>
</D:lockinfo>"""

        response = self.publish(
            "/a", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "LOCK",
                   "DEPTH": "infinity",
                   "TIMEOUT": "Second-4100000000",
                   "CONTENT_TYPE": "text/xml"},
            request_body = body)

        self.assertEqual(response.getStatus(), 200)
        self.assertEqual(response.getHeader("content-type"), "application/xml")
        locktoken = response.getHeader("lock-token")
        self.assert_(locktoken and locktoken[0] == "<" and locktoken[-1] == ">")

        rootfolder = self.getRootFolder()["a"]
        subresource = rootfolder["r2"]

        request = z3c.dav.publisher.WebDAVRequest(
            StringIO(""), {"HTTP_HOST": "localhost"})

        lockmanager = IDAVLockmanager(rootfolder)
        self.assertEqual(lockmanager.getActivelock(request).lockroot,
                         "http://localhost/a")
        self.assertEqual(
            lockmanager.getActivelock().locktoken[0], locktoken[1:-1])

        lockmanager = IDAVLockmanager(subresource)
        self.assertEqual(lockmanager.getActivelock(request).lockroot,
                         "http://localhost/a")
        self.assertEqual(
            lockmanager.getActivelock().locktoken[0], locktoken[1:-1])

    def test_lock_invalid_depth(self):
        file = self.addResource("/testresource", "some file content",
                                title = u"Test Resource")

        body ="""<?xml version="1.0" encoding="utf-8" ?>
<D:lockinfo xmlns:D='DAV:'>
  <D:lockscope><D:exclusive/></D:lockscope>
  <D:locktype><D:write/></D:locktype>
  <D:owner>
    <D:href>http://example.org/~ejw/contact.html</D:href>
  </D:owner>
</D:lockinfo>"""

        response = self.publish(
            "/testresource", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "LOCK",
                   "DEPTH": "1",
                   "TIMEOUT": "Infinite, Second-4100000000",
                   "CONTENT_TYPE": "text/xml"},
            request_body = body,
            handle_errors = True)

        self.assertEqual(response.getStatus(), 400)

    def test_refresh_lock(self):
        self.login()
        self.createCollectionResourceStructure()

        lockmanager = IDAVLockmanager(self.getRootFolder()["a"])
        owner = """<D:owner xmlns:D="DAV:">
<D:href>mailto:michael</D:href>
</D:owner>"""
        lockmanager.lock(u"exclusive", u"write", owner,
                         datetime.timedelta(seconds = 1000), "infinity")
        locktoken = lockmanager.getActivelock().locktoken[0]
        self.assertEqual(lockmanager.getActivelock().timeout, u"Second-1000")
        transaction.commit()
        self.logout()

        response = self.publish("/a/r2", basic = "mgr:mgrpw",
                                env = {"REQUEST_METHOD": "LOCK",
                                       "TIMEOUT": "Second-3600",
                                       "IF": "<%s>" % locktoken})

        self.assertEqual(response.getStatus(), 200)
        assertXMLEqual(response.getBody(), """<ns0:prop xmlns:ns0="DAV:">
<ns0:lockdiscovery xmlns:ns0="DAV:">
  <ns0:activelock xmlns:ns0="DAV:">
    <ns0:lockscope xmlns:ns0="DAV:"><ns0:exclusive xmlns:ns0="DAV:"/></ns0:lockscope>
    <ns0:locktype xmlns:ns0="DAV:"><ns0:write xmlns:ns0="DAV:"/></ns0:locktype>
    <ns0:depth xmlns:ns0="DAV:">infinity</ns0:depth>
    <ns0:owner xmlns:D="DAV:">
<ns0:href>mailto:michael</ns0:href>
    </ns0:owner>
    <ns0:timeout xmlns:ns0="DAV:">Second-3600</ns0:timeout>
    <ns0:locktoken xmlns:ns0="DAV:"><ns0:href xmlns:ns0="DAV:">%s</ns0:href></ns0:locktoken>
    <ns0:lockroot xmlns:ns0="DAV:">http://localhost/a</ns0:lockroot>
  </ns0:activelock>
</ns0:lockdiscovery></ns0:prop>""" % locktoken)

    def test_invalid_lock_request_uri(self):
        self.login()
        file = self.addResource("/testresource", "some file content",
                                title = u"Test Resource")

        lockmanager = IDAVLockmanager(file)
        lockmanager.lock(u"exclusive", u"write", u"Michael",
                         datetime.timedelta(seconds = 3600), '0')
        transaction.commit()
        self.logout()

        response = self.publish("/testresource", basic = "mgr:mgrpw",
                                env = {"REQUEST_METHOD": "LOCK",
                                       "TIMEOUT": "Second-3600",
                                       "IF": "<BADLOCKTOKEN>"},
                                handle_errors = True)

        self.assertEqual(response.getStatus(), 412)

    def test_no_lock_request_uri(self):
        self.login()
        file = self.addResource("/testresource", "some file content",
                                title = u"Test Resource")

        lockmanager = IDAVLockmanager(file)
        lockmanager.lock(u"exclusive", u"write", u"Michael",
                         datetime.timedelta(seconds = 3600), '0')
        transaction.commit()
        self.logout()

        response = self.publish("/testresource", basic = "mgr:mgrpw",
                                env = {"REQUEST_METHOD": "LOCK",
                                       "TIMEOUT": "Second-3600"},
                                handle_errors = True)

        self.assertEqual(response.getStatus(), 412)

    def test_not_locked_resource(self):
        file = self.addResource("/testresource", "some file content",
                                title = u"Test Resource")

        response = self.publish("/testresource", basic = "mgr:mgrpw",
                                env = {"REQUEST_METHOD": "LOCK",
                                       "TIMEOUT": "Second-3600",
                                       "IF": "<BADLOCKTOKEN>"},
                                handle_errors = True)

        self.assertEqual(response.getStatus(), 412)


class UNLOCKTestCase(z3c.dav.ftests.dav.DAVTestCase):

    layer = WebDAVLockingLayer

    def setUp(self):
        super(UNLOCKTestCase, self).setUp()

        sitemanager = component.getSiteManager(self.getRootFolder())
        self.utility = addUtility(sitemanager, "",
                                  zope.locking.interfaces.ITokenUtility,
                                  TokenUtility())

    def tearDown(self):
        del self.utility
        super(UNLOCKTestCase, self).tearDown()

    def test_unlock_file(self):
        self.login()
        file = self.addResource("/testfile", "some file content",
                                contentType = "text/plain")

        lockmanager = IDAVLockmanager(file)
        self.assertEqual(lockmanager.islocked(), False)
        lockmanager.lock(scope = "exclusive", type = "write",
                         owner = """<D:owner xmlns:D="DAV:">
  <D:href>mailto:michael@linux</D:href>
</D:owner>""",
                         duration = datetime.timedelta(100),
                         depth = "0")
        transaction.commit()

        lockmanager = IDAVLockmanager(file)
        self.assertEqual(lockmanager.islocked(), True)
        locktoken = lockmanager.getActivelock().locktoken[0]

        # end the current interaction
        self.logout()

        response = self.publish("/testfile", basic = "mgr:mgrpw",
                                env = {"REQUEST_METHOD": "UNLOCK",
                                       "LOCK_TOKEN": "<%s>" % locktoken})

        self.assertEqual(response.getStatus(), 204)
        self.assertEqual(response.getBody(), "")

        lockmanager = IDAVLockmanager(file)
        self.assertEqual(lockmanager.islocked(), False)

    def test_unlock_file_bad_token(self):
        self.login()
        file = self.addResource("/testfile", "some file content",
                                contentType = "text/plain")

        lockmanager = IDAVLockmanager(file)
        self.assertEqual(lockmanager.islocked(), False)
        lockmanager.lock(scope = "exclusive", type = "write",
                         owner = """<D:owner xmlns:D="DAV:">
  <D:href>mailto:michael@linux</D:href>
</D:owner>""",
                         duration = datetime.timedelta(100),
                         depth = "0")
        transaction.commit()

        lockmanager = IDAVLockmanager(file)
        self.assertEqual(lockmanager.islocked(), True)
        locktoken = "badtoken"

        # end the current interaction
        self.logout()

        response = self.publish("/testfile", basic = "mgr:mgrpw",
                                env = {"REQUEST_METHOD": "UNLOCK",
                                       "LOCK_TOKEN": "<%s>" % locktoken},
                                handle_errors = True)

        self.assertEqual(response.getStatus(), 409)
        self.assertEqual(response.getBody(), "")

        # file should be still locked
        lockmanager = IDAVLockmanager(file)
        self.assertEqual(lockmanager.islocked(), True)

    def test_unlock_file_no_token(self):
        self.login()
        file = self.addResource("/testfile", "some file content",
                                contentType = "text/plain")

        lockmanager = IDAVLockmanager(file)
        self.assertEqual(lockmanager.islocked(), False)
        lockmanager.lock(scope = "exclusive", type = "write",
                         owner = """<D:owner xmlns:D="DAV:">
  <D:href>mailto:michael@linux</D:href>
</D:owner>""",
                         duration = datetime.timedelta(100),
                         depth = "0")
        transaction.commit()

        lockmanager = IDAVLockmanager(file)
        self.assertEqual(lockmanager.islocked(), True)

        # end the current interaction
        self.logout()

        response = self.publish("/testfile", basic = "mgr:mgrpw",
                                env = {"REQUEST_METHOD": "UNLOCK"},
                                handle_errors = True)

        self.assertEqual(response.getStatus(), 400)
        self.assert_("No lock-token header supplied" in response.getBody())

        # file should be still locked
        lockmanager = IDAVLockmanager(file)
        self.assertEqual(lockmanager.islocked(), True)

    def test_lock_folder_depth_inf_then_unlock(self):
        self.createFolderFileStructure()

        body ="""<?xml version="1.0" encoding="utf-8" ?>
<D:lockinfo xmlns:D='DAV:'>
  <D:lockscope><D:exclusive/></D:lockscope>
  <D:locktype><D:write/></D:locktype>
  <D:owner>
    <D:href>http://example.org/~ejw/contact.html</D:href>
  </D:owner>
</D:lockinfo>"""

        response = self.publish(
            "/a", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "LOCK",
                   "DEPTH": "infinity",
                   "TIMEOUT": "Second-4100000000",
                   "CONTENT_TYPE": "text/xml"},
            request_body = body)

        self.assertEqual(response.getStatus(), 200)
        self.assertEqual(response.getHeader("content-type"), "application/xml")
        locktoken = response.getHeader("lock-token")
        self.assert_(locktoken and locktoken[0] == "<" and locktoken[-1] == ">")
        locktoken = locktoken[1:-1] # remove the <> characters

        response = self.publish("/a/r2", basic = "mgr:mgrpw",
                                env = {"REQUEST_METHOD": "UNLOCK",
                                       "LOCK_TOKEN": "<%s>" % locktoken})

        self.assertEqual(response.getStatus(), 204)
        self.assertEqual(response.getBody(), "")

        lockmanager = IDAVLockmanager(self.getRootFolder()["a"]["r2"])
        self.assertEqual(lockmanager.islocked(), False)

        lockmanager = IDAVLockmanager(self.getRootFolder())
        self.assertEqual(lockmanager.islocked(), False)

    def test_supportedlock_prop(self):
        file = self.addResource("/testfile", "some file content",
                                contentType = "text/plain")
        httpresponse = self.checkPropfind(
            "/testfile", properties = "<D:prop><D:supportedlock /></D:prop>")

        self.assertEqual(len(httpresponse.getMSResponses()), 1)

        expected = """<D:supportedlock xmlns:D="DAV:">
<D:lockentry>
  <D:lockscope><D:exclusive /></D:lockscope>
  <D:locktype><D:write /></D:locktype>
</D:lockentry>
<D:lockentry>
  <D:lockscope><D:shared /></D:lockscope>
  <D:locktype><D:write /></D:locktype>
</D:lockentry></D:supportedlock>"""
        assertXMLEqual(expected, httpresponse.getMSProperty(
            "http://localhost/testfile", "{DAV:}supportedlock"))


def test_suite():
    return unittest.TestSuite((
            unittest.makeSuite(LOCKNotAllowedTestCase),
            unittest.makeSuite(LOCKTestCase),
            unittest.makeSuite(UNLOCKTestCase),
            ))


if __name__ == "__main__":
    unittest.main(defaultTest = "test_suite")
