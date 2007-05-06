##############################################################################
# Copyright (c) 2003 Zope Corporation and Contributors.
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

$Id$
"""
__docformat__ = 'restructuredtext'

from zope import component
from zope import interface
import zope.publisher.interfaces.http
from zope.dublincore.interfaces import IDCTimes, IDCDescriptiveProperties
from zope.annotation.interfaces import IAnnotatable
import zope.app.file.interfaces

import z3c.dav.coreproperties


class DAVDublinCore(object):
    """
    Common data model that uses zope.dublincore package to handle the
    `{DAV:}creationdate`, `{DAV:}displayname` or title, and the
    `{DAV:}getlastmodified` WebDAV properties.

      >>> from zope.app.file.file import File
      >>> file = File('some data for a file', 'text/plain')
      >>> adapter = DAVDublinCore(file, None)
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

      >>> from zope.dublincore.annotatableadapter import ZDCAnnotatableAdapter
      >>> from zope.dublincore.interfaces import IWriteZopeDublinCore
      >>> from zope.annotation.attribute import AttributeAnnotations
      >>> from zope.annotation.interfaces import IAnnotations
      >>> from zope.annotation.interfaces import IAttributeAnnotatable
      >>> import datetime
      >>> from zope.datetime import tzinfo

      >>> interface.classImplements(File, IAttributeAnnotatable)
      >>> component.getGlobalSiteManager().registerAdapter(
      ...     AttributeAnnotations)
      >>> component.getGlobalSiteManager().registerAdapter(
      ...     ZDCAnnotatableAdapter, provided = IWriteZopeDublinCore)

      >>> file = File('some data for a file', 'text/plain')
      >>> IWriteZopeDublinCore(file).created = now = datetime.datetime(
      ...     2006, 5, 24, 0, 0, 58, tzinfo = tzinfo(60))
      >>> IWriteZopeDublinCore(file).title = u'Example Test File'
      >>> IWriteZopeDublinCore(file).modified = now = datetime.datetime(
      ...     2006, 5, 24, 0, 0, 58, tzinfo = tzinfo(60))

      >>> adapter = DAVDublinCore(file, None)
      >>> adapter.creationdate == now
      True
      >>> adapter.displayname
      u'Example Test File'
      >>> adapter.getlastmodified == now
      True
      >>> adapter.displayname = u'Changed Test File Title'
      >>> IWriteZopeDublinCore(file).title
      u'Changed Test File Title'

      >>> component.getGlobalSiteManager().unregisterAdapter(
      ...     AttributeAnnotations, provided = IAnnotations)
      True
      >>> component.getGlobalSiteManager().unregisterAdapter(
      ...     ZDCAnnotatableAdapter, provided = IWriteZopeDublinCore)
      True

    """
    interface.implements(z3c.dav.coreproperties.IDAVCoreSchema)
    component.adapts(IAnnotatable,
                     zope.publisher.interfaces.http.IHTTPRequest)

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


class DAVFileGetSchema(object):
    """
      >>> from zope.app.file.file import File
      >>> from zope.interface.verify import verifyObject
      >>> file = File('some data for the file', 'text/plain')
      >>> adapter = DAVFileGetSchema(file, None)
      >>> verifyObject(z3c.dav.coreproperties.IDAVGetSchema, adapter)
      True
      >>> adapter.getcontentlanguage is None
      True
      >>> adapter.getcontentlength
      22
      >>> adapter.getcontenttype
      'text/plain'

      >>> from zope.dublincore.annotatableadapter import ZDCAnnotatableAdapter
      >>> from zope.dublincore.interfaces import IWriteZopeDublinCore
      >>> from zope.annotation.attribute import AttributeAnnotations
      >>> from zope.annotation.interfaces import IAnnotations
      >>> from zope.annotation.interfaces import IAttributeAnnotatable
      >>> from zope.datetime import tzinfo
      >>> import datetime
      >>> interface.classImplements(File, IAttributeAnnotatable)
      >>> component.getGlobalSiteManager().registerAdapter(
      ...     AttributeAnnotations)
      >>> component.getGlobalSiteManager().registerAdapter(
      ...     ZDCAnnotatableAdapter, provided = IWriteZopeDublinCore)

      >>> file = File('some data for the file', 'text/plain')
      >>> adapter = DAVFileGetSchema(file, None)

      >>> adapter.getcontentlanguage is None
      True
      >>> adapter.getcontentlength
      22
      >>> adapter.getcontenttype
      'text/plain'
      >>> adapter.getetag is None # etag is None for now.
      True

      >>> component.getGlobalSiteManager().unregisterAdapter(
      ...     AttributeAnnotations, provided = IAnnotations)
      True
      >>> component.getGlobalSiteManager().unregisterAdapter(
      ...     ZDCAnnotatableAdapter, provided = IWriteZopeDublinCore)
      True

    """
    interface.implements(z3c.dav.coreproperties.IDAVGetSchema)
    component.adapts(zope.app.file.interfaces.IFile,
                     zope.publisher.interfaces.http.IHTTPRequest)

    def __init__(self, context, request):
        self.context = context

    @property
    def getcontentlanguage(self):
        return None

    @property
    def getetag(self):
        return None

    @property
    def getcontentlength(self):
        return self.context.getSize()

    @property
    def getcontenttype(self):
        return self.context.contentType
