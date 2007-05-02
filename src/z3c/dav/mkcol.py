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
"""DAV method MKCOL

$Id$
"""
__docformat__ = 'restructuredtext'

from zope import interface
from zope import component
from zope.filerepresentation.interfaces import IWriteDirectory
from zope.filerepresentation.interfaces import IDirectoryFactory
import zope.event
from zope.lifecycleevent import ObjectCreatedEvent
import zope.app.http.interfaces

import z3c.dav.interfaces

class MKCOL(object):
    """
    MKCOL handler for creating collections. This is only supported on
    unmapped urls.

      >>> from cStringIO import StringIO
      >>> from zope import component
      >>> from zope.publisher.browser import TestRequest
      >>> from zope.app.http.put import NullResource
      >>> from zope.app.folder.folder import Folder
      >>> from zope.app.folder.interfaces import IFolder

      >>> events = []
      >>> def eventLog(event):
      ...    events.append(event)
      >>> zope.event.subscribers.append(eventLog)

      >>> container = Folder()
      >>> context = NullResource(container, 'newdir')

    A MKCOL request message may contain a message body. But the specification
    says that if the server receives a entity type that it doesn't understand
    then it MOST respond with a 415 (Unsupported Media Type). This
    implementation of MKCOL doesn't understand any message body received
    with a MKCOL request and thus raise a UnsupportedMediaType exception.

      >>> mkcol = MKCOL(context, TestRequest(StringIO('some request body')))
      >>> mkcol.MKCOL() #doctest:+ELLIPSIS
      Traceback (most recent call last):
      ...
      UnsupportedMediaType: <zope.app.http.put.NullResource object at ...>, u'A request body is not supported for a MKCOL method'
      >>> events
      []

      >>> request = TestRequest(environ = {'CONTENT_LENGTH': 0})

    If no adapter implementing IWriteDirectory is registered for then we
    will never be able to create a new collection and hence this operation
    is forbidden.

      >>> MKCOL(context, request).MKCOL()
      Traceback (most recent call last):
      ...
      ForbiddenError
      >>> 'newdir' in container
      False
      >>> events
      []

    Now we will define and register a IWriteDirectory adapter. But we
    can't adapt the container to IDirectoryFactory (which creates the
    new collection object) so again this operation is forbidden.

      >>> class WriteDirectory(object):
      ...    interface.implements(IWriteDirectory)
      ...    component.adapts(IFolder)
      ...    def __init__(self, context):
      ...        self.context = context
      ...    def __setitem__(self, name, object):
      ...        self.context[name] = object
      ...    def __delitem__(slef, name):
      ...        del self.context[name]
      >>> component.getGlobalSiteManager().registerAdapter(WriteDirectory)

      >>> events = []

      >>> MKCOL(context, request).MKCOL()
      Traceback (most recent call last):
      ...
      ForbiddenError
      >>> 'newdir' in container
      False
      >>> events
      []

    By defining and registering a directory factory we can create a new
    collection.

      >>> class DirectoryFactory(object):
      ...    interface.implements(IDirectoryFactory)
      ...    component.adapts(IFolder)
      ...    def __init__(self, context):
      ...        pass
      ...    def __call__(self, name):
      ...        return Folder()
      >>> component.getGlobalSiteManager().registerAdapter(DirectoryFactory)
      >>> events = []

    The next call to the mkcol implementation will succeed and create
    a new folder with the name 'newdir'.
      
      >>> MKCOL(context, request).MKCOL()
      ''
      >>> request.response.getStatus()
      201
      >>> 'newdir' in container
      True
      >>> container['newdir'] #doctest:+ELLIPSIS
      <zope.app.folder.folder.Folder object at ...>

    Verify that the correct events are generated during the creation of the
    new folder.

      >>> events[0] #doctest:+ELLIPSIS
      <zope.app.event.objectevent.ObjectCreatedEvent object at ...>
      >>> events[1] #doctest:+ELLIPSIS
      <zope.app.container.contained.ObjectAddedEvent object at ...>
      >>> events[2] #doctest:+ELLIPSIS
      <zope.app.container.contained.ContainerModifiedEvent object at ...>
      >>> events[3:]
      []

    Cleanup.

      >>> component.getGlobalSiteManager().unregisterAdapter(WriteDirectory)
      True
      >>> component.getGlobalSiteManager().unregisterAdapter(DirectoryFactory)
      True

      >>> zope.event.subscribers.remove(eventLog)

    """
    interface.implements(z3c.dav.interfaces.IWebDAVMethod)
    component.adapts(zope.app.http.interfaces.INullResource,
                     z3c.dav.interfaces.IWebDAVRequest)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def MKCOL(self):
        if self.request.getHeader("content-length") > 0:
            # We don't (yet) support a request body on MKCOL.
            raise z3c.dav.interfaces.UnsupportedMediaType(
                self.context,
                message = u"A request body is not supported for a MKCOL method")

        container = self.context.container
        name = self.context.name

        dir = IWriteDirectory(container, None)
        dir_factory = IDirectoryFactory(container, None)
        if dir is None or dir_factory is None:
            raise z3c.dav.interfaces.ForbiddenError(
                self.context, message = u"")
        
        newdir = dir_factory(name)
        zope.event.notify(ObjectCreatedEvent(newdir))
        dir[name] = newdir

        self.request.response.setStatus(201)
        return ""
