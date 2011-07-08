##############################################################################
# Copyright (c) 2007 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
##############################################################################
"""
Miscellaneous utilities used for testing WebDAV components.
"""
__docformat__ = "restructuredtext"

from cStringIO import StringIO
import unittest
import webtest

from zope.publisher.http import status_reasons

import zope.app.wsgi.testlayer

import z3c.etree.testing
import z3c.dav.publisher

class WebDAVLayer(zope.app.wsgi.testlayer.BrowserLayer):

    def setUp(self):
        super(WebDAVLayer, self).setUp()
        z3c.etree.testing.etreeSetup()

    def tearDown(self):
        super(WebDAVLayer, self).tearDown()
        z3c.etree.testing.etreeTearDown()


class WebDAVResponseWrapper(object):
    """

    A HTTP response wrapper that adds support for parsing and retrieving
    information out of a 207 Multi-Status response. The idea is to make
    writing tests for different WebDAV components a lot easier.

      >>> import copy
      >>> from zope.publisher.http import HTTPResponse
      >>> etree = z3c.etree.getEngine()

      >>> response = webtest.Response()
      >>> wrapped = WebDAVResponseWrapper(response, '/testfile.txt')

    Get a list of response sub elements from the multistatus response body
    with the `getMSResponses` method.

      >>> wrapped.getMSResponses()
      Traceback (most recent call last):
      ...
      ValueError: Not a multistatus response

      >>> response = webtest.Response(status = 207)
      >>> wrapped = WebDAVResponseWrapper(response, '/testfile.txt')
      >>> wrapped.getMSResponses()
      Traceback (most recent call last):
      ...
      ValueError: Invalid response content type

      >>> response = webtest.Response(status = 207, content_type = 'application/xml', body = '<testdata />')
      >>> wrapped = WebDAVResponseWrapper(response, '/testfile.txt')
      >>> wrapped.getMSResponses()
      Traceback (most recent call last):
      ...
      ValueError: Invalid multistatus response body

      >>> response = webtest.Response(status = 207, content_type = 'application/xml', body = '<multistatus xmlns="DAV:" />')
      >>> wrapped = WebDAVResponseWrapper(response, '/testfile.txt')
      >>> wrapped.getMSResponses()
      Traceback (most recent call last):
      ...
      ValueError: No multistatus response present

    Add some a valid multistatus response to test with. Even though this
    data is in complete it is enough for the getMSResponses method to
    work with.

      >>> response = webtest.Response(status = 207, content_type = 'application/xml', body = '''<multistatus xmlns="DAV:">
      ...   <response />
      ... </multistatus>''')
      >>> wrapped = WebDAVResponseWrapper(response, '/testfile.txt')

      >>> msresponses = wrapped.getMSResponses()
      >>> len(msresponses)
      1
      >>> print etree.tostring(copy.copy(msresponses[0])) #doctest:+XMLDATA
      <response xmlns="DAV:" />

    Now use the `getMSResponse(href)` to get a response element who's href
    element matches the argument.

      >>> wrapped.getMSResponse('/testfile.txt')
      Traceback (most recent call last):
      ...
      ValueError: Invalid multistatus response body

      >>> response = webtest.Response(status = 207, content_type = 'application/xml', body = '''<multistatus xmlns="DAV:">
      ...   <response>
      ...     <href>/testfile.txt</href>
      ...   </response>
      ... </multistatus>''')
      >>> wrapped = WebDAVResponseWrapper(response, '/testfile.txt')

      >>> print etree.tostring(
      ...    copy.copy(
      ...        wrapped.getMSResponse('/testfile.txt'))) #doctest:+XMLDATA
      <response xmlns="DAV:">
        <href>/testfile.txt</href>
      </response>

    If no response element exist then a KeyError is raised.

      >>> wrapped.getMSResponse('/missingfile.txt')
      Traceback (most recent call last):
      ...
      KeyError: "Multistatus response contained no response for the resource '/missingfile.txt'"

    Get the propstat element with a specific status via the `getMSPropstat`
    method. We need to pass in a href and a status in order to find
    a specific value. Note that all methods raise a ValueError when the
    response doesn't correspond to the 207 multistatus protocol.

      >>> wrapped.getMSPropstat('/testfile.txt', 404)
      Traceback (most recent call last):
      ...
      ValueError: Response contains no propstats sub elements

      >>> response = webtest.Response(status = 207, content_type = 'application/xml', body = '''<multistatus xmlns="DAV:">
      ...   <response>
      ...     <href>/testfile.txt</href>
      ...     <propstat>
      ...       <prop>
      ...         <t1:testprop xmlns:t1="testns:">Test property</t1:testprop>
      ...       </prop>
      ...     </propstat>
      ...   </response>
      ... </multistatus>''')
      >>> wrapped = WebDAVResponseWrapper(response, '/testfile.txt')

      >>> wrapped.getMSPropstat('/testfile.txt', 200)
      Traceback (most recent call last):
      ...
      ValueError: Response containers invalid number of status elements

    The propstat element is not complete here but again there is enough
    information for `getMSPropstat` method to do its job.

      >>> response = webtest.Response(status = 207, content_type = 'application/xml', body = '''<multistatus xmlns="DAV:">
      ...   <response>
      ...     <href>/testfile.txt</href>
      ...     <propstat>
      ...       <status>HTTP/1.1 404 Not Found</status>
      ...     </propstat>
      ...   </response>
      ... </multistatus>''')
      >>> wrapped = WebDAVResponseWrapper(response, '/testfile.txt')

      >>> wrapped.getMSPropstat('/testfile.txt', 200)
      Traceback (most recent call last):
      ...
      KeyError: 'No propstats element with status 200'

      >>> print etree.tostring(
      ...    copy.copy(
      ...        wrapped.getMSPropstat('/testfile.txt', 404))) #doctest:+XMLDATA
      <propstat xmlns="DAV:">
        <status>HTTP/1.1 404 Not Found</status>
      </propstat>

    Get a specific property value from a propstat element corresponding to
    a specific status via the `getMSProperty` method.

      >>> wrapped.getMSProperty('/testfile.txt', '{testns:}missin', 404)
      Traceback (most recent call last):
      ...
      ValueError: Invalid propstat sub element - no prop element

    Finally set up a completely valid multistatus response.

      >>> response = webtest.Response(status = 207, content_type = 'application/xml', body = '''<multistatus xmlns="DAV:">
      ...   <response>
      ...     <href>/testfile.txt</href>
      ...     <propstat>
      ...       <prop>
      ...         <t1:testprop xmlns:t1="testns:">Test property</t1:testprop>
      ...       </prop>
      ...       <status>HTTP/1.1 404 Not Found</status>
      ...     </propstat>
      ...   </response>
      ... </multistatus>''')
      >>> wrapped = WebDAVResponseWrapper(response, '/testfile.txt')

      >>> wrapped.getMSProperty('/testfile.txt', '{testns:}missing', 404)
      Traceback (most recent call last):
      ...
      KeyError: "'{testns:}missing' property not found for resource /testfile.txt (404)"

      >>> print etree.tostring(wrapped.getMSProperty(
      ...    '/testfile.txt', '{testns:}testprop', 404)) #doctest:+XMLDATA
      <testprop xmlns="testns:">Test property</testprop>

    """

    def __init__(self, response, path, omit = ()):
        self._response = response
        self._path = path
        self._xmlcachebody = None

    def __getattr__(self, attr):
        return getattr(self._response, attr)

    def getBody(self):
        return self._response.body

    def getHeader(self, header, literal = None):
        return self._response.headers.get(header, None)

    def getStatus(self):
        return self._response.status_int

    def getMSResponses(self):
        if self.getStatus() != 207:
            raise ValueError("Not a multistatus response")
        if not self.getHeader('Content-Type').startswith('application/xml'):
            raise ValueError("Invalid response content type")

        etree = z3c.etree.getEngine()
        self._xmlcachebody = etree.fromstring(self.getBody())
        if self._xmlcachebody.tag != "{DAV:}multistatus":
            raise ValueError("Invalid multistatus response body")

        responses = self._xmlcachebody.findall("{DAV:}response")
        if not responses:
            raise ValueError("No multistatus response present")

        return responses

    def getMSResponse(self, href):
        ret = []
        for response in self.getMSResponses():
            hrefs = response.findall("{DAV:}href")
            if len(hrefs) != 1:
                raise ValueError("Invalid multistatus response body")

            if hrefs[0].text == href:
                ret.append(response)

        if not ret:
            raise KeyError("Multistatus response contained no response for " \
                           "the resource %r" % href)
        if len(ret) > 1:
            raise ValueError("Multistatus response contains too many " \
                             "responses for the response %r" % href)

        return ret[0]

    def getMSPropstat(self, href, status = 200):
        msresponse = self.getMSResponse(href)

        propstats = msresponse.findall("{DAV:}propstat")
        if not propstats:
            raise ValueError("Response contains no propstats sub elements")

        ret = []
        for propstatus in propstats:
            psstatus = propstatus.findall("{DAV:}status")
            if len(psstatus) != 1:
                raise ValueError("Response containers invalid number of " \
                                 "status elements")

            if psstatus[0].text == "HTTP/1.1 %d %s" %(status,
                                                      status_reasons[status]):
                ret.append(propstatus)

        if not ret:
            raise KeyError("No propstats element with status %d" % status)
        if len(ret) > 1:
            raise ValueError("Too many propstats with the same status")

        return ret[0]

    def getMSProperty(self, href, proptag, status = 200):
        propstat = self.getMSPropstat(href, status)

        props = propstat.findall("{DAV:}prop")
        if len(props) != 1:
            raise ValueError("Invalid propstat sub element - no prop element")
        props = props[0]

        ret = []
        for prop in props:
            if prop.tag == proptag:
                ret.append(prop)

        if not ret:
            raise KeyError("%r property not found for resource %s (%d)" %(
                proptag, href, status))
        if len(ret) > 1:
            raise ValueError("Too many %r properties found" % proptag)

        return ret[0]


