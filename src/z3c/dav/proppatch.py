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

import z3c.etree
from zope.security.interfaces import Unauthorized

import z3c.dav.utils
import z3c.dav.interfaces
import z3c.dav.properties

class PROPPATCH(object):
    """PROPPATCH handler for all objects"""
    interface.implements(z3c.dav.interfaces.IWebDAVMethod)
    component.adapts(interface.Interface, z3c.dav.interfaces.IWebDAVRequest)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def PROPPATCH(self):
        if self.request.content_type not in ("text/xml", "application/xml"):
            raise z3c.dav.interfaces.BadRequest(
                self.request,
                message = "All PROPPATCH requests needs a XML body")

        xmldata = self.request.xmlDataSource
        if xmldata.tag != "{DAV:}propertyupdate":
            raise z3c.dav.interfaces.UnprocessableError(
                self.context,
                message = u"PROPPATCH request body must be a "
                           "`propertyupdate' XML element.")

        etree = z3c.etree.getEngine()

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
            errors = z3c.dav.interfaces.WebDAVPropstatErrors(self.context)

            for prop, error in propErrors:
                errors[prop] = error

            for proptag in properties:
                errors[proptag] = z3c.dav.interfaces.FailedDependency(
                    self.context, proptag)

            raise errors # this kills the current transaction.

        if changed:
            zope.event.notify(ObjectModifiedEvent(self.context))

        url = z3c.dav.utils.getObjectURL(self.context, self.request)
        response = z3c.dav.utils.Response(url)
        propstat = response.getPropstat(200)

        for proptag in properties:
            propstat.properties.append(etree.Element(proptag))

        multistatus = z3c.dav.utils.MultiStatus()
        multistatus.responses.append(response)

        self.request.response.setStatus(207)
        self.request.response.setHeader("content-type", "application/xml")
        return etree.tostring(multistatus())

    def handleSet(self, prop):
        davprop, adapter = z3c.dav.properties.getProperty(
            self.context, self.request, prop.tag)

        widget = z3c.dav.properties.getWidget(
            davprop, adapter, self.request,
            type = z3c.dav.interfaces.IDAVInputWidget)

        field = davprop.field.bind(adapter)

        if field.readonly:
            raise z3c.dav.interfaces.ForbiddenError(
                self.context, prop.tag, message = u"readonly field")

        value = widget.getInputValue()
        field.validate(value)

        if field.get(adapter) != value:
            field.set(adapter, value)
            return True
        return False

    def handleRemove(self, prop):
        davprop = component.queryUtility(
            z3c.dav.interfaces.IDAVProperty, prop.tag, None)

        if davprop is not None:
            raise z3c.dav.interfaces.ConflictError(
                self.context, prop.tag,
                message = u"cannot remove a live property")

        deadproperties = z3c.dav.interfaces.IOpaquePropertyStorage(
            self.context, None)

        if deadproperties is None or not deadproperties.hasProperty(prop.tag):
            raise z3c.dav.interfaces.ConflictError(
                self.context, prop.tag, message = u"property doesn't exist")

        deadproperties.removeProperty(prop.tag)

        return True
