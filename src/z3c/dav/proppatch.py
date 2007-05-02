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
"""WebDAV PROPPATCH method.

  <!ELEMENT propertyupdate (remove | set)+ >
  <!ELEMENT remove (prop) >
  <!ELEMENT set (prop) >
  <!ELEMENT prop ANY >

$Id$
"""
__docformat__ = 'restructuredtext'

import zope.event
from zope import interface
from zope import component
from zope.lifecycleevent import ObjectModifiedEvent

import zope.webdav.utils
import zope.webdav.interfaces
import zope.webdav.properties
from zope.etree.interfaces import IEtree
from zope.security.interfaces import Unauthorized


class PROPPATCH(object):
    """PROPPATCH handler for all objects"""
    interface.implements(zope.webdav.interfaces.IWebDAVMethod)
    component.adapts(interface.Interface, zope.webdav.interfaces.IWebDAVRequest)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def PROPPATCH(self):
        if self.request.content_type not in ("text/xml", "application/xml"):
            raise zope.webdav.interfaces.BadRequest(
                self.request,
                message = "All PROPPATCH requests needs a XML body")

        xmldata = self.request.xmlDataSource
        if xmldata.tag != "{DAV:}propertyupdate":
            raise zope.webdav.interfaces.UnprocessableError(
                self.context,
                message = u"PROPPATCH request body must be a "
                           "`propertyupdate' XML element.")

        etree = component.getUtility(IEtree)

        # propErrors - list of (property tag, error). error is None if no
        #              error occurred in setting / removing the property.
        propErrors = []
        # properties - list of all the properties that we handled correctly.
        properties = []
        # changed - boolean indicating whether any content changed or not.
        changed = False
        for update in xmldata:
            if update.tag not in ("{DAV:}set", "{DAV:}remove"):
                continue

            props = update.findall("{DAV:}prop")
            if not props:
                continue

            props = props[0]

            for prop in props:
                try:
                    if update.tag == "{DAV:}set":
                        changed |= self.handleSet(prop)
                    else: # update.tag == "{DAV:}remove"
                        changed |= self.handleRemove(prop)
                except Unauthorized:
                    # If the use doesn't have the correct permission to modify
                    # a property then we need to re-raise the Unauthorized
                    # exception in order to ask the user to log in.
                    raise
                except Exception, error:
                    propErrors.append((prop.tag, error))
                else:
                    properties.append(prop.tag)

        if propErrors:
            errors = zope.webdav.interfaces.WebDAVPropstatErrors(self.context)

            for prop, error in propErrors:
                errors[prop] = error

            for proptag in properties:
                errors[proptag] = zope.webdav.interfaces.FailedDependency(
                    self.context, proptag)

            raise errors # this kills the current transaction.

        if changed:
            zope.event.notify(ObjectModifiedEvent(self.context))

        url = zope.webdav.utils.getObjectURL(self.context, self.request)
        response = zope.webdav.utils.Response(url)
        propstat = response.getPropstat(200)

        for proptag in properties:
            propstat.properties.append(etree.Element(proptag))

        multistatus = zope.webdav.utils.MultiStatus()
        multistatus.responses.append(response)

        self.request.response.setStatus(207)
        self.request.response.setHeader("content-type", "application/xml")
        return etree.tostring(multistatus())

    def handleSet(self, prop):
        davprop, adapter = zope.webdav.properties.getProperty(
            self.context, self.request, prop.tag)

        widget = zope.webdav.properties.getWidget(
            davprop, adapter, self.request,
            type = zope.webdav.interfaces.IDAVInputWidget)

        field = davprop.field.bind(adapter)

        if field.readonly:
            raise zope.webdav.interfaces.ForbiddenError(
                self.context, prop.tag, message = u"readonly field")

        value = widget.getInputValue()
        field.validate(value)

        if field.get(adapter) != value:
            field.set(adapter, value)
            return True
        return False

    def handleRemove(self, prop):
        davprop = component.queryUtility(
            zope.webdav.interfaces.IDAVProperty, prop.tag, None)

        if davprop is not None:
            raise zope.webdav.interfaces.ConflictError(
                self.context, prop.tag,
                message = u"cannot remove a live property")

        deadproperties = zope.webdav.interfaces.IOpaquePropertyStorage(
            self.context, None)

        if deadproperties is None or not deadproperties.hasProperty(prop.tag):
            raise zope.webdav.interfaces.ConflictError(
                self.context, prop.tag, message = u"property doesn't exist")

        deadproperties.removeProperty(prop.tag)

        return True
