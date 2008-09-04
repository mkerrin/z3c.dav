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
"""Miscellanous helper methods for implementing the WebDAV data model. See
datamodel.txt

$Id$
"""
__docformat__ = 'restructuredtext'

from zope import component
from zope import interface
from zope import schema
from zope.schema.interfaces import IField
from zope.schema.fieldproperty import FieldProperty

import z3c.etree
from z3c.dav.interfaces import IDAVProperty, IDAVWidget, IDAVInputWidget
from z3c.dav.interfaces import IOpaquePropertyStorage
import z3c.dav.widgets
import z3c.dav.utils

class DAVProperty(object):
    """

      >>> from zope.interface.verify import verifyObject
      >>> from zope.schema import getFields
      >>> from zope.interface.interfaces import IInterface
      >>> from coreproperties import IDAVResourcetype
      >>> prop = DAVProperty('{DAV:}resourcetype', IDAVResourcetype)
      >>> verifyObject(IDAVProperty, prop)
      True
      >>> prop.namespace
      'DAV:'
      >>> prop.__name__
      'resourcetype'
      >>> verifyObject(IInterface, prop.iface)
      True
      >>> prop.field in getFields(prop.iface).values()
      True
      >>> verifyObject(IField, prop.field)
      True
      >>> prop.custom_widget is None
      True
      >>> prop.restricted
      False

    """
    interface.implements(IDAVProperty)

    namespace = FieldProperty(IDAVProperty['namespace'])
    __name__  = FieldProperty(IDAVProperty['__name__'])
    ## XXX - If a developer writes his own field and passes it into
    ## DAVProperty then it is next to impossible to get the to validate
    ## correctly.
    ## field     = FieldProperty(IDAVProperty['field'])
    iface = FieldProperty(IDAVProperty['iface'])
    custom_widget = FieldProperty(IDAVProperty['custom_widget'])
    custom_input_widget = FieldProperty(IDAVProperty['custom_input_widget'])
    restricted = FieldProperty(IDAVProperty['restricted'])

    def __init__(self, tag, iface):
        namespace, name = z3c.dav.utils.parseEtreeTag(tag)
        self.namespace = namespace
        self.__name__  = name
        self.iface     = iface
        self.field     = iface[name]
        self.custom_widget = None
        self.custom_input_widget = None
        self.restricted    = False


_opaque_namespace_key = "z3c.dav.properties.DAVOpaqueProperties"

class DeadField(schema.Field):
    pass


class OpaqueWidget(z3c.dav.widgets.DAVWidget):

    def render(self):
        etree = z3c.etree.getEngine()
        el = etree.fromstring(self._value)
        return el


class OpaqueInputWidget(z3c.dav.widgets.DAVInputWidget):
    """

      >>> class Storage(object):
      ...    interface.implements(IOpaquePropertyStorage)
      ...    def __init__(self):
      ...        self.data = {}
      ...    def setProperty(self, tag, value):
      ...        self.data[tag] = value
      ...    def removeProperty(self, tag):
      ...        del self.data[tag]
      ...    def getProperty(self, tag):
      ...        return self.data[tag]
      >>> storage = Storage()

      >>> from cStringIO import StringIO
      >>> from z3c.dav.publisher import WebDAVRequest
      >>> reqdata = '''<propertyupdate xmlns="DAV:">
      ... <set>
      ...   <prop>
      ...     <high-unicode xmlns="http://webdav.org/neon/litmus/">&#65536;</high-unicode>
      ...   </prop>
      ... </set>
      ... </propertyupdate>'''
      >>> request = WebDAVRequest(StringIO(reqdata),
      ...    {'CONTENT_LENGTH': len(reqdata)})
      >>> request.processInputs()

      >>> prop = OpaqueProperty('{http://webdav.org/neon/litmus/}high-unicode')
      >>> widget = getWidget(prop, storage, request, type = IDAVInputWidget)

      >>> print widget.getInputValue() #doctest:+XMLDATA
      <ns0:high-unicode xmlns:ns0="http://webdav.org/neon/litmus/">\xf0\x90\x80\x80</ns0:high-unicode>

    """

    def getInputValue(self):
        el = self.request.xmlDataSource.findall(
            "{DAV:}set/{DAV:}prop/%s" % self.context.tag)

        etree = z3c.etree.getEngine()
        # XXX - ascii seems a bit wrong here
        return etree.tostring(el[-1], encoding="utf-8")


class IOpaqueField(IField):

    tag = schema.BytesLine(
        title = u"ElementTree tag",
        description = u"This is the key used by the opaque properties storage",
        required = True)


