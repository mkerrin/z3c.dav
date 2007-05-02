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
"""Collection of functional tests for the LOCK method.

$Id$
"""
__docformat__ = 'restructuredtext'

import unittest
import dav

class COPYTestCase(dav.DAVTestCase):

    def test_copy_file(self):
        file = self.addResource("/sourcefile", "some file content",
                                contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "COPY",
                   "DESTINATION": "http://localhost/destfile"})

        self.assertEqual(response.getStatus(), 201)
        self.assertEqual(response.getHeader("location"),
                         "http://localhost/destfile")

        self.assertEqual(self.getRootFolder()["destfile"].data,
                         "some file content")
        self.assertEqual(self.getRootFolder()["sourcefile"].data,
                         "some file content")

    def test_copy_file_nodest(self):
        file = self.addResource("/sourcefile", "some file content",
                                contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "COPY"}, handle_errors = True)

        self.assertEqual(response.getStatus(), 400)

    def test_copy_file_default_overwrite(self):
        file = self.addResource("/sourcefile", "some source file",
                                contentType = "text/plain")
        destfile = self.addResource("/destfile", "some dest file",
                                    contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "COPY",
                   "DESTINATION": "http://localhost/destfile"})

        self.assertEqual(response.getStatus(), 204)
        self.assertEqual(self.getRootFolder()["destfile"].data,
                         "some source file")
        self.assertEqual(self.getRootFolder()["sourcefile"].data,
                         "some source file")

    def test_copy_file_true_overwrite(self):
        file = self.addResource("/sourcefile", "some source file",
                                contentType = "text/plain")
        destfile = self.addResource("/destfile", "some dest file",
                                    contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "COPY",
                   "DESTINATION": "http://localhost/destfile",
                   "OVERWRITE": "T"})

        self.assertEqual(response.getStatus(), 204)
        self.assertEqual(self.getRootFolder()["destfile"].data,
                         "some source file")
        self.assertEqual(self.getRootFolder()["sourcefile"].data,
                         "some source file")

    def test_copy_file_false_overwrite(self):
        file = self.addResource("/sourcefile", "some source file",
                                contentType = "text/plain")
        destfile = self.addResource("/destfile", "some dest file",
                                    contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "COPY",
                   "DESTINATION": "http://localhost/destfile",
                   "OVERWRITE": "F"},
            handle_errors = True)

        self.assertEqual(response.getStatus(), 412)
        self.assertEqual(self.getRootFolder()["destfile"].data,
                         "some dest file")
        self.assertEqual(self.getRootFolder()["sourcefile"].data,
                         "some source file")

    def test_copy_file_to_remove(self):
        file = self.addResource("/sourcefile", "some source file",
                                contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "COPY",
                   "DESTINATION": "http://www.remove-server.com/destfile",
                   "OVERWRITE": "T"},
            handle_errors = True)

        self.assertEqual(response.getStatus(), 502)

    def test_copy_file_no_destparent(self):
        file = self.addResource("/sourcefile", "some source file",
                                contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "COPY",
                   "DESTINATION": "http://localhost/bla/destfile",
                   "OVERWRITE": "T"},
            handle_errors = True)

        self.assertEqual(response.getStatus(), 409)
        self.assertEqual(list(self.getRootFolder().keys()), [u"sourcefile"])

    def test_copy_to_same_file(self):
        file = self.addResource("/sourcefile", "some source file",
                                contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "COPY",
                   "DESTINATION": "http://localhost/sourcefile",
                   "OVERWRITE": "T"},
            handle_errors = True)

        self.assertEqual(response.getStatus(), 403)
        self.assertEqual(self.getRootFolder()["sourcefile"].data,
                         "some source file")

    def test_bad_overwrite(self):
        file = self.addResource("/sourcefile", "some source file",
                                contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "COPY",
                   "DESTINATION": "http://localhost/sourcefile",
                   "OVERWRITE": "X"},
            handle_errors = True)

        self.assertEqual(response.getStatus(), 400)

    def test_copy_folder(self):
        self.createCollectionResourceStructure()

        response = self.publish(
            "/a", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "COPY",
                   "DESTINATION": "http://localhost/c/"},
            handle_errors = True)

        self.assertEqual(response.getStatus(), 201)
        self.assertEqual(response.getHeader("location"),
                                            "http://localhost/c")
        self.assertEqual(list(self.getRootFolder()["c"].keys()), [u"r2", u"r3"])


