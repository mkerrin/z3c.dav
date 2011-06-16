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
"""WebDAV method PROPFIND

The propfind XML element conforms to the following DTD snippet

  <!ELEMENT propfind ( propname | (allprop, include?) | prop ) >
  <!ELEMENT propname EMPTY >
  <!ELEMENT allprop EMPTY >
  <!ELEMENT include ANY >
  <!ELEMENT prop ANY >

All the render*(ob, req, extra) know how to render the requested properties
requested by the PROPFIND method.

  renderPropnames(ob, req, ignore) - extra argument is ignored.

  renderAllProperties(ob, req, include) - extra argument is a list of all
                                          the properties that must be rendered.

  renderSelectedProperties(ob, req, props) - extra argument is a list of all
                                             the properties to render.

And all these methods return a z3c.dav.utils.IResponse implementation.

$Id$
"""
__docformat__ = 'restructuredtext'

import sys

from zope import interface
import zope.component
from zope.filerepresentation.interfaces import IReadDirectory
from zope.error.interfaces import IErrorReportingUtility
import zope.security.interfaces

import z3c.etree
import z3c.dav.utils
import z3c.dav.interfaces
import z3c.dav.properties

DEFAULT_NS = "DAV:"

class PROPFIND(object):
    """
    PROPFIND handler for all objects.
    """
    interface.implements(z3c.dav.interfaces.IWebDAVMethod)
    zope.component.adapts(
        interface.Interface, z3c.dav.interfaces.IWebDAVRequest)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def getDepth(self):
        return self.request.getHeader("depth", "infinity")

    def PROPFIND(self):
        if int(self.request.getHeader("content-length", 0)) > 0 and \
               self.request.content_type not in ("text/xml", "application/xml"):
            raise z3c.dav.interfaces.BadRequest(
                self.request,
                message = u"PROPFIND requires a valid XML request")

        depth = self.getDepth()
        if depth not in ("0", "1", "infinity"):
            raise z3c.dav.interfaces.BadRequest(
                self.request, message = u"Invalid Depth header supplied")

        propertiesFactory = None
        extraArg = None

        propfind = self.request.xmlDataSource
        if propfind is not None:
            if propfind.tag != "{DAV:}propfind":
                raise z3c.dav.interfaces.UnprocessableError(
                    self.context,
                    message = u"Request is not a `propfind' XML element.")
            properties = propfind[0]
            if properties.tag == "{DAV:}propname":
                propertiesFactory = self.renderPropnames
            elif properties.tag == "{DAV:}allprop":
                propertiesFactory = self.renderAllProperties
                includes = propfind.findall("{DAV:}include")
                if includes: # we have "DAV:include" properties
                    extraArg = includes[0]
            elif properties.tag == "{DAV:}prop":
                if len(properties) == 0:
                    propertiesFactory = self.renderAllProperties
                else:
                    propertiesFactory = self.renderSelectedProperties
                    extraArg = properties
            else:
                raise z3c.dav.interfaces.UnprocessableError(
                    self.context,
                    message = u"Unknown propfind property element.")
        else:
            propertiesFactory = self.renderAllProperties

        multistatus = z3c.dav.utils.MultiStatus()
        responses = self.handlePropfindResource(
            self.context, self.request, depth, propertiesFactory, extraArg)
        multistatus.responses.extend(responses)

        etree = z3c.etree.getEngine()

        self.request.response.setStatus(207)
        self.request.response.setHeader("content-type", "application/xml")
        ## Is UTF-8 encoding ok here or is there a better way of doing this.
        return etree.tostring(multistatus(), encoding = "utf-8")

    def handlePropfindResource(self, ob, req, depth, \
                               propertiesFactory, extraArg,
                               level = 0):
        """
        Recursive method that collects all the `response' XML elements for
        the current PROPFIND request.

        `propertiesFactory' is the method that is used to generated the
        `response' XML element for one resource. It takes the resource,
        request and `extraArg' used to pass in specific information about
        the properties we want to return.
        """
        responses = [propertiesFactory(ob, req, extraArg, level)]
        if depth in ("1", "infinity"):
            subdepth = (depth == "1") and "0" or "infinity"

            readdir = IReadDirectory(ob, None)
            if readdir is not None:
                try:
                    # We catch any Forbidden or Unauthorized exceptions here.
                    # We have successfully rendered the property on this
                    # resource and we are as such trying to render a listing
                    # of the container object. If we do get an Unauthorized
                    # exception then we only raise this if level == 0.
                    # Otherwise the user might never have access to the resource
                    # and they will never get to see the resources that they
                    # are interested in.
                    values = readdir.values()
                except zope.security.interfaces.Forbidden:
                    # Since we successfully rendered the properties and the
                    # user is forbidden to access the folder listing then
                    # we silently ignore this exception. Allowing them to
                    # continue with there usage of the system.
                    errUtility = zope.component.getUtility(
                        IErrorReportingUtility)
                    errUtility.raising(sys.exc_info(), req)
                except zope.security.interfaces.Unauthorized:
                    # Sometimes even the administrator will raise an
                    # `Unauthorized' exception on the `values' method. If this
                    # happens on a sub-resource to the requested resource then
                    # we log the exception and continue - others this request
                    # fails with the `Unauthorized' exception.
                    if level == 0:
                        raise
                    errUtility = zope.component.getUtility(
                        IErrorReportingUtility)
                    errUtility.raising(sys.exc_info(), req)
                else:
                    for subob in values:
                        responses.extend(self.handlePropfindResource(
                            subob, req, subdepth,
                            propertiesFactory, extraArg, level + 1))

        return responses

    def handleException(self, proptag, exc_info, request, response):
        error_view = zope.component.queryMultiAdapter(
            (exc_info[1], request), z3c.dav.interfaces.IDAVErrorWidget)
        if error_view is None:
            # An unexpected error occured here and should be fixed.
            propstat = response.getPropstat(500) # Internal Server Error
        else:
            propstat = response.getPropstat(error_view.status)
            # XXX - needs testing
            propstat.responsedescription += error_view.propstatdescription
            response.responsedescription += error_view.responsedescription

        # In order to easily debug the problem we will log the error with
        # the ErrorReportingUtility.
        errUtility = zope.component.getUtility(IErrorReportingUtility)
        errUtility.raising(exc_info, request)

        etree = z3c.etree.getEngine()
        propstat.properties.append(etree.Element(proptag))

    def renderPropnames(self, ob, req, ignoreExtraArg, ignorelevel = 0):
        """
        See doc string for the renderAllProperties method. Note that we don't
        need to worry about the security in this method has the permissions on
        the storage adapters should be enough to hide any properties that users
        don't have permission to see.
        """
        response = z3c.dav.utils.Response(
            z3c.dav.utils.getObjectURL(ob, req))

        etree = z3c.etree.getEngine()

        for davprop, adapter in \
                z3c.dav.properties.getAllProperties(ob, req):
            rendered_name = etree.Element(
                etree.QName(davprop.namespace, davprop.__name__)
                )
            response.addProperty(200, rendered_name)

        return response

    def renderAllProperties(self, ob, req, include, level = 0):
        """
        The specification says:
        
          Properties may be subject to access control.  In the case of
          'allprop' and 'propname' requests, if a principal does not have the
          right to know whether a particular property exists then the property
          MAY be silently excluded from the response.

        """
        response = z3c.dav.utils.Response(
            z3c.dav.utils.getObjectURL(ob, req))

        for davprop, adapter in \
                z3c.dav.properties.getAllProperties(ob, req):
            isIncluded = False
            if include is not None and \
                   include.find("{%s}%s" %(davprop.namespace,
                                           davprop.__name__)) is not None:
                isIncluded = True
            elif davprop.restricted:
                continue

            try:
                # getWidget and render are two possible areas where the
                # property is silently ignored because of security concerns.
                davwidget = z3c.dav.properties.getWidget(
                    davprop, adapter, req)
                response.addProperty(200, davwidget.render())
            except zope.security.interfaces.Unauthorized:
                # Users don't have the permission to view this property and
                # if they didn't explicitly ask for the named property
                # we can silently ignore this property, pretending that it
                # is a restricted property.
                if isIncluded:
                    self.handleException(
                        "{%s}%s" %(davprop.namespace, davprop.__name__),
                        sys.exc_info(), req, response)
                else:
                    # Considering that we just silently ignored this property
                    # - log this exception with the error reporting utility
                    # just in case this is a problem that needs sorting out.
                    errUtility = zope.component.getUtility(
                        IErrorReportingUtility)
                    errUtility.raising(sys.exc_info(), req)
            except:
                self.handleException(
                    "{%s}%s" %(davprop.namespace, davprop.__name__),
                    sys.exc_info(), req,
                    response)

        return response

    def renderSelectedProperties(self, ob, req, props, level = 0):
        response = z3c.dav.utils.Response(
            z3c.dav.utils.getObjectURL(ob, req))

        for prop in props:
            if z3c.dav.utils.parseEtreeTag(prop.tag)[0] == "":
                # XXX - A namespace which is None corresponds to when no
                # prefix is set, which I think is fine.
                raise z3c.dav.interfaces.BadRequest(
                    self.request,
                    u"PROPFIND with invalid namespace declaration in body")

            try:
                davprop, adapter = z3c.dav.properties.getProperty(
                    ob, req, prop.tag, exists = True)
                davwidget = z3c.dav.properties.getWidget(
                    davprop, adapter, req)
                propstat = response.getPropstat(200)
                propstat.properties.append(davwidget.render())
            except zope.security.interfaces.Unauthorized:
                if level == 0:
                    # When we are rendering properties on the requested
                    # resource then we must raise any Unauthorized exceptions
                    # so that user can then log in. But if the Unauthorized
                    # exception is on a sub resource to the requested resource
                    # then we can just handle this unauthorized exception.
                    raise
                self.handleException(prop.tag, sys.exc_info(), req, response)
            except:
                self.handleException(prop.tag, sys.exc_info(), req, response)

        return response
