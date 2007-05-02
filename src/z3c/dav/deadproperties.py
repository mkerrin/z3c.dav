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
"""Support for dead properties.

$Id$
"""
__docformat__ = 'restructuredtext'

from BTrees.OOBTree import OOBTree

from zope import interface
from zope import component
from zope.annotation.interfaces import IAnnotatable, IAnnotations

import z3c.dav.interfaces

_opaque_namespace_key = "z3c.dav.deadproperties.DAVOpaqueProperties"

class OpaqueProperties(object):
    """
      >>> from zope.annotation.attribute import AttributeAnnotations
      >>> from zope.interface.verify import verifyObject
      >>> component.getGlobalSiteManager().registerAdapter(
      ...     AttributeAnnotations, (IAnnotatable,), IAnnotations)

    Initiial the object contains no dead properties.

      >>> class DemoContent(object):
      ...     interface.implements(IAnnotatable)
      >>> resource = DemoContent()
      >>> opaqueProperties = OpaqueProperties(resource)
      >>> verifyObject(z3c.dav.interfaces.IOpaquePropertyStorage,
      ...              opaqueProperties)
      True
      >>> annotations = IAnnotations(resource)
      >>> list(annotations)
      []
      >>> list(opaqueProperties.getAllProperties())
      []

    `hasProperty` returns None since we haven't set any properties yet.

      >>> opaqueProperties.hasProperty('{example:}testprop')
      False
      >>> opaqueProperties.getProperty('{example:}testprop') is None
      True
      >>> annotations = IAnnotations(resource)
      >>> list(annotations)
      []

    Set the testprop property

      >>> opaqueProperties.setProperty('{examplens:}testprop',
      ...   '<E:testprop xmlns:E="examplens:">Test Property Value</E:testprop>')
      >>> annotations = IAnnotations(resource)
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
      >>> annotations = IAnnotations(resource)
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

    Cleanup this test.

      >>> component.getGlobalSiteManager().unregisterAdapter(
      ...     AttributeAnnotations, (IAnnotatable,), IAnnotations)
      True

    """
    interface.implements(z3c.dav.interfaces.IOpaquePropertyStorage)
    component.adapts(IAnnotatable)

    _annotations = None

    def __init__(self, context):
        # __parent__ must be set in order for the security to work
        self.__parent__ = context
        annotations = IAnnotations(context)
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
