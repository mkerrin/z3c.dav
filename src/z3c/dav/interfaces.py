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
"""WebDAV-specific interfaces

$Id$
"""
__docformat__ = 'restructuredtext'

import UserDict
from zope import interface
from zope.interface.interfaces import IInterface
from zope.interface.common.interfaces import IException
from zope.interface.common.mapping import IMapping
from zope.interface.common.sequence import IFiniteSequence
from zope import schema
from zope.schema.interfaces import IField
from zope.component.interfaces import IView

from zope.publisher.interfaces.http import IHTTPRequest, IHTTPResponse
from zope.app.publication.interfaces import IRequestFactory

################################################################################
#
# Common WebDAV specific errors
#
################################################################################

class IBadRequest(IException):
    """
    Some information passed in the request is in invalid.
    """

    request = interface.Attribute("""The request in which the error occured.""")

    message = interface.Attribute("""Message to send back to the user.""")

class BadRequest(Exception):
    interface.implements(IBadRequest)

    def __init__(self, request, message = None):
        self.request = request
        self.message = message

    def __str__(self):
        return "%r, %r" %(self.request, self.message)


class IUnsupportedMediaType(IException):
    """
    Unsupported media type.
    """

    context = interface.Attribute(""" """)

    message = interface.Attribute(""" """)

class UnsupportedMediaType(Exception):
    interface.implements(IUnsupportedMediaType)

    def __init__(self, context, message = u""):
        self.context = context
        self.message = message

    def __str__(self):
        return "%r, %r" %(self.context, self.message)


class IBadGateway(IException):
    """
    The server, while acting as a gateway or proxy, received an invalid
    response from the upstream server it accessed in attempting to
    fulfill the request.
    """

    context = interface.Attribute(""" """)

    request = interface.Attribute(""" """)

class BadGateway(Exception):
    interface.implements(IBadGateway)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __str__(self):
        return "%r, %r" %(self.context, self.request)


class IDAVException(IException):
    """
    Base interface for a common set of exceptions that should be raised
    to inform the client that something has gone a bit to the left.
    """

    resource = interface.Attribute("""
    Possible resource on which this error was raised.
    """)

    ## XXX - this attribute was added has an after-thought. It currently
    ## isn't being used and has such it properly should be removed.
    propertyname = interface.Attribute("""
    Possible property name for which the error applies.
    """)

    message = interface.Attribute("""
    Human readable message detailing what went wrong.
    """)

class DAVException(Exception):

    def __init__(self, resource, propertyname = None, message = None):
        self.resource = resource
        self.propertyname = propertyname
        self.message = message

    def __str__(self):
        return self.message


class IConflictError(IDAVException):
    """
    The client has provided a value whose semantics are not appropriate for
    current state of the resource.
    """

class ConflictError(DAVException):
    interface.implements(IConflictError)


class IForbiddenError(IDAVException):
    """
    The client, for reasons the server chooses not to specify, cannot alter
    the resource.
    """

class ForbiddenError(DAVException):
    interface.implements(IForbiddenError)


class IUnprocessableError(IDAVException):
    """
    The entity body couldn't be parsed or is invalid.
    """

class UnprocessableError(DAVException):
    interface.implements(IUnprocessableError)


# XXX - PropertyNotFound should go away and instead we should
# reuse the NotFound exception
class IPropertyNotFound(IDAVException):
    """
    The requested property was not found.
    """

class PropertyNotFound(DAVException):
    interface.implements(IPropertyNotFound)


class IPreconditionFailed(IDAVException):
    """
    Some condition header failed to evalute to True.
    """

class PreconditionFailed(DAVException):
    interface.implements(IPreconditionFailed)


class IFailedDependency(IDAVException):
    """
    Method could not be performed on the resource because the requested
    action depended on another action and that action failed.
    """

class FailedDependency(DAVException):
    interface.implements(IFailedDependency)


class IAlreadyLocked(IDAVException):
    """
    The resource is already locked.
    """

class AlreadyLocked(Exception):
    interface.implements(IAlreadyLocked)

    def __init__(self, context, message = None):
        self.resource = context
        self.propertyname = None
        self.message = None

    def __str__(self):
        # This stops zope.app.error.error from failing in getPrintable
        return "%r: %r" %(self.resource, self.message)


