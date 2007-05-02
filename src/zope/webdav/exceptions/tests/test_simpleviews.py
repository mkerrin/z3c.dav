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
"""Test the Bad Request view.

$Id$
"""
__docformat__ = 'restructuredtext'

import unittest
from cStringIO import StringIO
from zope.app.testing.placelesssetup import PlacelessSetup
from zope import component
from zope import interface
from zope.formlib.namedtemplate import INamedTemplate

import zope.webdav.interfaces
import zope.webdav.exceptions
import zope.webdav.exceptions.browser
from zope.webdav.publisher import WebDAVRequest
from test_multiviews import TestRequest

class TestExceptionViews(PlacelessSetup, unittest.TestCase):

    def test_unprocessable(self):
        request = WebDAVRequest(StringIO(""), {})
        error = zope.webdav.interfaces.UnprocessableError(None)
        view = zope.webdav.exceptions.UnprocessableError(error, request)

        result = view()

        self.assertEqual(request.response.getStatus(), 422)
        self.assertEqual(result, "")

    def test_precondition(self):
        request = WebDAVRequest(StringIO(""), {})
        error = zope.webdav.interfaces.PreconditionFailed(None)
        view = zope.webdav.exceptions.PreconditionFailed(error, request)

        result = view()

        self.assertEqual(request.response.getStatus(), 412)
        self.assertEqual(result, "")

    def test_badgateway(self):
        request = WebDAVRequest(StringIO(""), {})
        error = zope.webdav.interfaces.BadGateway(None, request)
        view = zope.webdav.exceptions.BadGateway(error, request)

        result = view()

        self.assertEqual(request.response.getStatus(), 502)
        self.assertEqual(result, "")

    def test_conflicterror(self):
        request = WebDAVRequest(StringIO(""), {})
        error = zope.webdav.interfaces.ConflictError(None, request)
        view = zope.webdav.exceptions.HTTPConflictError(error, request)

        result = view()

        self.assertEqual(request.response.getStatus(), 409)
        self.assertEqual(result, "")

    def test_forbiddenerror(self):
        request = WebDAVRequest(StringIO(""), {})
        error = zope.webdav.interfaces.ForbiddenError(None, request)
        view = zope.webdav.exceptions.HTTPForbiddenError(error, request)

        result = view()

        self.assertEqual(request.response.getStatus(), 403)
        self.assertEqual(result, "")

    def test_unsupportedmediatype(self):
        request = WebDAVRequest(StringIO(""), {})
        error = zope.webdav.interfaces.UnsupportedMediaType(None, request)
        view = zope.webdav.exceptions.HTTPUnsupportedMediaTypeError(
            error, request)

        result = view()

        self.assertEqual(request.response.getStatus(), 415)
        self.assertEqual(result, "")


class TestDAVErrors(unittest.TestCase):

    def test_conflict_error(self):
        errorview = zope.webdav.exceptions.ConflictError(None, None)

        self.assertEqual(errorview.status, 409)
        self.assertEqual(errorview.errors, [])
        self.assertEqual(errorview.propstatdescription, "")
        self.assertEqual(errorview.responsedescription, "")

    def test_forbidden_error(self):
        errorview = zope.webdav.exceptions.ForbiddenError(None, None)

        self.assertEqual(errorview.status, 403)
        self.assertEqual(errorview.errors, [])
        self.assertEqual(errorview.propstatdescription, "")
        self.assertEqual(errorview.responsedescription, "")

    def test_propertyNotFound_error(self):
        errorview = zope.webdav.exceptions.PropertyNotFoundError(None, None)

        self.assertEqual(errorview.status, 404)
        self.assertEqual(errorview.errors, [])
        self.assertEqual(errorview.propstatdescription, "")
        self.assertEqual(errorview.responsedescription, "")

    def test_failedDependency_error(self):
        errorview = zope.webdav.exceptions.FailedDependencyError(None, None)

        self.assertEqual(errorview.status, 424)
        self.assertEqual(errorview.errors, [])
        self.assertEqual(errorview.propstatdescription, "")
        self.assertEqual(errorview.responsedescription, "")

    def test_alreadlocked_error(self):
        errorview = zope.webdav.exceptions.AlreadyLockedError(None, None)

        self.assertEqual(errorview.status, 423)
        self.assertEqual(errorview.errors, [])
        self.assertEqual(errorview.propstatdescription, "")
        self.assertEqual(errorview.responsedescription, "")

    def test_unauthorized_error(self):
        errorview = zope.webdav.exceptions.UnauthorizedError(None, None)

        self.assertEqual(errorview.status, 401)
        self.assertEqual(errorview.errors, [])
        self.assertEqual(errorview.propstatdescription, "")
        self.assertEqual(errorview.responsedescription, "")


class DummyTemplate(object):

    def __init__(self, context):
        self.context = context

    component.adapts(zope.webdav.exceptions.browser.BadRequest)
    interface.implements(INamedTemplate)

    def __call__(self):
        return "Errr... bad request"


class TestBadRequestView(unittest.TestCase):

    def setUp(self):
        component.getGlobalSiteManager().registerAdapter(
            DummyTemplate, name = "default")

    def tearDown(self):
        component.getGlobalSiteManager().unregisterAdapter(
            DummyTemplate, name = "default")

    def test_badrequestView(self):
        error = zope.webdav.interfaces.BadRequest(
            None, message = u"Bad request data")
        request = TestRequest()
        view = zope.webdav.exceptions.browser.BadRequest(error, request)

        result = view()
        self.assertEqual(request.response.getStatus(), 400)
        self.assertEqual(result, "Errr... bad request")

    def test_badrequestView_message(self):
        error = zope.webdav.interfaces.BadRequest(
            None, message = u"Bad request data")
        request = TestRequest()
        view = zope.webdav.exceptions.browser.BadRequest(error, request)

        self.assertEqual(view.message(), "Bad request data")


def test_suite():
    suite = unittest.TestSuite((
        unittest.makeSuite(TestExceptionViews),
        unittest.makeSuite(TestDAVErrors),
        unittest.makeSuite(TestBadRequestView),
        ))
    return suite
