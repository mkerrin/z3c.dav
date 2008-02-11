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
"""Definition of all properties defined in the WebDAV specificiation.

  o readonly -> that the property is protected.

$Id$
"""
__docformat__ = 'restructuredtext'

from zope import interface
from zope import component
from zope import schema
import zope.app.container.interfaces
import zope.publisher.interfaces.http

from z3c.dav.properties import DAVProperty, DeadField
import z3c.dav.widgets

class IDAVCreationdate(interface.Interface):

    creationdate = schema.Datetime(
        title = u"Records the time and date the resource was created.",
        description = u"""The DAV:creationdate property SHOULD be defined on
                          all DAV compliant resources.  If present, it
                          contains a timestamp of the moment when the resource
                          was created.  Servers that are incapable of
                          persistently recording the creation date SHOULD
                          instead leave it undefined (i.e. report
                          "Not Found" """,
        readonly = True)


class IDAVDisplayname(interface.Interface):

    displayname = schema.TextLine(
        title = u"Provides a name for the resource that is suitable for presentation to a user.",
        description = u"""Contains a description of the resource that is
                          suitable for presentation to a user.  This property
                          is defined on the resource, and hence SHOULD have
                          the same value independent of the Request-URI used
                          to retrieve it (thus computing this property based
                          on the Request-URI is deprecated).  While generic
                          clients might display the property value to end
                          users, client UI designers must understand that the
                          method for identifying resources is still the URL.
                          Changes to DAV:displayname do not issue moves or
                          copies to the server, but simply change a piece of
                          meta-data on the individual resource.  Two resources
                          can have the same DAV:displayname value even within
                          the same collection.""",
        readonly = False)


class IDAVGetcontentlanguage(interface.Interface):

    getcontentlanguage = schema.TextLine(
        title = u"GET Content-Language header.",
        description = u"""Contains the Content-Language header value (from
                          Section 14.12 of [RFC2616]) as it would be returned
                          by a GET without accept headers.

                          The DAV:getcontentlanguage property MUST be defined
                          on any DAV compliant resource that returns the
                          Content-Language header on a GET.""",
        readonly = False)


class IDAVGetcontentlength(interface.Interface):

    getcontentlength = schema.Int(
        title = u"Contains the Content-Length header returned by a GET without accept headers.",
        description = u"""The DAV:getcontentlength property MUST be defined on
                          any DAV compliant resource that returns the
                          Content-Length header in response to a GET.""",
        readonly = True)


class IDAVGetcontenttype(interface.Interface):

    getcontenttype = schema.TextLine(
        title = u"Contains the Content-Type header value as it would be returned by a GET without accept headers.",
        description = u"""This property MUST be defined on any DAV compliant
                          resource that returns the Content-Type header in
                          response to a GET.""",
        readonly = False)


class IDAVGetetag(interface.Interface):

    getetag = schema.TextLine(
        title = u"Contains the ETag header value as it would be returned by a GET without accept headers.",
        description = u"""The getetag property MUST be defined on any DAV
                          compliant resource that returns the Etag header.
                          Refer to Section 3.11 of RFC2616 for a complete
                          definition of the semantics of an ETag, and to
                          Section 8.6 for a discussion of ETags in WebDAV.""",
        readonly = True)


class IDAVGetlastmodified(interface.Interface):

    getlastmodified = schema.Datetime(
        title = u"Contains the Last-Modified header value as it would be returned by a GET method without accept headers.",
        description = u"""Note that the last-modified date on a resource SHOULD
                          only reflect changes in the body (the GET responses)
                          of the resource.  A change in a property only SHOULD
                          NOT cause the last-modified date to change, because
                          clients MAY rely on the last-modified date to know
                          when to overwrite the existing body.  The
                          DAV:getlastmodified property MUST be defined on any
                          DAV compliant resource that returns the
                          Last-Modified header in response to a GET.""",
        readonly = True)


class ILockEntry(interface.Interface):
    """A DAV Sub property of the supportedlock property.
    """
    lockscope = schema.List(
        title = u"Describes the exclusivity of a lock",
        description = u"""Specifies whether a lock is an exclusive lock, or a
                          shared lock.""",
        required = True,
        readonly = True)

    locktype = schema.List(
        title = u"Describes the access type of the lock.",
        description = u"""Specifies the access type of a lock. At present,
                          this specification only defines one lock type, the
                          write lock.""",
        required = True,
        readonly = True)


