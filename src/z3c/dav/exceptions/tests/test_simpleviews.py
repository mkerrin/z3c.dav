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
"""Test the Bad Request view.
"""
__docformat__ = 'restructuredtext'

import unittest

import zope.component
import zope.interface
from zope.formlib.namedtemplate import INamedTemplate

import z3c.dav.interfaces
import z3c.dav.exceptions
import z3c.dav.exceptions.browser

from zope.publisher.browser import TestRequest

class TestExceptionViews(unittest.TestCase):

    def test_unprocessable(self):
        request = TestRequest()
        error = z3c.dav.interfaces.UnprocessableError(None)
        view = z3c.dav.exceptions.UnprocessableError(error, request)

        result = view()

        self.assertEqual(request.response.getStatus(), 422)
        self.assertEqual(result, "")

    def test_precondition(self):
        request = TestRequest()
        error = z3c.dav.interfaces.PreconditionFailed(None)
        view = z3c.dav.exceptions.PreconditionFailed(error, request)

        result = view()

        self.assertEqual(request.response.getStatus(), 412)
        self.assertEqual(result, "")

    def test_badgateway(self):
        request = TestRequest()
        error = z3c.dav.interfaces.BadGateway(None, request)
        view = z3c.dav.exceptions.BadGateway(error, request)

        result = view()

        self.assertEqual(request.response.getStatus(), 502)
        self.assertEqual(result, "")

    def test_conflicterror(self):
        request = TestRequest()
        error = z3c.dav.interfaces.ConflictError(None, request)
        view = z3c.dav.exceptions.HTTPConflictError(error, request)

        result = view()

        self.assertEqual(request.response.getStatus(), 409)
        self.assertEqual(result, "")

    def test_forbiddenerror(self):
        request = TestRequest()
        error = z3c.dav.interfaces.ForbiddenError(None, request)
        view = z3c.dav.exceptions.HTTPForbiddenError(error, request)

        result = view()

        self.assertEqual(request.response.getStatus(), 403)
        self.assertEqual(result, "")

    def test_unsupportedmediatype(self):
        request = TestRequest()
        error = z3c.dav.interfaces.UnsupportedMediaType(None, request)
        view = z3c.dav.exceptions.HTTPUnsupportedMediaTypeError(
            error, request)

        result = view()

        self.assertEqual(request.response.getStatus(), 415)
        self.assertEqual(result, "")

    def test_alreadylocked(self):
        request = TestRequest()
        error = z3c.dav.interfaces.AlreadyLocked(None, "Alread locked")
        view = z3c.dav.exceptions.AlreadyLockedErrorView(error, request)

        result = view()

        self.assertEqual(request.response.getStatus(), 423)
        self.assertEqual(result, "")


class TestDAVErrors(unittest.TestCase):

    def test_conflict_error(self):
        errorview = z3c.dav.exceptions.ConflictError(None, None)

        self.assertEqual(errorview.status, 409)
        self.assertEqual(errorview.errors, [])
        self.assertEqual(errorview.propstatdescription, "")
        self.assertEqual(errorview.responsedescription, "")

    def test_forbidden_error(self):
        errorview = z3c.dav.exceptions.ForbiddenError(None, None)

        self.assertEqual(errorview.status, 403)
        self.assertEqual(errorview.errors, [])
        self.assertEqual(errorview.propstatdescription, "")
        self.assertEqual(errorview.responsedescription, "")

    def test_propertyNotFound_error(self):
        errorview = z3c.dav.exceptions.PropertyNotFoundError(None, None)

        self.assertEqual(errorview.status, 404)
        self.assertEqual(errorview.errors, [])
        self.assertEqual(errorview.propstatdescription, "")
        self.assertEqual(errorview.responsedescription, "")

    def test_failedDependency_error(self):
        errorview = z3c.dav.exceptions.FailedDependencyError(None, None)

        self.assertEqual(errorview.status, 424)
        self.assertEqual(errorview.errors, [])
        self.assertEqual(errorview.propstatdescription, "")
        self.assertEqual(errorview.responsedescription, "")

    def test_alreadlocked_error(self):
        errorview = z3c.dav.exceptions.AlreadyLockedError(None, None)

        self.assertEqual(errorview.status, 423)
        self.assertEqual(errorview.errors, [])
        self.assertEqual(errorview.propstatdescription, "")
        self.assertEqual(errorview.responsedescription, "")

    def test_unauthorized_error(self):
        errorview = z3c.dav.exceptions.UnauthorizedError(None, None)

        self.assertEqual(errorview.status, 401)
        self.assertEqual(errorview.errors, [])
        self.assertEqual(errorview.propstatdescription, "")
        self.assertEqual(errorview.responsedescription, "")


class DummyTemplate(object):

    def __init__(self, context):
        self.context = context

    zope.component.adapts(z3c.dav.exceptions.browser.BadRequest)
    zope.interface.implements(INamedTemplate)

    def __call__(self):
        return "Errr... bad request"


class TestBadRequestView(unittest.TestCase):

    def setUp(self):
        zope.component.getGlobalSiteManager().registerAdapter(
            DummyTemplate, name = "default")

    def tearDown(self):
        zope.component.getGlobalSiteManager().unregisterAdapter(
            DummyTemplate, name = "default")

    def test_badrequestView(self):
        error = z3c.dav.interfaces.BadRequest(
            None, message = u"Bad request data")
        request = TestRequest()
        view = z3c.dav.exceptions.browser.BadRequest(error, request)

        result = view()
        self.assertEqual(request.response.getStatus(), 400)
        self.assertEqual(result, "Errr... bad request")

    def test_badrequestView_message(self):
        error = z3c.dav.interfaces.BadRequest(
            None, message = u"Bad request data")
        request = TestRequest()
        view = z3c.dav.exceptions.browser.BadRequest(error, request)

        self.assertEqual(view.message(), "Bad request data")


def test_suite():
    suite = unittest.TestSuite((
        unittest.makeSuite(TestExceptionViews),
        unittest.makeSuite(TestDAVErrors),
        unittest.makeSuite(TestBadRequestView),
        ))
    return suite