class IWebDAVErrors(IFiniteSequence, IException):
    """
    List-like container of all exceptions that occured during the process
    of a request. All the exceptions should be viewed and returned to the
    client via a multi-status response.
    """

    def append(error):
        """
        Append a error to the collection of errors.
        """

class WebDAVErrors(Exception):
    """
    Collect has many errors has we can and then provide a view of all the
    errors to the user.
    """
    interface.implements(IWebDAVErrors)

    def __init__(self, context, errors = ()):
        Exception.__init__(self)
        self.errors = errors
        self.context = context

    def append(self, error):
        self.errors += (error,)

    def __len__(self):
        return len(self.errors)

    def __iter__(self):
        return iter(self.errors)

    def __getitem__(self, index):
        return self.errors[index]


class IWebDAVPropstatErrors(IMapping, IException):
    """
    Exception containing a mapping of property names to exceptions. This is
    used to collect all the exceptions that occured when modifying the
    properties on a resource.
    """

    context = interface.Attribute("""
    The context on which all the properties are defined.
    """)

class WebDAVPropstatErrors(UserDict.IterableUserDict, Exception):
    interface.implements(IWebDAVPropstatErrors)

    def __init__(self, context):
        ## Allowing users to pass the list of errors into this exception
        ## is causing problems. This optional dictionary was remembering
        ## the arguements from previous functional tests.
        ## See the test_remove_live_prop in test_propfind.
        UserDict.IterableUserDict.__init__(self)
        Exception.__init__(self)
        self.context = context

################################################################################
#
# WebDAV related publication interfaces.
#
################################################################################

class IWebDAVMethod(interface.Interface):
    """
    A object implementing this method is a callable object that implements
    one of the WebDAV specific methods.
    """


class IWebDAVResponse(IHTTPResponse):
    """
    A WebDAV Response object.
    """


class IWebDAVRequest(IHTTPRequest):
    """
    A WebDAV Request.

    This request should only be used to respond to a WebDAV specific request
    that contains either XML or nothing has a payload.
    """

    xmlDataSource = interface.Attribute("""
    xml.dom.Document instance representing the input stream has an XML document.

    If there was no input or the input wasn't in XML then this attribute
    is None.
    """)

    content_type = interface.Attribute("""
    A string representing the content type of the input stream without any
    parameters.
    """)


class IWebDAVRequestFactory(IRequestFactory):
    """
    WebDAV request factory.
    """

################################################################################
#
# WebDAV interfaces for widgets, properties and management of the widgets
# and properties.
#
################################################################################

class IBaseDAVWidget(IView):
    """
    DAVWidget are views of IDAVProperty objects, generally used by PROPFIND

     - context is a IDAVProperty.

     - request is a IHTTPRequest.

    """

    name = interface.Attribute("""
    The local naem of the property.
    """)

    namespace = interface.Attribute("""
    The XML namespace to which the property belongs.
    """)


class IIDAVWidget(IInterface):
    """
    Meta-interface marker for classes that when instanciated will implement
    IDAVWidget.
    """


class IIDAVInputWidget(IInterface):
    """
    Meta-interface marker for classes that when instanciated will implement
    IDAVInputWidget.
    """


class IDAVInputWidget(IBaseDAVWidget):
    """
    For use with in the PROPPATCH method.
    """

    def toFieldValue(element):
        """
        Convert the ElementTree element to a value which can be legally
        assigned to the field.
        """

    def getInputValue():
        """
        Return value suitable for the widget's field.

        The widget must return a value that can be legally assigned to
        its bound field or otherwise raise ``WidgetInputError``.

        The return value is not affected by `setRenderedValue()`.
        """

    def hasInput():
        """
        Returns ``True`` if the widget has input.

        Input is used by the widget to calculate an 'input value', which is
        a value that can be legally assigned to a field.

        Note that the widget may return ``True``, indicating it has input, but
        still be unable to return a value from `getInputValue`. Use
        `hasValidInput` to determine whether or not `getInputValue` will return
        a valid value.

        A widget that does not have input should generally not be used
        to update its bound field.  Values set using
        `setRenderedValue()` do not count as user input.

        A widget that has been rendered into a form which has been
        submitted must report that it has input.  If the form
        containing the widget has not been submitted, the widget
        shall report that it has no input.
        """