class IActiveLock(ILockEntry):
    """A DAV Sub property of the lockdiscovery property.
    """
    depth = schema.Text(
        title = u"Depth",
        description = u"The value of the Depth header.",
        required = False,
        readonly = True)

    owner = DeadField(
        title = u"Owner",
        description = u"""The owner XML element provides information sufficient
                          for either directly contacting a principal (such as a
                          telephone number or Email URI), or for discovering the
                          principal (such as the URL of a homepage) who created
                          a lock.

                          The value provided MUST be treated as a dead property
                          in terms of XML Information Item preservation.  The
                          server MUST NOT alter the value unless the owner
                          value provided by the client is empty.
                          """,
        required = False,
        readonly = True)

    timeout = schema.Text(
        title = u"Timeout",
        description = u"The timeout associated with a lock",
        required = False,
        readonly = True)

    locktoken = schema.List(
        title = u"Lock Token",
        description = u"""The href contains one or more opaque lock token URIs
                          which all refer to the same lock (i.e., the
                          OpaqueLockToken-URI production in section 6.4).""",
        value_type = schema.URI(
              __name__ = u"href",
              title = u"Href",
              description = u"""The href contains a single lock token URI
                                which refers to the lock.""",
              ),
        required = False,
        readonly = True,
        max_length = 1)

    lockroot = schema.URI(
        title = u"Lock root",
        description = u"""
        """,
        readonly = True,
        required = True)


class IDAVLockdiscovery(interface.Interface):

    lockdiscovery = schema.List(
        title = u"Describes the active locks on a resource",
        description = u"""Returns a listing of who has a lock, what type of
                          lock he has, the timeout type and the time remaining
                          on the timeout, and the associated lock token.  If
                          there are no locks, but the server supports locks,
                          the property will be present but contain zero
                          'activelock' elements.  If there is one or more
                          lock, an 'activelock' element appears for each lock
                          on the resource.  This property is NOT lockable with
                          respect to write locks (Section 7).""",
        value_type = schema.Object(
            __name__ = "activelock",
            title = u"",
            schema = IActiveLock,
            readonly = True),
        readonly = True)


class IDAVResourcetype(interface.Interface):

    resourcetype = schema.List(
        title = u"Specifies the nature of the resource.",
        description = u"""MUST be defined on all DAV compliant resources.  Each
                          child element identifies a specific type the
                          resource belongs to, such as 'collection', which is
                          the only resource type defined by this specification
                          (see Section 14.3).  If the element contains the
                          'collection' child element plus additional
                          unrecognized elements, it should generally be
                          treated as a collection.  If the element contains no
                          recognized child elements, it should be treated as a
                          non-collection resource.  The default value is empty.
                          This element MUST NOT contain text or mixed content.
                          Any custom child element is considered to be an
                          identifier for a resource type.""",
        readonly = True)


class IDAVSupportedlock(interface.Interface):

    supportedlock = schema.List(
        title = u"To provide a listing of the lock capabilities supported by the resource.",
        description = u"""Returns a listing of the combinations of scope and
                          access types which may be specified in a lock
                          request on the resource.  Note that the actual
                          contents are themselves controlled by access
                          controls so a server is not required to provide
                          information the client is not authorized to see.
                          This property is NOT lockable with respect to
                          write locks (Section 7).""",
        value_type = schema.Object(
            __name__ = "lockentry",
            title = u"",
            schema = ILockEntry,
            readonly = True),
        readonly = True)


class IDAVCoreSchema(IDAVCreationdate,
                     IDAVDisplayname,
                     IDAVGetlastmodified):
    """Base core properties - note that resourcetype is complusory and is in
    its own interface.
    """


class IDAVGetSchema(IDAVGetcontentlanguage,
                    IDAVGetcontentlength,
                    IDAVGetcontenttype,
                    IDAVGetetag):
    """Extended properties that only apply to certain content.
    """


class IDAVLockSupport(IDAVLockdiscovery,
                      IDAVSupportedlock):
    """
    """


