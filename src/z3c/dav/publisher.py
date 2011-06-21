##############################################################################
# Copyright (c) 2006 Zope Foundation and Contributors.
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
"""
__docformat__ = 'restructuredtext'

import zope.component
from zope.interface import implements
from zope.publisher.http import HTTPResponse, HTTPRequest
from zope.app.publication.http import HTTPPublication
from zope.app.publication.interfaces import IRequestPublicationFactory

import z3c.etree
import z3c.conditionalviews
import interfaces


class WebDAVResponse(HTTPResponse):
    implements(interfaces.IWebDAVResponse)


class WebDAVRequest(z3c.conditionalviews.ConditionalHTTPRequest):
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
        content_type = self.getHeader("content-type", None)
        content_type_params = None
        if content_type and ";" in content_type:
            parts = content_type.split(";", 1)
            content_type = parts[0].strip().lower()
            content_type_params = parts[1].strip()

        content_length = self.getHeader("content-length", 0)
        if content_length:
            content_length = int(content_length)

        if content_type in ("text/xml", "application/xml", None, "") and \
               content_length > 0:
            etree = z3c.etree.getEngine()
            try:
                self.xmlDataSource = etree.parse(self.bodyStream).getroot()
            except:
                # There was an error parsing the body stream so this is a
                # bad request if the content was declared as xml
                if content_type is not None:
                    raise interfaces.BadRequest(
                        self, u"Invalid xml data passed")
            else:
                self.content_type = content_type or "application/xml"
        else:
            self.content_type = content_type

    def _createResponse(self):
        """Create a specific WebDAV response object."""
        return WebDAVResponse()


class WebDAVRequestFactory(object):
    implements(IRequestPublicationFactory)

    def canHandle(self, environment):
        return True

    def __call__(self):
        request_class = zope.component.queryUtility(
            interfaces.IWebDAVRequestFactory, default = WebDAVRequest)
        return request_class, HTTPPublication