class IDAVWidget(IBaseDAVWidget):
    """
    For use in rendering dav properties.
    """

    def render():
        """
        Render the property to a XML fragment, according to the relevent
        specification.
        """


class IDAVErrorWidget(interface.Interface):
    """
    Widget used to render any errors that should be included in a multi-status
    response.
    """

    status = interface.Attribute("""
    The HTTP status code.
    """)

    errors = interface.Attribute("""
    List of etree elements that is a precondition or a postcondition code.
    """)

    propstatdescription = interface.Attribute("""
    Contains readable information about an error that occured and applies
    to all properties contained within the current propstat XML element.
    """)

    responsedescription = interface.Attribute("""
    Contains readable information about an error that occured and applies to
    all resources contained within the current response XML element.
    """)

################################################################################
#
# Namespace management
#
################################################################################

class IDAVProperty(interface.Interface):
    """
    Data structure that holds information about a live WebDAV property.
    """

    __name__ = schema.ASCII(
        title = u"Name",
        description = u"Local name of the WebDAV property.",
        required = True)

    namespace = schema.URI(
        title = u"Namespace",
        description = u"WebDAV namespace to which this property belongs.",
        required = True)

    field = schema.Object(
        title = u"Field",
        description = u"""Zope schema field that defines the data of the live
                          WebDAV property.""",
        schema = IField,
        required = True)

    custom_widget = schema.Object(
        title = u"Custom Widget",
        description = u"""Factory to use for widget construction. If None then
                          a multi-adapter implementing IDAVWidget.""",
        default = None,
        schema = IIDAVWidget,
        required = False)

    custom_input_widget = schema.Object(
        title = u"Custom Input Widget",
        description = u"""Factory to use for widget construction. If None then
                          a multi-adapter implementing IDAVInputWidget.""",
        default = None,
        schema = IIDAVInputWidget,
        required = False)

    restricted = schema.Bool(
        title = u"Restricted property",
        description = u"""If True then this property should not be included in
                          the response to an allprop PROPFIND request.""",
        default = False,
        required = False)

    iface = schema.Object(
        title = u"Storage interface",
        description = u"""Interface which declares how to find, store
                          the property""",
        schema = IInterface,
        required = True)

################################################################################
#
# Application specific interfaces.
#
################################################################################

class IOpaquePropertyStorage(interface.Interface):
    """
    Declaration of an adapter that is used to store, remove and query all
    dead properties on a resource.
    """

    def getAllProperties():
        """
        Return iterable of all IDAVProperty objects defined for the
        current context.
        """

    def hasProperty(tag):
        """
        Return boolean indicating whether the named property exists has
        a dead property for the current resource.
        """

    def getProperty(tag):
        """
        Return a IDAVProperty utility for the named property.
        """

    def setProperty(tag, value):
        """
        Set the value of the named property to value.
        """

    def removeProperty(tag):
        """
        Remove the named property from this property.
        """


class IDAVLockmanager(interface.Interface):
    """
    Helper adapter for manage locks in an independent manner. Different
    Zope systems are going to have there own locking mechanisms for example
    Zope3 and CPS have two conflicting locking mechanisms.
    """

    def islockable():
        """
        Return False when the current context can never be locked or locking
        is not support in your setup.

        For example in Zope3, z3c.dav.lockingutils.DAVLockmanager depends
        on a persistent zope.locking.interfaces.ITokenUtility utility being
        present and registered. If this utility can not be locked be then
        we can never use this implementation of IDAVLockmanager.
        """

    def lock(scope, type, owner, duration, depth):
        """
        Lock the current context passing in all the possible information
        neccessary for generating a lock token.

        If the context can't be locked raise an exception that has a
        corresponding IDAVErrorWidget implementation so that we can extract
        what went wrong.

        If `depth` has the value `infinity` and the context is a folder then
        recurse through all the subitems locking them has you go.

        Raise a AlreadyLockedError if some resource is already locked.

        Return the locktoken associated with the token that we just created.
        """

    def refreshlock(timeout):
        """
        Refresh to lock token associated with this resource.
        """

    def unlock(locktoken):
        """
        Find the lock token on this resource with the same locktoken as the
        argument and unlock it.
        """

    def islocked():
        """
        Is the current context locked or not. Return True, otherwise False.
        """