class LockdiscoveryDAVWidget(z3c.dav.widgets.ListDAVWidget):
    """
    Custom widget for the `{DAV:}lockdiscovery` property. This is basically
    a list widget but it doesn't display any sub XML element whose value
    is equal to its field missing_value.

      >>> import zope.schema.interfaces
      >>> from z3c.dav.tests import test_widgets

    Setup some adapters for rendering the widget.

      >>> gsm = component.getGlobalSiteManager()
      >>> gsm.registerAdapter(z3c.dav.widgets.TextDAVWidget,
      ...                     (zope.schema.interfaces.IText, None))
      >>> gsm.registerAdapter(z3c.dav.widgets.IntDAVWidget,
      ...                     (zope.schema.interfaces.IInt, None))

    Setup a field and test object to render. While this is not the same field
    as the `{DAV:}lockdiscovery` property but it is lot easier to work with
    during the tests.

      >>> field = schema.List(__name__ = 'testelement',
      ...    title = u'Test field',
      ...    value_type = schema.Object(
      ...        __name__ = u'testsubelement',
      ...        title = u'Test sub element',
      ...        schema = test_widgets.ISimpleInterface))
      >>> objectvalue = test_widgets.SimpleObject(name = None, age = 26)

      >>> widget = LockdiscoveryDAVWidget(field, None)
      >>> widget.namespace = 'DAV:'
      >>> widget.setRenderedValue([objectvalue])

    The objectvalue name is None which is equal the Text field missing_value
    so the name sub XML element doesn't show up.

      >>> print etree.tostring(widget.render()) #doctest:+XMLDATA
      <testelement xmlns='DAV:'>
        <testsubelement>
          <age>26</age>
        </testsubelement>
      </testelement>

    By setting the name attribute it now shows up in the output.

      >>> objectvalue.name = u'Michael Kerrin'
      >>> print etree.tostring(widget.render()) #doctest:+XMLDATA
      <testelement xmlns='DAV:'>
        <testsubelement>
          <name>Michael Kerrin</name>
          <age>26</age>
        </testsubelement>
      </testelement>

    But the content object needs to be locked for the `{DAV:}lockdiscovery`
    element to have a value.

      >>> widget.setRenderedValue(None)
      >>> print etree.tostring(widget.render()) #doctest:+XMLDATA
      <testelement xmlns='DAV:' />

    Clean up the component registration.

      >>> gsm.unregisterAdapter(z3c.dav.widgets.TextDAVWidget,
      ...                       (zope.schema.interfaces.IText, None))
      True
      >>> gsm.unregisterAdapter(z3c.dav.widgets.IntDAVWidget,
      ...                       (zope.schema.interfaces.IInt, None))
      True

    """
    interface.classProvides(z3c.dav.interfaces.IIDAVWidget)

    def render(self):
        etree = z3c.etree.getEngine()
        el = etree.Element(etree.QName(self.namespace, self.name))

        if self._value is not self.context.missing_value:
            for value in self._value:
                widget = z3c.dav.widgets.ObjectDAVWidget(
                    self.context.value_type, self.request)
                widget.render_missing_values = False
                widget.setRenderedValue(value)
                widget.namespace = self.namespace
                el.append(widget.render())

        return el


################################################################################
#
# Collection of default properties has defined in Section 15.
# subsection 1 -> 10 of draft-ietf-webdav-rfc2518bis-15.txt
#
################################################################################

creationdate = DAVProperty("{DAV:}creationdate", IDAVCreationdate)
creationdate.custom_widget = z3c.dav.widgets.ISO8601DatetimeDAVWidget

displayname = DAVProperty("{DAV:}displayname", IDAVDisplayname)

getcontentlanguage = DAVProperty("{DAV:}getcontentlanguage",
                                 IDAVGetcontentlanguage)

getcontentlength = DAVProperty("{DAV:}getcontentlength", IDAVGetcontentlength)

getcontenttype = DAVProperty("{DAV:}getcontenttype", IDAVGetcontenttype)

getetag = DAVProperty("{DAV:}getetag", IDAVGetetag)

getlastmodified = DAVProperty("{DAV:}getlastmodified", IDAVGetlastmodified)

resourcetype = DAVProperty("{DAV:}resourcetype", IDAVResourcetype)

lockdiscovery = DAVProperty("{DAV:}lockdiscovery", IDAVLockdiscovery)
lockdiscovery.custom_widget = LockdiscoveryDAVWidget

supportedlock = DAVProperty("{DAV:}supportedlock", IDAVSupportedlock)

################################################################################
#
# Default storage adapter for the only mandatory property.
#
################################################################################

class ResourceTypeAdapter(object):
    """

    All content that doesn't implement the IReadContainer interface, their
    resourcetype value is None.

      >>> class Resource(object):
      ...    pass
      >>> resource = Resource()
      >>> adapter = ResourceTypeAdapter(resource, None)
      >>> adapter.resourcetype is None
      True

    If a content object implements IReadContainer then it value is a list
    of types, just 'collection' in this case.

      >>> from zope.app.folder.folder import Folder
      >>> folder = Folder()
      >>> adapter = ResourceTypeAdapter(folder, None)
      >>> adapter.resourcetype
      [u'collection']

    """
    interface.implements(IDAVResourcetype)
    component.adapts(interface.Interface,
                     zope.publisher.interfaces.http.IHTTPRequest)

    def __init__(self, context, request):
        self.context = context

    @property
    def resourcetype(self):
        if zope.app.container.interfaces.IReadContainer.providedBy(
            self.context):
            return [u'collection']
        return None
