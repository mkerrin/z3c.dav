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
"""Test WebDAV COPY and MOVE methods.

$Id$
"""

import unittest
import UserDict
from cStringIO import StringIO

from zope import interface
from zope import component
from zope import schema
from zope.copypastemove.interfaces import IObjectCopier, IObjectMover
from zope.location.traversing import LocationPhysicallyLocatable
from zope.traversing.adapters import Traverser, DefaultTraversable
from zope.traversing.browser.interfaces import IAbsoluteURL
from zope.app.publication.http import MethodNotAllowed
from zope.app.container.interfaces import IReadContainer
from zope.traversing.interfaces import IContainmentRoot

import z3c.dav.publisher
from z3c.dav.copymove import Base, COPY, MOVE

class IResource(interface.Interface):

    text = schema.TextLine(
        title = u"Example Text Property")

    intprop = schema.Int(
        title = u"Example Int Property")


class Resource(object):
    interface.implements(IResource)

    def __init__(self, text = u"", intprop = 0):
        self.text = text
        self.intprop = intprop


class ICollectionResource(IReadContainer):

    title = schema.TextLine(
        title = u"Title",
        description = u"Title of resource")


class CollectionResource(UserDict.UserDict):
    interface.implements(ICollectionResource)

    title = None

    def __setitem__(self, key, val):
        val.__parent__ = self
        val.__name__ = key

        self.data[key] = val

class RootCollectionResource(CollectionResource):
    interface.implements(IContainmentRoot)

class TestRequest(z3c.dav.publisher.WebDAVRequest):

    def __init__(self, environ = {}):
        env = environ.copy()
        env.setdefault("HTTP_HOST", "localhost")
        super(TestRequest, self).__init__(StringIO(""), env)

        self.processInputs()


def baseSetUp():
    gsm = component.getGlobalSiteManager()
    gsm.registerAdapter(LocationPhysicallyLocatable,
                        (IResource,))
    gsm.registerAdapter(LocationPhysicallyLocatable,
                        (ICollectionResource,))
    gsm.registerAdapter(Traverser, (IResource,))
    gsm.registerAdapter(Traverser, (ICollectionResource,))
    gsm.registerAdapter(DefaultTraversable, (IResource,))
    gsm.registerAdapter(DefaultTraversable,
                        (ICollectionResource,))


def baseTearDown():
    gsm = component.getGlobalSiteManager()
    gsm.unregisterAdapter(LocationPhysicallyLocatable,
                          (IResource,))
    gsm.unregisterAdapter(LocationPhysicallyLocatable,
                          (ICollectionResource,))
    gsm.unregisterAdapter(Traverser, (IResource,))
    gsm.unregisterAdapter(Traverser, (ICollectionResource,))
    gsm.unregisterAdapter(DefaultTraversable, (IResource,))
    gsm.unregisterAdapter(DefaultTraversable,
                          (ICollectionResource,))


