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

import zope.publisher.publish
from zope.publisher.http import status_reasons
import zope.app.testing.functional
import zope.app.publication.http

import z3c.etree.testing
import z3c.dav.publisher

class WebDAVLayerClass(zope.app.testing.functional.ZCMLLayer):

    def setUp(self):
        z3c.etree.testing.etreeSetup()
        zope.app.testing.functional.ZCMLLayer.setUp(self)

    def tearDown(self):
        z3c.etree.testing.etreeTearDown()
        zope.app.testing.functional.ZCMLLayer.tearDown(self)


class WebDAVResponseWrapper(zope.app.testing.functional.ResponseWrapper):
    """

    A HTTP response wrapper that adds support for parsing and retrieving
    information out of a 207 Multi-Status response. The idea is to make
    writing tests for different WebDAV components a lot easier.

      >>> import copy
      >>> from zope.publisher.http import HTTPResponse
      >>> etree = z3c.etree.getEngine()

      >>> response = HTTPResponse()
      >>> wrapped = WebDAVResponseWrapper(response, '/testfile.txt')

    Get a list of response sub elements from the multistatus response body
    with the `getMSResponses` method.

      >>> wrapped.getMSResponses()
      Traceback (most recent call last):
      ...
      ValueError: Not a multistatus response

      >>> response.setStatus(207)
      >>> wrapped.getMSResponses()
      Traceback (most recent call last):
      ...
      ValueError: Invalid response content type

      >>> response.setHeader('content-type', 'application/xml')
      >>> response.setResult('<testdata />')
      >>> wrapped.getMSResponses()
      Traceback (most recent call last):
      ...
      ValueError: Invalid multistatus response body

      >>> response.setResult('<multistatus xmlns="DAV:" />')
      >>> wrapped._body = None # turn off cache
      >>> wrapped.getMSResponses()
      Traceback (most recent call last):
      ...
      ValueError: No multistatus response present

    Add some a valid multistatus response to test with. Even though this
    data is in complete it is enough for the getMSResponses method to
    work with.

      >>> response.setResult('''<multistatus xmlns="DAV:">
      ...   <response />
      ... </multistatus>''')
      >>> wrapped._body = None # turn off cache

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

      >>> response.setResult('''<multistatus xmlns="DAV:">
      ...   <response>
      ...     <href>/testfile.txt</href>
      ...   </response>
      ... </multistatus>''')
      >>> wrapped._body = None # turn off cache

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

      >>> response.setResult('''<multistatus xmlns="DAV:">
      ...   <response>
      ...     <href>/testfile.txt</href>
      ...     <propstat>
      ...       <prop>
      ...         <t1:testprop xmlns:t1="testns:">Test property</t1:testprop>
      ...       </prop>
      ...     </propstat>
      ...   </response>
      ... </multistatus>''')
      >>> wrapped._body = None # turn off cache

      >>> wrapped.getMSPropstat('/testfile.txt', 200)
      Traceback (most recent call last):
      ...
      ValueError: Response containers invalid number of status elements

    The propstat element is not complete here but again there is enough
    information for `getMSPropstat` method to do its job.

      >>> response.setResult('''<multistatus xmlns="DAV:">
      ...   <response>
      ...     <href>/testfile.txt</href>
      ...     <propstat>
      ...       <status>HTTP/1.1 404 Not Found</status>
      ...     </propstat>
      ...   </response>
      ... </multistatus>''')
      >>> wrapped._body = None # turn off cache

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

      >>> response.setResult('''<multistatus xmlns="DAV:">
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
      >>> wrapped._body = None # turn off cache

      >>> wrapped.getMSProperty('/testfile.txt', '{testns:}missing', 404)
      Traceback (most recent call last):
      ...
      KeyError: "'{testns:}missing' property not found for resource /testfile.txt (404)"

      >>> print etree.tostring(wrapped.getMSProperty(
      ...    '/testfile.txt', '{testns:}testprop', 404)) #doctest:+XMLDATA
      <testprop xmlns="testns:">Test property</testprop>

    """

    def __init__(self, response, path, omit = ()):
        super(WebDAVResponseWrapper, self).__init__(response, path, omit)
        self._xmlcachebody = None

    def getMSResponses(self):
        if self._response.getStatus() != 207:
            raise ValueError("Not a multistatus response")
        if self._response.getHeader('content-type') != 'application/xml':
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


class WebDAVTestCase(zope.app.testing.functional.HTTPTestCase):

    def makeRequest(self, path = "", basic = None, form = None,
                    env = {}, instream = None):
        """Create a new WebDAV request
        """
        if instream is None:
            instream = ""

        environment = {"HTTP_HOST": "localhost",
                       "HTTP_REFERER": "localhost"}
        environment.update(env)
        if instream and "CONTENT_LENGTH" not in environment:
            if getattr(instream, "getvalue", None) is not None:
                instream = instream.getvalue()
            environment["CONTENT_LENGTH"] = len(instream)

        app = \
            zope.app.testing.functional.FunctionalTestSetup().getApplication()

        request = app._request(
            path, instream, environment = environment,
            basic = basic, form = form,
            request = z3c.dav.publisher.WebDAVRequest,
            publication = zope.app.publication.http.HTTPPublication)

        return request

    def publish(self, path, basic = None, form = None, env = {},
                handle_errors = False, request_body = ""):
        request = self.makeRequest(path, basic = basic, form = form, env = env,
                                   instream = request_body)
        response = WebDAVResponseWrapper(request.response, path)

        zope.publisher.publish.publish(request, handle_errors = handle_errors)

        return response


class WebDAVCaller(zope.app.testing.functional.HTTPCaller):

    def __call__(self, request_string, handle_errors = True, form = None):
        response = super(WebDAVCaller, self).__call__(
            request_string, handle_errors, form)

        # response should be a zope.app.testing.functional.ResponseWrapper
        return WebDAVResponseWrapper(response, response._path, response.omit)


def functionalSetUp(test):
    test.globs["http"] = zope.app.testing.functional.HTTPCaller()
    test.globs["webdav"] = WebDAVCaller()
    test.globs["getRootFolder"] = zope.app.testing.functional.getRootFolder


def functionalTearDown(test):
    del test.globs["http"]
    del test.globs["webdav"]
    del test.globs["getRootFolder"]
