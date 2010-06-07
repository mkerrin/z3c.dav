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

$Id$
"""
__docformat__ = 'restructuredtext'

import unittest
from cStringIO import StringIO

from z3c.dav.ftests import dav
import z3c.dav.interfaces
import z3c.dav.exceptions.browser

class TestBadRequest(dav.DAVTestCase):

    def test_badrequest(self):
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        error = z3c.dav.interfaces.BadRequest(
            request, u"Some bad content in the request")

        view = z3c.dav.exceptions.browser.BadRequest(error, request)
        result = view()

        self.assertEqual(request.response.getStatus(), 400)
        self.assertEqual(
            request.response.getHeader("content-type"), "text/html")
        self.assert_("Some bad content in the request" in result)


def test_suite():
    suite = unittest.TestSuite((
        unittest.makeSuite(TestBadRequest)))
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest = "test_suite")
