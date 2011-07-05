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
"""WebDAV PROPPATCH method.

  <!ELEMENT propertyupdate (remove | set)+ >
  <!ELEMENT remove (prop) >
  <!ELEMENT set (prop) >
  <!ELEMENT prop ANY >
"""
__docformat__ = 'restructuredtext'

from xml.etree import ElementTree

import zope.event
import zope.interface
import zope.component
import zope.lifecycleevent

from zope.security.interfaces import Unauthorized

import z3c.dav.utils
import z3c.dav.interfaces
import z3c.dav.properties

class PROPPATCH(object):
    """PROPPATCH handler for all objects"""
    zope.interface.implements(z3c.dav.interfaces.IWebDAVMethod)
    zope.component.adapts(
        zope.interface.Interface, z3c.dav.interfaces.IWebDAVRequest)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def PROPPATCH(self):
        if self.request.xmlDataSource is None:
            raise z3c.dav.interfaces.BadRequest(
                self.request,
                message = "All PROPPATCH requests needs a XML body")

        xmldata = self.request.xmlDataSource
        if xmldata.tag != "{DAV:}propertyupdate":
            raise z3c.dav.interfaces.UnprocessableError(
                self.context,
                message = u"PROPPATCH request body must be a "
                           "`propertyupdate' XML element.")

        # propErrors - list of (property tag, error). error is None if no
        #              error occurred in setting / removing the property.
        propErrors = []
        # properties - list of all the properties that we handled correctly.
        properties = []
        # changedAttributes - list of IModificationDescription objects
        #                     indicting what as changed during this request
        changedAttributes = []
        for update in xmldata:
            if update.tag not in ("{DAV:}set", "{DAV:}remove"):
                continue

            props = update.findall("{DAV:}prop")
            if not props:
                continue

            props = props[0]

            for prop in props:
                if z3c.dav.utils.parseEtreeTag(prop.tag)[0] == "":
                    # A namespace which is None corresponds to when no prefix
                    # is set, which I think is fine.
                    raise z3c.dav.interfaces.BadRequest(
                        self.request,
                        u"PROPFIND with invalid namespace declaration in body")

                try:
                    if update.tag == "{DAV:}set":
                        changedAttributes.extend(self.handleSet(prop))
                    else: # update.tag == "{DAV:}remove"
                        changedAttributes.extend(self.handleRemove(prop))
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

        if changedAttributes:
            zope.event.notify(
                zope.lifecycleevent.ObjectModifiedEvent(
                    self.context, *changedAttributes))

        url = z3c.dav.utils.getObjectURL(self.context, self.request)
        response = z3c.dav.utils.Response(url)
        propstat = response.getPropstat(200)

        for proptag in properties:
            propstat.properties.append(ElementTree.Element(proptag))

        multistatus = z3c.dav.utils.MultiStatus()
        multistatus.responses.append(response)

        self.request.response.setStatus(207)
        self.request.response.setHeader("content-type", "application/xml")
        ## Is UTF-8 encoding ok here or is there a better way of doing this.
        return ElementTree.tostring(multistatus(), encoding = "utf-8")

    def handleSet(self, prop):
        davprop, adapter = z3c.dav.properties.getProperty(
            self.context, self.request, prop.tag)

        # Not all properties have a IDAVInputWidget defined
        field = davprop.field.bind(adapter)
        if field.readonly:
            raise z3c.dav.interfaces.ForbiddenError(
                self.context, prop.tag, message = u"readonly field")

        widget = z3c.dav.properties.getWidget(
            davprop, adapter, self.request,
            type = z3c.dav.interfaces.IDAVInputWidget)

        value = widget.getInputValue()
        field.validate(value)

        if field.get(adapter) != value:
            field.set(adapter, value)
            return [
                zope.lifecycleevent.Attributes(davprop.iface, davprop.__name__)]
        return []

    def handleRemove(self, prop):
        davprop = zope.component.queryUtility(
            z3c.dav.interfaces.IDAVProperty, prop.tag, None)

        if davprop is not None:
            raise z3c.dav.interfaces.ConflictError(
                self.context, prop.tag,
                message = u"cannot remove a live property")

        deadproperties = z3c.dav.interfaces.IOpaquePropertyStorage(
            self.context, None)

        if deadproperties is not None and deadproperties.hasProperty(prop.tag):
            deadproperties.removeProperty(prop.tag)
            return [zope.lifecycleevent.Sequence(
                z3c.dav.interfaces.IOpaquePropertyStorage, prop.tag)]

        return []
