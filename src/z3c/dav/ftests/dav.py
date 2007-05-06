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
"""Common utilities needed for writing WebDAV functional tests.

XXX - This really needs some tidying up, also the setup should be moved to
a global setup method so that individual tests can call it if they need to.

$Id$
"""

from cStringIO import StringIO
import os.path
from BTrees.OOBTree import OOBTree

import transaction

from zope import interface
from zope import component
from zope import schema

from zope.security.proxy import removeSecurityProxy
from zope.app.folder.folder import Folder
from zope.app.file.file import File
from zope.app.publication.http import HTTPPublication
from zope.security.management import newInteraction, endInteraction
from zope.security.testing import Principal, Participation
from zope.dublincore.interfaces import IWriteZopeDublinCore

from z3c.dav.publisher import WebDAVRequest
from z3c.dav.properties import DAVProperty

import z3c.dav.testing

here = os.path.dirname(os.path.realpath(__file__))
WebDAVLayer = z3c.dav.testing.WebDAVLayerClass(
    os.path.join(here, "ftesting.zcml"), __name__, "WebDAVLayer")


class IExamplePropertyStorage(interface.Interface):

    exampleintprop = schema.Int(
        title = u"Example Integer Property",
        description = u"")

    exampletextprop = schema.Text(
        title = u"Example Text Property",
        description = u"")

exampleIntProperty = DAVProperty("{DAVtest:}exampleintprop",
                                 IExamplePropertyStorage)

exampleTextProperty = DAVProperty("{DAVtest:}exampletextprop",
                                  IExamplePropertyStorage)
exampleTextProperty.restricted = True


ANNOT_KEY = "EXAMPLE_PROPERTY"
class ExamplePropertyStorage(object):
    interface.implements(IExamplePropertyStorage)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def _getproperty(name, default = None):
        def get(self):
            annots = getattr(removeSecurityProxy(self.context),
                             "exampleannots", {})
            return annots.get("%s_%s" %(ANNOT_KEY, name), default)
        def set(self, value):
            annots = getattr(removeSecurityProxy(self.context),
                             "exampleannots", None)
            if annots is None:
                annots = removeSecurityProxy(
                    self.context).exampleannots = OOBTree()
            annots["%s_%s" %(ANNOT_KEY, name)] = value
        return property(get, set)

    exampleintprop = _getproperty("exampleintprop", default = 0)

    exampletextprop = _getproperty("exampletextprop", default = u"")


class TestWebDAVRequest(WebDAVRequest):
    """."""
    def __init__(self, elem = None):
        if elem is not None:
            body = """<?xml version="1.0" encoding="utf-8" ?>
<D:propertyupdate xmlns:D="DAV:">
  <D:set>
    <D:prop />
  </D:set>
</D:propertyupdate>
"""
            f = StringIO(body)
        else:
            f = StringIO('')

        super(TestWebDAVRequest, self).__init__(
            f, {'CONTENT_TYPE': 'text/xml',
                'CONTENT_LENGTH': len(f.getvalue()),
                })

        # processInputs to test request
        self.processInputs()

        # if elem is given insert it into the proppatch request.
        if elem is not None:
            self.xmlDataSource[0][0].append(elem)


class DAVTestCase(z3c.dav.testing.WebDAVTestCase):

    layer = WebDAVLayer

    def login(self, principalid = "mgr"):
        """Some locking methods new an interaction in order to lock a resource
        """
        principal = Principal(principalid)
        participation = Participation(principal)
        newInteraction(participation)

    def logout(self):
        """End the current interaction so we run the publish method.
        """
        endInteraction()

    #
    # Some methods for creating dummy content.
    #
    def createCollections(self, path):
        collection = self.getRootFolder()
        if path[0] == '/':
            path = path[1:]
        path = path.split('/')
        for id in path[:-1]:
            try:
                collection = collection[id]
            except KeyError:
                collection[id] = Folder()
                collection = collection[id]
        return collection, path[-1]

    def createObject(self, path, obj):
        collection, id = self.createCollections(path)
        collection[id] = obj
        transaction.commit()
        return collection[id]

    def addResource(self, path, content, title = None, contentType = ''):
        resource = File(data = content, contentType = contentType)
        if title is not None:
            IWriteZopeDublinCore(resource).title = title
        return self.createObject(path, resource)

    def addCollection(self, path, title = None):
        coll = Folder()
        if title is not None:
            IWriteZopeDublinCore(coll).title = title
        return self.createObject(path, coll)

    def createCollectionResourceStructure(self):
        """  _____ rootFolder/ _____
            /          \            \
           r1       __ a/ __          b/
                   /        \
                   r2       r3
        """
        self.addResource("/r1", "first resource")
        self.addResource("/a/r2", "second resource")
        self.addResource("/a/r3", "third resource")
        self.addCollection("/b")

    def createFolderFileStructure(self):
        """  _____ rootFolder/ _____
            /          \            \
           r1       __ a/ __          b/
                   /        \
                   r2       r3
        """
        self.addResource("/r1", "first resource", contentType = "test/plain")
        self.addResource("/a/r2", "second resource", contentType = "text/plain")
        self.addResource("/a/r3", "third resource", contentType = "text/plain")
        self.createObject("/b", Folder())

    def checkPropfind(self, path = "/", basic = None, env = {},
                      properties = None):
        # - properties if set is a string containing the contents of the
        #   propfind XML element has specified in the WebDAV spec.
        if properties is not None:
            body = """<?xml version="1.0" encoding="utf-8" ?>
<propfind xmlns:D="DAV:" xmlns="DAV:">
  %s
</propfind>
""" % properties
            if not env.has_key("CONTENT_TYPE"):
                env["CONTENT_TYPE"] = "application/xml"
            env["CONTENT_LENGTH"] = len(body)
        else:
            body = ""
            env["CONTENT_LENGTH"] = 0

        if not env.has_key("REQUEST_METHOD"):
            env["REQUEST_METHOD"] = "PROPFIND"

        response = self.publish(path, basic = basic, env = env,
                                request_body = body)

        self.assertEqual(response.getStatus(), 207)
        self.assertEqual(response.getHeader("content-type"), "application/xml")

        return response

    def checkProppatch(self, path = '/', basic = None, env = {},
                       set_properties = None, remove_properties = None,
                       handle_errors = True):
        # - set_properties is None or a string that is the XML fragment
        #   that should be included within the <D:set><D:prop> section of
        #   a PROPPATCH request.
        # - remove_properties is None or a string that is the XML fragment
        #   that should be included within the <D:remove><D:prop> section of
        #   a PROPPATCH request.
        set_body = ""
        if set_properties:
            set_body = "<D:set><D:prop>%s</D:prop></D:set>" % set_properties

        remove_body = ""
        if remove_properties:
            remove_body = "<D:remove><D:prop>%s</D:prop></D:remove>" % \
                          remove_properties

        body = """<?xml version="1.0" encoding="utf-8" ?>
<D:propertyupdate xmlns:D="DAV:" xmlns="DAV:">
  %s %s
</D:propertyupdate>
        """ %(set_body, remove_body)
        body = body.encode("utf-8")

        if not env.has_key("CONTENT_TYPE"):
            env["CONTENT_TYPE"] = "application/xml"
        env["CONTENT_LENGTH"] = len(body)

        if not env.has_key("REQUEST_METHOD"):
            env["REQUEST_METHOD"] = "PROPPATCH"

        response = self.publish(path, basic = basic, env = env,
                                request_body = body,
                                handle_errors = handle_errors)

        self.assertEqual(response.getStatus(), 207)
        self.assertEqual(response.getHeader("content-type"), "application/xml")

        return response
