##############################################################################
# Copyright (c) 2003 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
##############################################################################
"""Basic WebDAV storage adapters for Files and Folders content objects.
"""
__docformat__ = 'restructuredtext'

from BTrees.OOBTree import OOBTree

import zope.interface
import zope.annotation.interfaces
from zope.dublincore.interfaces import IDCTimes, IDCDescriptiveProperties

import z3c.dav.coreproperties


class DAVDublinCore(object):
    """
    Common data model that uses zope.dublincore package to handle the
    `{DAV:}creationdate`, `{DAV:}displayname` or title, and the
    `{DAV:}getlastmodified` WebDAV properties.

      >>> from zope.dublincore.annotatableadapter import ZDCAnnotatableAdapter
      >>> from zope.dublincore.interfaces import IWriteZopeDublinCore
      >>> from zope.annotation.attribute import AttributeAnnotations
      >>> from zope import component
      >>> import datetime
      >>> from zope.datetime import tzinfo

    Create some sample content

      >>> class Resource(object):
      ...    pass
      >>> resource = Resource()

    With no IZopeDublinCore adapters register all properties return None.

      >>> adapter = DAVDublinCore(resource, None)
      >>> adapter.displayname is None
      True
      >>> adapter.creationdate is None
      True
      >>> adapter.displayname = u'Test File Title'
      Traceback (most recent call last):
      ...
      ValueError
      >>> adapter.getlastmodified is None
      True

    Now define the IZopeDublinCore adapters, the properties can now have
    non None values.

      >>> zope.interface.classImplements(Resource,
      ...    zope.annotation.interfaces.IAttributeAnnotatable)
      >>> component.getGlobalSiteManager().registerAdapter(
      ...     AttributeAnnotations)
      >>> component.getGlobalSiteManager().registerAdapter(
      ...     ZDCAnnotatableAdapter, provided = IWriteZopeDublinCore)

      >>> IWriteZopeDublinCore(resource).created = now = datetime.datetime(
      ...     2006, 5, 24, 0, 0, 58, tzinfo = tzinfo(60))
      >>> IWriteZopeDublinCore(resource).title = u'Example Test File'
      >>> IWriteZopeDublinCore(resource).modified = now = datetime.datetime(
      ...     2006, 5, 24, 0, 0, 58, tzinfo = tzinfo(60))

      >>> adapter.creationdate == now
      True
      >>> adapter.displayname
      u'Example Test File'
      >>> adapter.getlastmodified == now
      True
      >>> adapter.displayname = u'Changed Test File Title'
      >>> IWriteZopeDublinCore(resource).title
      u'Changed Test File Title'

    Cleanup

      >>> component.getGlobalSiteManager().unregisterAdapter(
      ...     AttributeAnnotations,
      ...     provided = zope.annotation.interfaces.IAnnotations)
      True
      >>> component.getGlobalSiteManager().unregisterAdapter(
      ...     ZDCAnnotatableAdapter, provided = IWriteZopeDublinCore)
      True

    """
    zope.interface.implements(z3c.dav.coreproperties.IDAVCoreSchema)

    def __init__(self, context, request):
        self.context = context

    @property
    def creationdate(self):
        dc = IDCTimes(self.context, None)
        if dc is None or dc.created is None:
            return None
        return dc.created

    @apply
    def displayname():
        def get(self):
            descproperties = IDCDescriptiveProperties(self.context, None)
            if descproperties is None:
                return None
            return descproperties.title
        def set(self, value):
            descproperties = IDCDescriptiveProperties(self.context, None)
            if descproperties is None:
                raise ValueError("")
            descproperties.title = value
        return property(get, set)

    @property
    def getlastmodified(self):
        dc = IDCTimes(self.context, None)
        if dc is None or dc.modified is None:
            return None
        return dc.modified


_opaque_namespace_key = "z3c.dav.deadproperties.DAVOpaqueProperties"

