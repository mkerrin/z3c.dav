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
"""COPY and MOVE support for WebDAV.

This needs to be cleaned up in order to be easily ported to Zope2.

$Id$
"""
__docformat__ = 'restructuredtext'

import urlparse

from zope import interface
from zope import component
from zope.copypastemove.interfaces import IObjectCopier, IObjectMover
from zope.traversing.api import traverse, getRoot
from zope.traversing.interfaces import TraversalError
from zope.traversing.browser import absoluteURL
from zope.app.publication.http import MethodNotAllowed

import z3c.dav.interfaces

class Base(object):
    interface.implements(z3c.dav.interfaces.IWebDAVMethod)
    component.adapts(interface.Interface, z3c.dav.interfaces.IWebDAVRequest)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def getOverwrite(self):
        overwrite = self.request.getHeader("overwrite", "t").lower().strip()
        if overwrite == "t":
            overwrite = True
        elif overwrite == "f":
            overwrite = False
        else:
            raise z3c.dav.interfaces.BadRequest(
                self.request, message = u"Invalid overwrite header")

        return overwrite

    def getDestinationPath(self):
        dest = self.request.getHeader("destination", None)
        while dest and dest[-1] == "/":
            dest = dest[:-1]
        if not dest:
            raise z3c.dav.interfaces.BadRequest(
                self.request, message = u"No `destination` header sent.")

        scheme, location, destpath, query, fragment = urlparse.urlsplit(dest)
        # XXX - this is likely to break under virtual hosting.
        if location and self.request.get("HTTP_HOST", None) is not None:
            if location.split("@", 1)[-1] != self.request.get("HTTP_HOST"):
                # This may occur when the destination is on another
                # server, repository or URL namespace.  Either the source
                # namespace does not support copying to the destination
                # namespace, or the destination namespace refuses to accept
                # the resource.  The client may wish to try GET/PUT and
                # PROPFIND/PROPPATCH instead.
                raise z3c.dav.interfaces.BadGateway(
                    self.context, self.request)

        return destpath

    def getDestinationNameAndParentObject(self):
        """Returns a tuple for destionation name, the parent folder object
        and a boolean flag indicating wheater the the destinatin object will
        have to be created or not.
        """
        destpath = self.getDestinationPath()
        try:
            destob = traverse(getRoot(self.context), destpath)
        except TraversalError:
            destob = None

        overwrite = self.getOverwrite()

        parentpath = destpath.split('/')
        destname = parentpath.pop()
        try:
            parent = traverse(getRoot(self.context), parentpath)
        except TraversalError:
            raise z3c.dav.interfaces.ConflictError(
                self.context, message = u"Destination resource has no parent")

        if destob is not None and not overwrite:
            raise z3c.dav.interfaces.PreconditionFailed(
                self.context,
                message = "destination exists and OverWrite header is F")
        elif destob is not None and destob == self.context:
            raise z3c.dav.interfaces.ForbiddenError(
                self.context,
                message = "destionation and source objects are the same")
        elif destob is not None:
            del parent[destname]

        return destname, destob, parent


class COPY(Base):
    """COPY handler for all objects."""

    def COPY(self):
        copier = IObjectCopier(self.context, None)
        if copier is None or not copier.copyable():
            raise MethodNotAllowed(self.context, self.request)

        # get the destination
        destname, destob, parent = self.getDestinationNameAndParentObject()

        if not copier.copyableTo(parent, destname):
            # Conflict
            raise z3c.dav.interfaces.ConflictError(
                self.context,
                message = u"can not copy to the destionation folder")

        newdestname = copier.copyTo(parent, destname)

        if destob is not None:
            self.request.response.setStatus(204)
        else:
            self.request.response.setStatus(201)
            self.request.response.setHeader(
                "Location", absoluteURL(parent[newdestname], self.request))

        return ""


class MOVE(Base):
    """MOVE handler for all objects."""

    def MOVE(self):
        mover = IObjectMover(self.context, None)
        if mover is None or not mover.moveable():
            raise MethodNotAllowed(self.context, self.request)

        # get the destination
        destname, destob, parent = self.getDestinationNameAndParentObject()

        if not mover.moveableTo(parent, destname):
            raise z3c.dav.interfaces.ConflictError(
                self.context,
                message = u"can not copy to the destionation folder")

        newdestname = mover.moveTo(parent, destname)

        if destob is not None:
            self.request.response.setStatus(204)
        else:
            self.request.response.setStatus(201)
            self.request.response.setHeader(
                "Location", absoluteURL(parent[newdestname], self.request))

        return ""