class MOVETestCase(dav.DAVTestCase):
    """These tests are very similar to the COPY tests. Actually I copied them
    and modified them to work with MOVE.
    """

    def test_move_file(self):
        file = self.addResource("/sourcefile", "some file content",
                                contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "MOVE",
                   "DESTINATION": "http://localhost/destfile"})

        self.assertEqual(response.getStatus(), 201)
        self.assertEqual(response.getHeader("location"),
                         "http://localhost/destfile")

        self.assertEqual(self.getRootFolder()["destfile"].data,
                         "some file content")
        self.assert_("sourcefile" not in self.getRootFolder().keys())

    def test_move_file_nodest(self):
        file = self.addResource("/sourcefile", "some file content",
                                contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "MOVE"}, handle_errors = True)

        self.assertEqual(response.getStatus(), 400)

    def test_move_file_default_overwrite(self):
        file = self.addResource("/sourcefile", "some source file",
                                contentType = "text/plain")
        destfile = self.addResource("/destfile", "some dest file",
                                    contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "MOVE",
                   "DESTINATION": "http://localhost/destfile"})

        self.assertEqual(response.getStatus(), 204)
        self.assertEqual(self.getRootFolder()["destfile"].data,
                         "some source file")
        self.assert_("sourcefile" not in self.getRootFolder().keys())

    def test_move_file_true_overwrite(self):
        file = self.addResource("/sourcefile", "some source file",
                                contentType = "text/plain")
        destfile = self.addResource("/destfile", "some dest file",
                                    contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "MOVE",
                   "DESTINATION": "http://localhost/destfile",
                   "OVERWRITE": "T"})

        self.assertEqual(response.getStatus(), 204)
        self.assertEqual(self.getRootFolder()["destfile"].data,
                         "some source file")
        self.assert_("sourcefile" not in self.getRootFolder().keys())

    def test_move_file_false_overwrite(self):
        file = self.addResource("/sourcefile", "some source file",
                                contentType = "text/plain")
        destfile = self.addResource("/destfile", "some dest file",
                                    contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "MOVE",
                   "DESTINATION": "http://localhost/destfile",
                   "OVERWRITE": "F"},
            handle_errors = True)

        self.assertEqual(response.getStatus(), 412)
        self.assertEqual(self.getRootFolder()["destfile"].data,
                         "some dest file")
        self.assertEqual(self.getRootFolder()["sourcefile"].data,
                         "some source file")

    def test_move_file_to_remove(self):
        file = self.addResource("/sourcefile", "some source file",
                                contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "MOVE",
                   "DESTINATION": "http://www.remove-server.com/destfile",
                   "OVERWRITE": "T"},
            handle_errors = True)

        self.assertEqual(response.getStatus(), 502)

    def test_move_file_no_destparent(self):
        file = self.addResource("/sourcefile", "some source file",
                                contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "MOVE",
                   "DESTINATION": "http://localhost/bla/destfile",
                   "OVERWRITE": "T"},
            handle_errors = True)

        self.assertEqual(response.getStatus(), 409)
        self.assertEqual(list(self.getRootFolder().keys()), [u"sourcefile"])

    def test_move_to_same_file(self):
        file = self.addResource("/sourcefile", "some source file",
                                contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "MOVE",
                   "DESTINATION": "http://localhost/sourcefile",
                   "OVERWRITE": "T"},
            handle_errors = True)

        self.assertEqual(response.getStatus(), 403)
        self.assertEqual(self.getRootFolder()["sourcefile"].data,
                         "some source file")

    def test_bad_overwrite(self):
        file = self.addResource("/sourcefile", "some source file",
                                contentType = "text/plain")

        response = self.publish(
            "/sourcefile", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "MOVE",
                   "DESTINATION": "http://localhost/sourcefile",
                   "OVERWRITE": "X"},
            handle_errors = True)

        self.assertEqual(response.getStatus(), 400)

    def test_move_folder(self):
        self.createCollectionResourceStructure()

        response = self.publish(
            "/a", basic = "mgr:mgrpw",
            env = {"REQUEST_METHOD": "MOVE",
                   "DESTINATION": "http://localhost/c/"},
            handle_errors = True)

        self.assertEqual(response.getStatus(), 201)
        self.assertEqual(response.getHeader("location"),
                                            "http://localhost/c")
        self.assertEqual(list(self.getRootFolder()["c"].keys()), [u"r2", u"r3"])


def test_suite():
    return unittest.TestSuite((
            unittest.makeSuite(COPYTestCase),
            unittest.makeSuite(MOVETestCase),
            ))


if __name__ == "__main__":
    unittest.main(defaultTest = "test_suite")