class OpaqueProperties(object):
    """
      >>> from zope.annotation.attribute import AttributeAnnotations
      >>> from zope.interface.verify import verifyObject
      >>> from zope import component
      >>> component.getGlobalSiteManager().registerAdapter(
      ...     AttributeAnnotations,
      ...     (zope.annotation.interfaces.IAnnotatable,),
      ...      zope.annotation.interfaces.IAnnotations)

    Initiial the object contains no dead properties.

      >>> class DemoContent(object):
      ...     zope.interface.implements(zope.annotation.interfaces.IAnnotatable)
      >>> resource = DemoContent()
      >>> opaqueProperties = OpaqueProperties(resource)
      >>> verifyObject(z3c.dav.interfaces.IOpaquePropertyStorage,
      ...              opaqueProperties)
      True
      >>> annotations = zope.annotation.interfaces.IAnnotations(resource)
      >>> list(annotations)
      []
      >>> list(opaqueProperties.getAllProperties())
      []

    `hasProperty` returns None since we haven't set any properties yet.

      >>> opaqueProperties.hasProperty('{example:}testprop')
      False
      >>> opaqueProperties.getProperty('{example:}testprop') is None
      True
      >>> annotations = zope.annotation.interfaces.IAnnotations(resource)
      >>> list(annotations)
      []

    Set the testprop property

      >>> opaqueProperties.setProperty('{examplens:}testprop',
      ...   '<E:testprop xmlns:E="examplens:">Test Property Value</E:testprop>')
      >>> annotations = zope.annotation.interfaces.IAnnotations(resource)
      >>> list(annotations[_opaque_namespace_key])
      ['{examplens:}testprop']
      >>> annotations[_opaque_namespace_key]['{examplens:}testprop']
      '<E:testprop xmlns:E="examplens:">Test Property Value</E:testprop>'
      >>> opaqueProperties.hasProperty('{examplens:}testprop')
      True
      >>> opaqueProperties.getProperty('{examplens:}testprop')
      '<E:testprop xmlns:E="examplens:">Test Property Value</E:testprop>'
      >>> list(opaqueProperties.getAllProperties())
      ['{examplens:}testprop']
      >>> opaqueProperties.hasProperty('{examplens:}testbadprop')
      False

    Now we will remove the property we just set up.

      >>> opaqueProperties.removeProperty('{examplens:}testprop')
      >>> annotations = zope.annotation.interfaces.IAnnotations(resource)
      >>> list(annotations[_opaque_namespace_key])
      []

    Test multiple sets to this value.

      >>> opaqueProperties.setProperty('{examplens:}prop0',
      ...    '<E:prop0 xmlns:E="examplens:">PROP0</E:prop0>')
      >>> opaqueProperties.setProperty('{examplens:}prop1',
      ...    '<E:prop1 xmlns:E="examplens:">PROP1</E:prop1>')
      >>> opaqueProperties.setProperty('{examplens:}prop2',
      ...    '<E:prop2 xmlns:E="examplens:">PROP2</E:prop2>')
      >>> list(opaqueProperties.getAllProperties())
      ['{examplens:}prop0', '{examplens:}prop1', '{examplens:}prop2']

      >>> opaqueProperties.removeProperty('{examplens:}prop0')
      >>> opaqueProperties.removeProperty('{examplens:}prop1')
      >>> list(opaqueProperties.getAllProperties())
      ['{examplens:}prop2']

    The key for the opaque storage is the ElementTree tag. The namespace
    part of this key can be None.

      >>> opaqueProperties.setProperty('prop2',
      ...    '<E:prop2 xmlns:E="examplens:">PROP2</E:prop2>')
      >>> opaqueProperties.hasProperty('prop2')
      True
      >>> opaqueProperties.getProperty('prop2')
      '<E:prop2 xmlns:E="examplens:">PROP2</E:prop2>'
      >>> opaqueProperties.removeProperty('prop2')
      >>> list(opaqueProperties.getAllProperties())
      ['{examplens:}prop2']

    Cleanup this test.

      >>> component.getGlobalSiteManager().unregisterAdapter(
      ...     AttributeAnnotations,
      ...     (zope.annotation.interfaces.IAnnotatable,),
      ...      zope.annotation.interfaces.IAnnotations)
      True

    """
    zope.interface.implements(z3c.dav.interfaces.IOpaquePropertyStorage)

    _annotations = None

    def __init__(self, context):
        # __parent__ must be set in order for the security to work
        self.__parent__ = context
        annotations = zope.annotation.interfaces.IAnnotations(context)
        oprops = annotations.get(_opaque_namespace_key)
        if oprops is None:
            self._annotations = annotations
            oprops = OOBTree()

        self._mapping = oprops

    def _changed(self):
        if self._annotations is not None:
            self._annotations[_opaque_namespace_key] = self._mapping
            self._annotations = None

    def getAllProperties(self):
        for tag in self._mapping.keys():
            yield tag

    def hasProperty(self, tag):
        return tag in self._mapping

    def getProperty(self, tag):
        """Returns None."""
        return self._mapping.get(tag, None)

    def setProperty(self, tag, value):
        self._mapping[tag] = value
        self._changed()

    def removeProperty(self, tag):
        del self._mapping[tag]
        self._changed()

################################################################################
#
# GetEtag property based on z3c.conditionalviews.
#
################################################################################

class Getetag(object):
    zope.interface.implements(z3c.dav.coreproperties.IDAVGetetag)

    def __init__(self, etag):
        self.getetag = etag


@zope.component.adapter(
    zope.interface.Interface, zope.publisher.interfaces.http.IHTTPRequest)
@zope.interface.implementer(z3c.dav.coreproperties.IDAVGetetag)
def DAVGetetag(context, request):
    # XXX - this is tested via the z3c.davapp.zopefile package.
    sm = zope.component.getSiteManager(context)
    ob = zope.interface.providedBy(context)

    # get default view, then get z3c.conditionalviews.interfaces.IETag adapter
    name = sm.adapters.lookup(
        (ob, zope.publisher.interfaces.browser.IBrowserRequest),
        zope.publisher.interfaces.IDefaultViewName)
    if name:
        view = sm.adapters.lookup(
            (ob, zope.publisher.interfaces.browser.IBrowserRequest),
            zope.interface.Interface,
            name = name)
        if view:
            etag = zope.component.queryMultiAdapter(
                (context, request, view), z3c.conditionalviews.interfaces.IETag)
            if etag:
                return Getetag(etag.etag)

    # Failed to find either the default name, view or etag data source.
    return None
