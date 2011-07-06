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
"""Common WebDAV error handling code.

There are two types of error views. Ones that get caught by the WebDAV protocol
and the other which escapes to the publisher. Both these views implement
different interface which we can control through the WebDAV package via the
IPublication.handleException method.
"""
__docformat__ = 'restructuredtext'

from xml.etree import ElementTree

from zope import interface
from zope import schema
from zope import component
import zope.publisher.interfaces.http
from zope.publisher.interfaces.http import IHTTPException
import zope.publisher.defaultview

import z3c.dav.interfaces
import z3c.dav.utils

class DAVError(object):
    interface.implements(z3c.dav.interfaces.IDAVErrorWidget)
    component.adapts(interface.Interface,
                     z3c.dav.interfaces.IWebDAVRequest)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    status = None

    errors = []

    propstatdescription = ""

    responsedescription = ""


class ConflictError(DAVError):
    status = 409


class ForbiddenError(DAVError):
    status = 403


class PropertyNotFoundError(DAVError):
    status = 404


class FailedDependencyError(DAVError):
    # context is generally None for a failed dependency error.
    status = 424


class AlreadyLockedError(DAVError):
    status = 423


class UnauthorizedError(DAVError):
    status = 401

################################################################################
#
# Multi-status error view
#
################################################################################

class MultiStatusErrorView(object):
    component.adapts(z3c.dav.interfaces.IWebDAVErrors,
                     z3c.dav.interfaces.IWebDAVRequest)
    interface.implements(IHTTPException)

    def __init__(self, error, request):
        self.error = error
        self.request = request

    def __call__(self):
        multistatus = z3c.dav.utils.MultiStatus()

        if len(self.error.errors) == 1 and \
               self.error.errors[0].resource == self.error.context:
            # If have only one error and the context on which we raised the
            # exception, then we just try and view the default view of the
            # error.
            error = self.error.errors[0]
            name = zope.publisher.defaultview.queryDefaultViewName(
                error, self.request)
            if name is not None:
                view = component.queryMultiAdapter(
                    (error, self.request), name = name)
                return view()

        seenContext = False
        for error in self.error.errors:
            if error.resource == self.error.context:
                seenContext = True

            davwidget = component.getMultiAdapter(
                (error, self.request), z3c.dav.interfaces.IDAVErrorWidget)

            response = z3c.dav.utils.Response(
                z3c.dav.utils.getObjectURL(error.resource, self.request))
            response.status = davwidget.status
            # we don't generate a propstat elements during this view so
            # we just ignore the propstatdescription.
            response.responsedescription += davwidget.responsedescription

            multistatus.responses.append(response)

        if not seenContext:
            response = z3c.dav.utils.Response(
                z3c.dav.utils.getObjectURL(self.error.context, self.request))
            response.status = 424 # Failed Dependency
            multistatus.responses.append(response)

        self.request.response.setStatus(207)
        self.request.response.setHeader("content-type", "application/xml")
        return ElementTree.tostring(multistatus(), encoding = "utf-8")


class WebDAVPropstatErrorView(object):
    interface.implements(IHTTPException)
    component.adapts(z3c.dav.interfaces.IWebDAVPropstatErrors,
                     z3c.dav.interfaces.IWebDAVRequest)

    def __init__(self, error, request):
        self.error = error
        self.request = request

    def __call__(self):
        multistatus = z3c.dav.utils.MultiStatus()

        response = z3c.dav.utils.Response(
            z3c.dav.utils.getObjectURL(self.error.context, self.request))
        multistatus.responses.append(response)

        for prop, error in self.error.items():
            error_view = component.getMultiAdapter(
                (error, self.request), z3c.dav.interfaces.IDAVErrorWidget)
            propstat = response.getPropstat(error_view.status)

            if z3c.dav.interfaces.IDAVProperty.providedBy(prop):
                ## XXX - not tested - but is it needed?
                prop = "{%s}%s" %(prop.namespace, prop.__name__)

            propstat.properties.append(ElementTree.Element(prop))
            ## XXX - needs testing.
            propstat.responsedescription += error_view.propstatdescription
            response.responsedescription += error_view.responsedescription

        self.request.response.setStatus(207)
        self.request.response.setHeader("content-type", "application/xml")
        return ElementTree.tostring(multistatus(), encoding = "utf-8")

################################################################################
#
# Some more generic exception view.
#
################################################################################

class HTTPForbiddenError(object):
    interface.implements(IHTTPException)
    component.adapts(z3c.dav.interfaces.IForbiddenError,
                     zope.publisher.interfaces.http.IHTTPRequest)

    def __init__(self, error, request):
        self.error = error
        self.request = request

    def __call__(self):
        self.request.response.setStatus(403)
        return ""


class HTTPConflictError(object):
    interface.implements(IHTTPException)
    component.adapts(z3c.dav.interfaces.IConflictError,
                     zope.publisher.interfaces.http.IHTTPRequest)

    def __init__(self, error, request):
        self.error = error
        self.request = request

    def __call__(self):
        self.request.response.setStatus(409)
        return ""


class PreconditionFailed(object):
    interface.implements(IHTTPException)
    component.adapts(z3c.dav.interfaces.IPreconditionFailed,
                     zope.publisher.interfaces.http.IHTTPRequest)

    def __init__(self, error, request):
        self.error = error
        self.request = request

    def __call__(self):
        self.request.response.setStatus(412)
        return ""


class HTTPUnsupportedMediaTypeError(object):
    interface.implements(IHTTPException)
    component.adapts(z3c.dav.interfaces.IUnsupportedMediaType,
                     zope.publisher.interfaces.http.IHTTPRequest)

    def __init__(self, error, request):
        self.error = error
        self.request = request

    def __call__(self):
        self.request.response.setStatus(415)
        return ""


class UnprocessableError(object):
    interface.implements(IHTTPException)
    component.adapts(z3c.dav.interfaces.IUnprocessableError,
                     zope.publisher.interfaces.http.IHTTPRequest)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self):
        self.request.response.setStatus(422)
        return ""


class AlreadyLockedErrorView(object):
    interface.implements(IHTTPException)
    component.adapts(z3c.dav.interfaces.IAlreadyLocked,
                     zope.publisher.interfaces.http.IHTTPRequest)

    def __init__(self, context, request):
        self.request = request

    def __call__(self):
        self.request.response.setStatus(423)
        return ""


class BadGateway(object):
    interface.implements(IHTTPException)
    component.adapts(z3c.dav.interfaces.IBadGateway,
                     zope.publisher.interfaces.http.IHTTPRequest)

    def __init__(self, error, request):
        self.error = error
        self.request = request

    def __call__(self):
        self.request.response.setStatus(502)
        return ""