class COPYMOVEParseHeadersTestCase(unittest.TestCase):

    def setUp(self):
        self.root = RootCollectionResource()

        baseSetUp()

    def tearDown(self):
        del self.root

        baseTearDown()

    def test_no_overwrite(self):
        request = TestRequest()
        copy = COPY(None, request)

        self.assertEqual(copy.getOverwrite(), True)

    def test_T_overwrite(self):
        request = TestRequest(environ = {"OVERWRITE": "t"})
        copy = COPY(None, request)

        self.assertEqual(copy.getOverwrite(), True)

    def test_t_overwrite(self):
        request = TestRequest(environ = {"OVERWRITE": "T"})
        copy = COPY(None, request)

        self.assertEqual(copy.getOverwrite(), True)

    def test_F_overwrite(self):
        request = TestRequest(environ = {"OVERWRITE": "F"})
        copy = COPY(None, request)

        self.assertEqual(copy.getOverwrite(), False)

    def test_f_overwrite(self):
        request = TestRequest(environ = {"OVERWRITE": "f"})
        copy = COPY(None, request)

        self.assertEqual(copy.getOverwrite(), False)

    def test_bad_overwrite(self):
        request = TestRequest(environ = {"OVERWRITE": "x"})
        copy = COPY(None, request)

        self.assertRaises(z3c.dav.interfaces.BadRequest, copy.getOverwrite)

    def test_default_destination_path(self):
        request = TestRequest()
        copy = COPY(None, request)

        self.assertRaises(
            z3c.dav.interfaces.BadRequest, copy.getDestinationPath)

    def test_destination_path(self):
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/testpath"})
        copy = COPY(None, request)

        self.assertEqual(copy.getDestinationPath(), "/testpath")

    def test_destination_path_slash(self):
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/testpath/"})
        copy = COPY(None, request)

        self.assertEqual(copy.getDestinationPath(), "/testpath")

    def test_getDestinationPath_wrong_server(self):
        request = TestRequest(
            environ = {"DESTINATION": "http://www.server.com/testpath"})
        copy = COPY(None, request)

        self.assertRaises(z3c.dav.interfaces.BadGateway,
                          copy.getDestinationPath)

    def test_getDestinationPath_with_username(self):
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://michael@localhost/testpath"})
        copy = COPY(resource, request)
        destname, destob, parent = copy.getDestinationNameAndParentObject()
        self.assertEqual(destname, "testpath")
        self.assertEqual(destob, None)
        self.assertEqual(parent, self.root)

    def test_getDestinationPath_with_username_and_password(self):
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://michael:pw@localhost/testpath"})
        copy = COPY(resource, request)
        destname, destob, parent = copy.getDestinationNameAndParentObject()
        self.assertEqual(destname, "testpath")
        self.assertEqual(destob, None)
        self.assertEqual(parent, self.root)

    def test_getDestinationPath_with_port(self):
        # this is correct since localhost:10080 is a different server to
        # localhost.
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost:10080/testpath"})
        copy = COPY(resource, request)
        self.assertRaises(z3c.dav.interfaces.BadGateway,
                          copy.getDestinationNameAndParentObject)

    def test_getDestinationPath_with_space(self):
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/test path"})

        copy = Base(resource, request)
        destname, destob, parent = copy.getDestinationNameAndParentObject()
        self.assertEqual(destname, "test path")
        self.assertEqual(destob, None)
        self.assertEqual(parent, self.root)

    def test_getDestinationPath_with_quotedspace(self):
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/test%20path"})

        copy = Base(resource, request)
        destname, destob, parent = copy.getDestinationNameAndParentObject()
        self.assertEqual(destname, "test path")
        self.assertEqual(destob, None)
        self.assertEqual(parent, self.root)

    def test_getDestinationNameAndParentObject(self):
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/testpath"})

        copy = COPY(resource, request)
        destname, destob, parent = copy.getDestinationNameAndParentObject()
        self.assertEqual(destname, "testpath")
        self.assertEqual(destob, None)
        self.assertEqual(parent, self.root)

    def test_getDestinationNameAndParentObject_destob_overwrite(self):
        destresource = self.root["destresource"] = Resource()
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/destresource",
                       "OVERWRITE": "T"})

        copy = COPY(resource, request)
        destname, destob, parent = copy.getDestinationNameAndParentObject()
        self.assertEqual(destname, "destresource")
        self.assertEqual(destob, destresource)
        self.assert_("destresource" not in self.root)
        self.assertEqual(parent, self.root)

    def test_getDestinationNameAndParentObject_destob_overwrite_failed(self):
        destresource = self.root["destresource"] = Resource()
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/destresource",
                       "OVERWRITE": "F"})

        copy = COPY(resource, request)
        self.assertRaises(z3c.dav.interfaces.PreconditionFailed,
                          copy.getDestinationNameAndParentObject)
        self.assert_("destresource" in self.root)

    def test_getDestinationNameAndParentObject_noparent(self):
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/noparent/testpath"})

        copy = COPY(resource, request)
        self.assertRaises(z3c.dav.interfaces.ConflictError,
                          copy.getDestinationNameAndParentObject)

    def test_getDestinationNameAndParentObject_destob_sameob(self):
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/resource",
                       "OVERWRITE": "T"})

        copy = COPY(resource, request)
        self.assertRaises(z3c.dav.interfaces.ForbiddenError,
                          copy.getDestinationNameAndParentObject)

    def test_nocopier(self):
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/copy_of_resource"})

        copy = COPY(resource, request)
        self.assertRaises(MethodNotAllowed, copy.COPY)

    def test_nomovier(self):
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/copy_of_resource"})

        copy = MOVE(resource, request)
        self.assertRaises(MethodNotAllowed, copy.MOVE)


class DummyResourceURL(object):
    interface.implements(IAbsoluteURL)

    def __init__(self, context, request):
        self.context = context

    def __str__(self):
        if getattr(self.context, "__parent__", None) is not None:
            path = DummyResourceURL(self.context.__parent__, None)()
        elif IContainmentRoot.providedBy(self.context):
            return ""
        else:
            path = ""

        if getattr(self.context, "__name__", None) is not None:
            path += "/" + self.context.__name__
        elif IResource.providedBy(self.context):
            path += "/resource"
        elif ICollectionResource.providedBy(self.context):
            path += "/collection"
        else:
            raise ValueError("unknown context type")

        return path

    __call__ = __str__


class Copier(object):
    interface.implements(IObjectCopier)

    iscopyable = True
    canCopyableTo = True

    def __init__(self, context):
        self.context = context

    def copyable(self):
        return self.iscopyable

    def copyTo(self, target, new_name):
        target[new_name] = self.context

        return new_name

    def copyableTo(self, parent, destname):
        return self.canCopyableTo


