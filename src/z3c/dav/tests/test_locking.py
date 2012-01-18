import doctest
import unittest
import UserDict

import zope.interface
import zope.publisher.interfaces
from zope.publisher.browser import TestRequest
import zope.location.interfaces
import zope.security.proxy
from zope.security.management import newInteraction, endInteraction, \
     queryInteraction
from zope.security.testing import Principal
import z3c.conditionalviews.interfaces

import z3c.dav.ifvalidator

import test_doctests

class Demo(object):
    zope.interface.implements(zope.publisher.interfaces.IPublishTraverse)

    def __init__(self, name):
        self.__name__ = name
        self.__parent__ = None
        self.children = {}

    def add(self, value):
        self.children[value.__name__] = value
        value.__parent__ = self

    def publishTraverse(self, request, name):
        child = self.children.get(name, None)
        if child:
            return child
        raise zope.publisher.interfaces.NotFound(self, name, request)


class ReqAnnotation(UserDict.IterableUserDict):
    zope.interface.implements(zope.annotation.interfaces.IAnnotations)

    def __init__(self, request):
        self.data = request._environ.setdefault('annotation', {})


class ETag(object):
    zope.interface.implements(z3c.conditionalviews.interfaces.IETag)

    def __init__(self, context, request, view):
        pass

    etag = None

    weak = False


class Statetokens(object):
    zope.interface.implements(z3c.dav.ifvalidator.IStateTokens)

    def __init__(self, context, request, view):
        self.context = context

    schemes = ('ns',)

    @property
    def tokens(self):
        context = zope.security.proxy.removeSecurityProxy(self.context) # ???
        if getattr(context, '_tokens', None) is not None:
            return context._tokens
        return []


class PhysicallyLocatable(object):
    zope.interface.implements(zope.location.interfaces.ILocationInfo)

    def __init__(self, context):
        self.context = context

    def getRoot(self):
        return self.context.__parent__

    def getPath(self):
        return '/' + self.context.__name__


def setUp(test):
    test.globs["Demo"] = Demo
    test.globs["DemoFolder"] = test_doctests.DemoFolder
    test.globs["ETag"] = ETag
    test.globs["ReqAnnotation"] = ReqAnnotation

    # create principal
    participation = TestRequest(environ = {"REQUEST_METHOD": "PUT"})
    participation.setPrincipal(Principal("michael"))
    if queryInteraction() is not None:
        queryInteraction().add(participation)
    else:
        newInteraction(participation)


    gsm = zope.component.getGlobalSiteManager()

    gsm.registerAdapter(
        ReqAnnotation, (zope.publisher.interfaces.http.IHTTPRequest,))
    gsm.registerAdapter(Statetokens, (None, TestRequest, None))
    gsm.registerAdapter(ETag, (None, TestRequest, None))
    gsm.registerAdapter(PhysicallyLocatable, (Demo,))
    gsm.registerAdapter(PhysicallyLocatable, (test_doctests.DemoFolder,))


def tearDown(test):
    del test.globs["Demo"]
    del test.globs["DemoFolder"]
    del test.globs["ETag"]
    del test.globs["ReqAnnotation"]

    gsm = zope.component.getGlobalSiteManager()

    gsm.unregisterAdapter(
        ReqAnnotation, (zope.publisher.interfaces.http.IHTTPRequest,))
    gsm.unregisterAdapter(Statetokens, (None, TestRequest, None))
    gsm.unregisterAdapter(ETag, (None, TestRequest, None))
    gsm.unregisterAdapter(PhysicallyLocatable, (Demo,))
    gsm.unregisterAdapter(PhysicallyLocatable, (test_doctests.DemoFolder,))


def test_suite():
    return unittest.TestSuite((
        doctest.DocTestSuite(
            "z3c.dav.ifvalidator",
            setUp = setUp,
            tearDown = tearDown,
            )
        ))