class WebDAVTestCase(unittest.TestCase):

    def makeRequest(self, path = "", basic = None, form = None,
                    env = {}, instream = None):
        if instream is None:
            instream = ""

        environment = {
            "HTTP_HOST": "localhost",
            "HTTP_REFERER": "localhost",
            "PATH_INFO": path,
            }
        environment.update(env)
        if instream and "CONTENT_LENGTH" not in environment:
            if getattr(instream, "getvalue", None) is not None:
                instream = instream.getvalue()
            environment["CONTENT_LENGTH"] = len(instream)

        environment["wsgi.input"] = StringIO(instream)

        # setup auth
        if basic:
            environment["HTTP_AUTHORIZATION"] = "Basic %s" % basic

        request = webtest.TestRequest(environment)

        return request

    def publish(self, path, basic = None, form = None, env = {},
                handle_errors = False, request_body = ""):
        app = self.layer.get_app()

        env["wsgi.handleErrors"] = handle_errors

        request = self.makeRequest(
            path, basic = basic, form = form, env = env, instream = request_body)

        response = WebDAVResponseWrapper(request.get_response(app), path)

        return response

    def getRootFolder(self):
        return self.layer.getRootFolder()


def http(string, handle_errors = True):
    app = zope.testbrowser.wsgi.Layer.get_app()
    if app is None:
        raise Exception("No app")

    fp = StringIO(string)
    request = webtest.TestRequest.from_file(fp)
    # XXX - there is a bug in WebOB where setting the body let so, is
    # surrounded by a if request.method in ('PUT', 'POST') which fails
    # to work for lots of WebDAV requests.
    body = request.body_file_raw.read()
    if not body:
        clen = request.content_length
        if clen:
            request.body = fp.read(clen)

    request.environ['wsgi.handleErrors'] = handle_errors

    response = WebDAVResponseWrapper(request.get_response(app), "")
    return response


def functionalSetUp(test):
    test.globs["http"] = http
    test.globs["webdav"] = http
    # test.globs["getRootFolder"] = test.layer.getRootFolder


def functionalTearDown(test):
    del test.globs["http"]
    del test.globs["webdav"]
    # del test.globs["getRootFolder"]