class COPYObjectTestCase(unittest.TestCase):

    def setUp(self):
        self.root = RootCollectionResource()

        baseSetUp()

        Copier.iscopyable = True
        Copier.canCopyableTo = True
        gsm = component.getGlobalSiteManager()
        gsm.registerAdapter(Copier, (IResource,))
        gsm.registerAdapter(DummyResourceURL,
                            (IResource,
                             z3c.dav.interfaces.IWebDAVRequest))

    def tearDown(self):
        del self.root

        baseTearDown()

        gsm = component.getGlobalSiteManager()
        gsm.unregisterAdapter(Copier, (IResource,))
        gsm.unregisterAdapter(DummyResourceURL,
                              (IResource,
                               z3c.dav.interfaces.IWebDAVRequest))

    def test_copy(self):
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/copy_of_resource"})

        copy = COPY(resource, request)
        result = copy.COPY()

        self.assertEqual(request.response.getStatus(), 201)
        self.assertEqual(request.response.getHeader("Location"),
                         "/copy_of_resource")
        self.assertEqual(result, "")
        self.assertEqual(self.root["copy_of_resource"] is resource, True)
        self.assertEqual(self.root["resource"] is resource, True)

    def test_copy_overwrite(self):
        resource = self.root["resource"] = Resource()
        resource2 = self.root["resource2"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/resource2",
                       "OVERWRITE": "T"})

        copy = COPY(resource, request)
        result = copy.COPY()

        self.assertEqual(request.response.getStatus(), 204)
        self.assertEqual(result, "")
        self.assertEqual(self.root["resource"] is resource, True)
        self.assertEqual(self.root["resource2"] is resource, True)

    def test_copy_not_copyable(self):
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/copy_of_resource"})

        Copier.iscopyable = False

        copy = COPY(resource, request)
        self.assertRaises(MethodNotAllowed, copy.COPY)

    def test_copy_not_copyableto(self):
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/copy_of_resource"})

        Copier.canCopyableTo = False

        copy = COPY(resource, request)
        self.assertRaises(z3c.dav.interfaces.ConflictError, copy.COPY)


class Movier(object):
    interface.implements(IObjectMover)

    isMoveable = True
    isMoveableTo = True

    def __init__(self, context):
        self.context = context

    def moveTo(self, target, new_name):
        del self.context.__parent__[self.context.__name__]
        target[new_name] = self.context

        return new_name

    def moveable(self):
        return self.isMoveable

    def moveableTo(self, target, name = None):
        return self.isMoveableTo


class MOVEObjectTestCase(unittest.TestCase):

    def setUp(self):
        self.root = RootCollectionResource()

        baseSetUp()

        Movier.isMoveable = True
        Movier.isMoveableTo = True
        gsm = component.getGlobalSiteManager()
        gsm.registerAdapter(Movier, (IResource,))
        gsm.registerAdapter(DummyResourceURL,
                            (IResource,
                             z3c.dav.interfaces.IWebDAVRequest))

    def tearDown(self):
        del self.root

        baseTearDown()

        gsm = component.getGlobalSiteManager()
        gsm.unregisterAdapter(Movier, (IResource,))
        gsm.unregisterAdapter(DummyResourceURL,
                              (IResource,
                               z3c.dav.interfaces.IWebDAVRequest))

    def test_move(self):
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/copy_of_resource"})

        move = MOVE(resource, request)
        result = move.MOVE()

        self.assertEqual(request.response.getStatus(), 201)
        self.assertEqual(request.response.getHeader("Location"),
                         "/copy_of_resource")
        self.assertEqual("resource" not in self.root, True)
        self.assertEqual(self.root["copy_of_resource"], resource)

    def test_move_overwrite(self):
        resource = self.root["resource"] = Resource()
        resource2 = self.root["resource2"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/resource2",
                       "OVERWRITE": "T"})

        move = MOVE(resource, request)
        result = move.MOVE()

        self.assertEqual(request.response.getStatus(), 204)
        self.assertEqual("resource" not in self.root, True)
        self.assertEqual(self.root["resource2"] is resource, True)

    def test_move_not_moveable(self):
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/copy_of_resource"})

        Movier.isMoveable = False

        move = MOVE(resource, request)
        self.assertRaises(MethodNotAllowed, move.MOVE)

    def test_move_not_moveableTo(self):
        resource = self.root["resource"] = Resource()
        request = TestRequest(
            environ = {"DESTINATION": "http://localhost/copy_of_resource"})

        Movier.isMoveableTo = False

        move = MOVE(resource, request)
        self.assertRaises(z3c.dav.interfaces.ConflictError, move.MOVE)


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(COPYMOVEParseHeadersTestCase),
        unittest.makeSuite(COPYObjectTestCase),
        unittest.makeSuite(MOVEObjectTestCase),
        ))
