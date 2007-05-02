##############################################################################
# Copyright (c) 2006 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
##############################################################################
"""WebDAV publishing objects including the request and response.

$Id$
"""
__docformat__ = 'restructuredtext'

from zope import component
from zope.interface import implements
from zope.publisher.http import HTTPResponse, HTTPRequest
from zope.app.publication.http import HTTPPublication
from zope.app.publication.interfaces import IRequestPublicationFactory

from zope.etree.interfaces import IEtree
import interfaces


class WebDAVResponse(HTTPResponse):
    implements(interfaces.IWebDAVResponse)


class WebDAVRequest(HTTPRequest):
    implements(interfaces.IWebDAVRequest)

    __slot__ = (
        'xmlDataSource', # holds xml.dom representation of the input stream
                         # if it is XML otherwise it is None.
        'content_type',  # 
        )

    def __init__(self, body_instream, environ, reponse = None,
                 positional = None, outstream = None):
        super(WebDAVRequest, self).__init__(body_instream, environ)

        self.xmlDataSource = None
        self.content_type = None

    def processInputs(self):
        """See IPublisherRequest."""
        content_type = self.getHeader('content-type', '')
        content_type_params = None
        if ';' in content_type:
            parts = content_type.split(';', 1)
            content_type = parts[0].strip().lower()
            content_type_params = parts[1].strip()

        self.content_type = content_type

        if content_type in ("text/xml", "application/xml") and \
               self.getHeader("content-length", 0) > 0:
            etree = component.getUtility(IEtree)
            try:
                self.xmlDataSource = etree.parse(self.bodyStream).getroot()
            except:
                # There was an error parsing the body stream so this is a
                # bad request.
                raise interfaces.BadRequest(
                    self, u"Invalid xml data passed")

    def _createResponse(self):
        """Create a specific WebDAV response object."""
        return WebDAVResponse()


class WebDAVRequestFactory(object):
    implements(IRequestPublicationFactory)

    def canHandle(self, environment):
        return True

    def __call__(self):
        request_class = component.queryUtility(
            interfaces.IWebDAVRequestFactory, default = WebDAVRequest)
        return request_class, HTTPPublication