class OpaqueField(schema.Field):
    """

      >>> from zope.interface.verify import verifyObject
      >>> field = OpaqueField(__name__ = 'test',
      ...    title = u'Test opaque field',
      ...    tag = '{testns:}test')

      >>> IOpaqueField.providedBy(field)
      True
      >>> field.tag
      '{testns:}test'

      >>> from zope.interface.verify import verifyObject
      >>> field = OpaqueField(__name__ = 'test',
      ...    title = u'Test opaque field',
      ...    tag = 'test')
      >>> IOpaqueField.providedBy(field)
      True
      >>> field.tag
      'test'

    """
    interface.implements(IOpaqueField)

    tag = FieldProperty(IOpaqueField["tag"])

    def __init__(self, tag, **kw):
        super(OpaqueField, self).__init__(**kw)
        self.tag = tag

    def get(self, obj):
        return obj.getProperty(self.tag)

    def set(self, obj, value):
        obj.setProperty(self.tag, value)


class OpaqueProperty(object):
    """

      >>> from zope.interface.verify import verifyObject
      >>> prop = OpaqueProperty('{examplens:}testprop')
      >>> verifyObject(IDAVProperty, prop)
      True
      >>> IOpaqueField.providedBy(prop.field)
      True
      >>> prop.namespace
      'examplens:'

    The namespace part of a opaque property can be None.

      >>> prop = OpaqueProperty('testprop')
      >>> verifyObject(IDAVProperty, prop)
      True
      >>> IOpaqueField.providedBy(prop.field)
      True
      >>> prop.namespace is None
      True

    """
    interface.implements(IDAVProperty)

    def __init__(self, tag):
        namespace, name = z3c.dav.utils.parseEtreeTag(tag)
        self.__name__ = name
        self.namespace = namespace
        self.iface = IOpaquePropertyStorage
        self.field = OpaqueField(
            __name__ = name,
            tag = tag,
            title = u"",
            description = u"")
        self.custom_widget = OpaqueWidget
        self.custom_input_widget = OpaqueInputWidget
        self.restricted = False


def getAllProperties(context, request):
    for name, prop in component.getUtilitiesFor(IDAVProperty):
        adapter = component.queryMultiAdapter((context, request),
                                              prop.iface,
                                              default = None)
        if adapter is None:
            continue

        yield prop, adapter

    adapter = IOpaquePropertyStorage(context, None)
    if adapter is None:
        raise StopIteration

    for tag in adapter.getAllProperties():
        yield OpaqueProperty(tag), adapter


def hasProperty(context, request, tag):
    prop = component.queryUtility(IDAVProperty, name = tag, default = None)
    if prop is None:
        adapter = IOpaquePropertyStorage(context, None)
        if adapter is not None and adapter.hasProperty(tag):
            return True
        return False

    adapter = component.queryMultiAdapter((context, request), prop.iface,
                                          default = None)
    if adapter is None:
        return False

    return True


def getProperty(context, request, tag, exists = False):
    prop = component.queryUtility(IDAVProperty, name = tag, default = None)
    if prop is None:
        adapter = IOpaquePropertyStorage(context, None)
        if adapter is None:
            ## XXX - should we use the zope.publisher.interfaces.NotFound
            ## exceptin here.
            raise z3c.dav.interfaces.PropertyNotFound(context, tag, tag)

        if exists and not adapter.hasProperty(tag):
            ## XXX - should we use the zope.publisher.interfaces.NotFound
            ## exceptin here.
            raise z3c.dav.interfaces.PropertyNotFound(context, tag, tag)

        return OpaqueProperty(tag), adapter

    adapter = component.queryMultiAdapter((context, request), prop.iface,
                                          default = None)
    if adapter is None:
        ## XXX - should we use the zope.publisher.interfaces.NotFound
        ## exceptin here.
        raise z3c.dav.interfaces.PropertyNotFound(context, tag, tag)

    return prop, adapter


def getWidget(prop, adapter, request, type = IDAVWidget):
    """prop.field describes the data we want to render.
    """
    if type is IDAVWidget and prop.custom_widget is not None:
        widget = prop.custom_widget(prop.field, request)
    elif type is IDAVInputWidget and prop.custom_input_widget is not None:
        widget = prop.custom_input_widget(prop.field, request)
    else:
        widget = component.getMultiAdapter((prop.field, request), type)

    if IDAVWidget.providedBy(widget):
        field = prop.field.bind(adapter)
        widget.setRenderedValue(field.get(adapter))

    widget.namespace = prop.namespace

    return widget
