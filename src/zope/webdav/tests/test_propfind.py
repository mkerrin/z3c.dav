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
"""Test WebDAV propfind method.

It is easier to do this has a unit test has we have complete control over
what properties are defined or not.

$Id$
"""

import unittest
from cStringIO import StringIO
import UserDict

from zope import interface
from zope import component
from zope import schema
import zope.schema.interfaces
from zope.traversing.browser.interfaces import IAbsoluteURL
from zope.filerepresentation.interfaces import IReadDirectory
from zope.app.container.interfaces import IReadContainer
from zope.app.error.interfaces import IErrorReportingUtility
from zope.security.interfaces import Unauthorized, IUnauthorized
from zope.security.interfaces import IChecker
from zope.security.checker import CheckerPublic

import zope.webdav.properties
import zope.webdav.publisher
import zope.webdav.widgets
import zope.webdav.exceptions
import zope.webdav.coreproperties
from zope.webdav.propfind import PROPFIND
from zope.etree.testing import etreeSetup, etreeTearDown, assertXMLEqual
from zope.etree.interfaces import IEtree

from test_proppatch import unauthProperty, UnauthorizedPropertyStorage, \
     IUnauthorizedPropertyStorage
from utils import TestMultiStatusBody

class TestRequest(zope.webdav.publisher.WebDAVRequest):

    def __init__(self, properties = None, environ = {}):
        if properties is not None:
            body = """<?xml version="1.0" encoding="utf-8" ?>
<propfind xmlns:D="DAV:" xmlns="DAV:">
  %s
</propfind>
""" % properties
        else:
            body = ""

        env = environ.copy()
        env.setdefault("REQUEST_METHOD", "PROPFIND")
        env.setdefault("CONTENT_TYPE", "text/xml")
        env.setdefault("CONTENT_LENGTH", len(body))

        super(TestRequest, self).__init__(StringIO(body), env)

        # call processInputs now since we are in a unit test.
        self.processInputs()


class PROPFINDBodyParsed(PROPFIND):

    propertiesFactory = extraArg = depth = None

    def handlePropfindResource(self, ob, req,
                               depth, propertiesFactory, extraArg):
        self.propertiesFactory = propertiesFactory
        self.extraArg = extraArg
        self.depth = depth

        return []


class PROPFINDBodyTestCase(unittest.TestCase):
    # Using PROPFINDBodyParsed test that the correct method and arguements
    # get set up.

    def setUp(self):
        etreeSetup()

    def tearDown(self):
        etreeTearDown()

    def checkPropfind(self, properties = None, environ = {}):
        request = TestRequest(properties = properties, environ = environ)
        propfind = PROPFINDBodyParsed(None, request)
        propfind.PROPFIND()

        return propfind

    def test_notxml(self):
        self.assertRaises(zope.webdav.interfaces.BadRequest, self.checkPropfind,
            "<propname />", {"CONTENT_TYPE": "text/plain"})

    def test_bad_depthheader(self):
        self.assertRaises(zope.webdav.interfaces.BadRequest, self.checkPropfind,
            "<propname />", {"DEPTH": "2"})

    def test_depth_header(self):
        propf = self.checkPropfind("<propname />", {"DEPTH": "0"})
        self.assertEqual(propf.depth, "0")
        propf = self.checkPropfind("<propname />", {"DEPTH": "1"})
        self.assertEqual(propf.depth, "1")
        propf = self.checkPropfind("<propname />", {"DEPTH": "infinity"})
        self.assertEqual(propf.depth, "infinity")

    def test_xml_propname(self):
        propf = self.checkPropfind("<propname />")
        self.assertEqual(propf.propertiesFactory, propf.renderPropnames)
        self.assertEqual(propf.extraArg, None)

    def test_xml_allprop(self):
        propf = self.checkPropfind("<allprop />")
        self.assertEqual(propf.propertiesFactory, propf.renderAllProperties)
        self.assertEqual(propf.extraArg, None)

    def test_xml_allprop_with_include(self):
        includes = """<include xmlns="DAV:"><davproperty /></include>"""
        propf = self.checkPropfind("<allprop/>%s" % includes)
        self.assertEqual(propf.propertiesFactory, propf.renderAllProperties)
        assertXMLEqual(propf.extraArg, includes)

    def test_xml_emptyprop(self):
        propf = self.checkPropfind("<prop />")
        self.assertEqual(propf.propertiesFactory, propf.renderAllProperties)
        self.assertEqual(propf.extraArg, None)

    def test_xml_someprops(self):
        props = """<prop xmlns="DAV:"><someprop/></prop>"""
        propf = self.checkPropfind(props)
        self.assertEqual(propf.propertiesFactory,
                         propf.renderSelectedProperties)
        assertXMLEqual(propf.extraArg, props)

    def test_emptybody(self):
        propf = self.checkPropfind()
        self.assertEqual(propf.propertiesFactory, propf.renderAllProperties)
        self.assertEqual(propf.extraArg, None)

    def test_xml_nopropfind_element(self):
        body = """<?xml version="1.0" encoding="utf-8" ?>
<nopropfind xmlns:D="DAV:" xmlns="DAV:">
  invalid xml
</nopropfind>
        """
        env = {"CONTENT_TYPE": "text/xml",
               "CONTENT_LENGTH": len(body)}
        request = zope.webdav.publisher.WebDAVRequest(StringIO(body), env)
        request.processInputs()

        propf = PROPFINDBodyParsed(None, request)
        self.assertRaises(zope.webdav.interfaces.UnprocessableError,
                          propf.PROPFIND)

    def test_xml_propfind_bad_content(self):
        self.assertRaises(zope.webdav.interfaces.UnprocessableError,
                          self.checkPropfind, properties = "<noproperties />")


class IExamplePropertyStorage(interface.Interface):

    exampleintprop = schema.Int(
        title = u"Example Integer Property")

    exampletextprop = schema.Text(
        title = u"Example Text Property")

class IExtraPropertyStorage(interface.Interface):

    extratextprop = schema.Text(
        title = u"Property with no storage")

class IBrokenPropertyStorage(interface.Interface):

    brokenprop = schema.Text(
        title = u"Property which does not render")

exampleIntProperty = zope.webdav.properties.DAVProperty(
    "{DAVtest:}exampleintprop", IExamplePropertyStorage)
exampleTextProperty = zope.webdav.properties.DAVProperty(
    "{DAVtest:}exampletextprop", IExamplePropertyStorage)
extraTextProperty = zope.webdav.properties.DAVProperty(
    "{DAVtest:}extratextprop", IExtraPropertyStorage)
brokenProperty = zope.webdav.properties.DAVProperty(
    "{DAVtest:}brokenprop", IBrokenPropertyStorage)
# this is a hack to make all the render all properties work as this broken
# property then never shows up these tests responses.
brokenProperty.restricted = True


class ExamplePropertyStorage(object):
    interface.implements(IExamplePropertyStorage)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def _getproperty(name, default = None):
        def get(self):
            return getattr(self.context, name, default)
        def set(self, value):
            setattr(self.context, name, value)
        return property(get, set)

    exampleintprop = _getproperty("intprop", default = 0)

    exampletextprop = _getproperty("text", default = u"")


class BrokenPropertyStorage(object):
    interface.implements(IBrokenPropertyStorage)

    def __init__(self, context, request):
        pass

    @property
    def brokenprop(self):
        raise NotImplementedError("The property brokenprop is not implemented.")


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


class ICollection(IReadContainer):
    pass


class Collection(UserDict.UserDict):
    interface.implements(ICollection)

    def __setitem__(self, key, value):
        self.data[key] = value
        value.__parent__ = self
        value.__name__ = key


class DummyResourceURL(object):
    interface.implements(IAbsoluteURL)

    def __init__(self, context, request):
        self.context = context

    def __str__(self):
        if getattr(self.context, "__parent__", None) is not None:
            path = DummyResourceURL(self.context.__parent__, None)()
        else:
            path = ""

        if getattr(self.context, "__name__", None) is not None:
            path += "/" + self.context.__name__
        elif IResource.providedBy(self.context):
            path += "/resource"
        elif ICollection.providedBy(self.context):
            path += "/collection"
        else:
            raise ValueError("unknown context type")

        return path

    __call__ = __str__


def propfindSetUp():
    etreeSetup()

    gsm = component.getGlobalSiteManager()

    gsm.registerUtility(exampleIntProperty,
                        name = "{DAVtest:}exampleintprop",
                        provided = zope.webdav.interfaces.IDAVProperty)
    gsm.registerUtility(exampleTextProperty,
                        name = "{DAVtest:}exampletextprop",
                        provided = zope.webdav.interfaces.IDAVProperty)
    exampleTextProperty.restricted = False
    gsm.registerUtility(extraTextProperty,
                        name = "{DAVtest:}extratextprop",
                        provided = zope.webdav.interfaces.IDAVProperty)
    gsm.registerUtility(zope.webdav.coreproperties.resourcetype,
                        name = "{DAV:}resourcetype")
    gsm.registerUtility(brokenProperty, name = "{DAVtest:}brokenprop",
                        provided = zope.webdav.interfaces.IDAVProperty)
    gsm.registerUtility(unauthProperty, name = "{DAVtest:}unauthprop")
    # make sure that this property is always restricted so that we
    # only try and render this property whenever we want to.
    unauthProperty.restricted = True

    gsm.registerAdapter(ExamplePropertyStorage,
                        (IResource, zope.webdav.interfaces.IWebDAVRequest),
                        provided = IExamplePropertyStorage)
    gsm.registerAdapter(BrokenPropertyStorage,
                        (IResource, zope.webdav.interfaces.IWebDAVRequest),
                        provided = IBrokenPropertyStorage)
    gsm.registerAdapter(UnauthorizedPropertyStorage,
                        (IResource, zope.webdav.interfaces.IWebDAVRequest),
                        provided = IUnauthorizedPropertyStorage)
    gsm.registerAdapter(zope.webdav.coreproperties.ResourceTypeAdapter)

    gsm.registerAdapter(DummyResourceURL,
                        (IResource, zope.webdav.interfaces.IWebDAVRequest))
    gsm.registerAdapter(DummyResourceURL,
                        (ICollection, zope.webdav.interfaces.IWebDAVRequest))

    gsm.registerAdapter(zope.webdav.widgets.TextDAVWidget,
                        (zope.schema.interfaces.IText,
                         zope.webdav.interfaces.IWebDAVRequest))
    gsm.registerAdapter(zope.webdav.widgets.IntDAVWidget,
                        (zope.schema.interfaces.IInt,
                         zope.webdav.interfaces.IWebDAVRequest))
    gsm.registerAdapter(zope.webdav.widgets.ListDAVWidget,
                        (zope.schema.interfaces.IList,
                         zope.webdav.interfaces.IWebDAVRequest))

    gsm.registerAdapter(zope.webdav.exceptions.PropertyNotFoundError,
                        (zope.webdav.interfaces.IPropertyNotFound,
                         zope.webdav.interfaces.IWebDAVRequest))
    gsm.registerAdapter(zope.webdav.exceptions.UnauthorizedError,
                        (IUnauthorized,
                         zope.webdav.interfaces.IWebDAVRequest))

def propfindTearDown():
    etreeTearDown()

    gsm = component.getGlobalSiteManager()

    gsm.unregisterUtility(exampleIntProperty,
                          name = "{DAVtest:}exampleintprop",
                          provided = zope.webdav.interfaces.IDAVProperty)
    gsm.unregisterUtility(exampleTextProperty,
                          name = "{DAVtest:}exampletextprop",
                          provided = zope.webdav.interfaces.IDAVProperty)
    gsm.unregisterUtility(extraTextProperty,
                          name = "{DAVtest:}extratextprop",
                          provided = zope.webdav.interfaces.IDAVProperty)
    gsm.unregisterUtility(zope.webdav.coreproperties.resourcetype,
                          name = "{DAV:}resourcetype")
    gsm.unregisterUtility(brokenProperty, name = "{DAVtest:}brokenprop",
                          provided = zope.webdav.interfaces.IDAVProperty)
    gsm.unregisterUtility(unauthProperty, name = "{DAVtest:}unauthprop")

    gsm.unregisterAdapter(ExamplePropertyStorage,
                          (IResource, zope.webdav.interfaces.IWebDAVRequest),
                          provided = IExamplePropertyStorage)
    gsm.unregisterAdapter(BrokenPropertyStorage,
                          (IResource, zope.webdav.interfaces.IWebDAVRequest),
                          provided = IBrokenPropertyStorage)
    gsm.registerAdapter(UnauthorizedPropertyStorage,
                        (IResource, zope.webdav.interfaces.IWebDAVRequest),
                        provided = IUnauthorizedPropertyStorage)
    gsm.unregisterAdapter(zope.webdav.coreproperties.ResourceTypeAdapter)

    gsm.unregisterAdapter(DummyResourceURL,
                          (IResource, zope.webdav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(DummyResourceURL,
                          (ICollection, zope.webdav.interfaces.IWebDAVRequest))

    gsm.unregisterAdapter(zope.webdav.widgets.TextDAVWidget,
                          (zope.schema.interfaces.IText,
                           zope.webdav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(zope.webdav.widgets.IntDAVWidget,
                          (zope.schema.interfaces.IInt,
                           zope.webdav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(zope.webdav.exceptions.PropertyNotFoundError,
                          (zope.webdav.interfaces.IPropertyNotFound,
                           zope.webdav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(zope.webdav.exceptions.UnauthorizedError,
                          (IUnauthorized,
                           zope.webdav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(zope.webdav.widgets.ListDAVWidget,
                          (zope.schema.interfaces.IList,
                           zope.webdav.interfaces.IWebDAVRequest))


class ErrorReportingUtility(object):
    interface.implements(IErrorReportingUtility)

    def __init__(self):
        self.errors = []

    def raising(self, exc_info, request):
        self.errors.append((exc_info, request))


class PROPFINDTestRender(unittest.TestCase, TestMultiStatusBody):
    # Test all the methods that render a resource into a `response' XML
    # element. We are going to need to register the DAV widgets for
    # text and int properties.

    def setUp(self):
        propfindSetUp()
        ## This is for the test_renderBrokenProperty
        self.errUtility = ErrorReportingUtility()
        component.getGlobalSiteManager().registerUtility(self.errUtility)

    def tearDown(self):
        propfindTearDown()
        ## This is for the test_renderBrokenProperty
        component.getGlobalSiteManager().unregisterUtility(self.errUtility)
        del self.errUtility

    def test_renderPropnames(self):
        resource = Resource("some text", 10)
        request = zope.webdav.publisher.WebDAVRequest(StringIO(""), {})

        propf = PROPFIND(None, None)
        response = propf.renderPropnames(resource, request, None)

        # call the response to render to an XML fragment.
        response = response()

        self.assertMSPropertyValue(response, "{DAVtest:}exampletextprop")
        self.assertMSPropertyValue(response, "{DAVtest:}exampleintprop")
        self.assertMSPropertyValue(response, "{DAV:}resourcetype")
        self.assertMSPropertyValue(response, "{DAVtest:}brokenprop")
        self.assertMSPropertyValue(response, "{DAVtest:}unauthprop")

        assertXMLEqual(response, """<ns0:response xmlns:ns0="DAV:">
<ns0:href xmlns:ns0="DAV:">/resource</ns0:href>
<ns0:propstat xmlns:ns0="DAV:" xmlns:ns01="DAVtest:">
  <ns0:prop xmlns:ns0="DAV:">
    <ns1:brokenprop xmlns:ns1="DAVtest:"/>
    <ns1:exampletextprop xmlns:ns1="DAVtest:"/>
    <ns1:exampleintprop xmlns:ns1="DAVtest:"/>
    <ns1:unauthprop xmlns:ns1="DAVtest:"/>
    <ns0:resourcetype />
  </ns0:prop>
  <ns0:status xmlns:ns0="DAV:">HTTP/1.1 200 OK</ns0:status>
</ns0:propstat></ns0:response>""")

    def test_renderSelected(self):
        resource = Resource("some text", 10)
        request = zope.webdav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        etree = component.getUtility(IEtree)
        props = etree.fromstring("""<prop xmlns="DAV:" xmlns:D="DAVtest:">
<D:exampletextprop />
<D:exampleintprop />
</prop>""")
        response = propf.renderSelectedProperties(resource, request, props)

        assertXMLEqual(response(), """<ns0:response xmlns:ns0="DAV:">
<ns0:href xmlns:ns0="DAV:">/resource</ns0:href>
<ns0:propstat xmlns:ns0="DAV:" xmlns:ns01="DAVtest:">
  <ns0:prop xmlns:ns0="DAV:">
    <ns01:exampletextprop xmlns:ns0="DAVtest:">some text</ns01:exampletextprop>
    <ns01:exampleintprop xmlns:ns0="DAVtest:">10</ns01:exampleintprop>
  </ns0:prop>
  <ns0:status xmlns:ns0="DAV:">HTTP/1.1 200 OK</ns0:status>
</ns0:propstat></ns0:response>""")

    def test_renderSelected_notfound(self):
        resource = Resource("some text", 10)
        request = zope.webdav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        etree = component.getUtility(IEtree)
        props = etree.fromstring("""<prop xmlns="DAV:" xmlns:D="DAVtest:">
<D:exampletextprop />
<D:extratextprop />
</prop>""")
        response = propf.renderSelectedProperties(resource, request, props)

        assertXMLEqual(response(), """<ns0:response xmlns:ns0="DAV:">
<ns0:href xmlns:ns0="DAV:">/resource</ns0:href>
<ns0:propstat xmlns:ns0="DAV:" xmlns:ns01="DAVtest:">
  <ns0:prop xmlns:ns0="DAV:">
    <ns01:exampletextprop xmlns:ns0="DAVtest:">some text</ns01:exampletextprop>
  </ns0:prop>
  <ns0:status xmlns:ns0="DAV:">HTTP/1.1 200 OK</ns0:status>
</ns0:propstat>
<ns0:propstat xmlns:ns0="DAV:" xmlns:ns01="DAVtest:">
  <ns0:prop xmlns:ns0="DAV:">
    <ns01:extratextprop xmlns:ns0="DAVtest:" />
  </ns0:prop>
  <ns0:status xmlns:ns0="DAV:">HTTP/1.1 404 Not Found</ns0:status>
</ns0:propstat>
</ns0:response>""")

    def test_renderAllProperties(self):
        resource = Resource("some text", 10)
        request = zope.webdav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        response = propf.renderAllProperties(resource, request, None)

        assertXMLEqual(response(), """<ns0:response xmlns:ns0="DAV:">
<ns0:href xmlns:ns0="DAV:">/resource</ns0:href>
<ns0:propstat xmlns:ns0="DAV:" xmlns:ns01="DAVtest:">
  <ns0:prop xmlns:ns0="DAV:">
    <ns01:exampletextprop xmlns:ns0="DAVtest:">some text</ns01:exampletextprop>
    <ns01:exampleintprop xmlns:ns0="DAVtest:">10</ns01:exampleintprop>
    <ns0:resourcetype />
  </ns0:prop>
  <ns0:status xmlns:ns0="DAV:">HTTP/1.1 200 OK</ns0:status>
</ns0:propstat></ns0:response>""")

    def test_renderAllProperties_withInclude(self):
        resource = Resource("some text", 10)
        request = zope.webdav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        etree = component.getUtility(IEtree)
        include = etree.fromstring("""<include xmlns="DAV:" xmlns:D="DAVtest:">
<D:exampletextprop />
</include>""")
        response = propf.renderAllProperties(resource, request, include)

        assertXMLEqual(response(), """<ns0:response xmlns:ns0="DAV:">
<ns0:href xmlns:ns0="DAV:">/resource</ns0:href>
<ns0:propstat xmlns:ns0="DAV:" xmlns:ns01="DAVtest:">
  <ns0:prop xmlns:ns0="DAV:">
    <ns01:exampletextprop xmlns:ns0="DAVtest:">some text</ns01:exampletextprop>
    <ns01:exampleintprop xmlns:ns0="DAVtest:">10</ns01:exampleintprop>
    <ns0:resourcetype />
  </ns0:prop>
  <ns0:status xmlns:ns0="DAV:">HTTP/1.1 200 OK</ns0:status>
</ns0:propstat></ns0:response>""")

    def test_renderAllProperties_withRestrictedProp(self):
        resource = Resource("some text", 10)
        request = zope.webdav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        exampleTextProperty.restricted = True
        response = propf.renderAllProperties(resource, request, None)

        assertXMLEqual(response(), """<ns0:response xmlns:ns0="DAV:">
<ns0:href xmlns:ns0="DAV:">/resource</ns0:href>
<ns0:propstat xmlns:ns0="DAV:" xmlns:ns01="DAVtest:">
  <ns0:prop xmlns:ns0="DAV:">
    <ns01:exampleintprop xmlns:ns0="DAVtest:">10</ns01:exampleintprop>
    <ns0:resourcetype />
  </ns0:prop>
  <ns0:status xmlns:ns0="DAV:">HTTP/1.1 200 OK</ns0:status>
</ns0:propstat></ns0:response>""")

    def test_renderAllProperties_withRestrictedProp_include(self):
        resource = Resource("some text", 10)
        request = zope.webdav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        exampleTextProperty.restricted = True
        etree = component.getUtility(IEtree)
        include = etree.fromstring("""<include xmlns="DAV:" xmlns:D="DAVtest:">
<D:exampletextprop />
</include>""")
        response = propf.renderAllProperties(resource, request, include)

        assertXMLEqual(response(), """<ns0:response xmlns:ns0="DAV:">
<ns0:href xmlns:ns0="DAV:">/resource</ns0:href>
<ns0:propstat xmlns:ns0="DAV:" xmlns:ns01="DAVtest:">
  <ns0:prop xmlns:ns0="DAV:">
    <ns01:exampletextprop xmlns:ns0="DAVtest:">some text</ns01:exampletextprop>
    <ns01:exampleintprop xmlns:ns0="DAVtest:">10</ns01:exampleintprop>
    <ns0:resourcetype />
  </ns0:prop>
  <ns0:status xmlns:ns0="DAV:">HTTP/1.1 200 OK</ns0:status>
</ns0:propstat></ns0:response>""")

    def test_renderBrokenProperty(self):
        resource = Resource("some text", 10)
        request = zope.webdav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        etree = component.getUtility(IEtree)
        props = etree.fromstring("""<prop xmlns="DAV:" xmlns:D="DAVtest:">
<D:brokenprop />
</prop>""")
        response = propf.renderSelectedProperties(resource, request, props)
        response = response()

        self.assertMSPropertyValue(response, "{DAVtest:}brokenprop",
                                   status = 500)

        # now check that the error reporting utility caught the error.
        self.assertEqual(len(self.errUtility.errors), 1)
        error = self.errUtility.errors[0]
        self.assertEqual(isinstance(error[0][1], NotImplementedError), True)

    def test_render_selected_unauthorizedProperty(self):
        resource = Resource("some text", 10)
        request = zope.webdav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        etree = component.getUtility(IEtree)
        props = etree.fromstring("""<prop xmlns="DAV:" xmlns:D="DAVtest:">
<D:unauthprop />
<D:exampletextprop />
</prop>""")

        response = propf.renderSelectedProperties(resource, request, props)
        response = response()

        # The PROPFIND method should return a 401 when the user is unauthorized
        # to view a property.
        self.assertMSPropertyValue(response, "{DAVtest:}exampletextprop",
                                   text_value = "some text")
        self.assertMSPropertyValue(response, "{DAVtest:}unauthprop",
                                   status = 401)

        # PROPFIND does catch all exceptions during the main PROPFIND method
        # but instead we need to make sure that the renderSelectedProperties
        # does throw the exception.

    def test_renderAllProperties_unauthorized(self):
        # If we request to render all property but we are unauthorized to
        # access one of the propertues then this property should be threated
        # as if it were restricted property and not returned to the user.
        resource = Resource("some text", 10)
        request = zope.webdav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, request)

        # Set the unauthproperty as un-restricted so that the
        # renderAllProperties will render all the properties.
        unauthProperty.restricted = False

        # PROPFIND does catch all exceptions during the main PROPFIND method
        # but instead we need to make sure that the renderSelectedProperties
        # does throw the exception.
        response = propf.renderAllProperties(resource, request, None)
        response = response()

        self.assertEqual(len(response.findall("{DAV:}propstat")), 1)
        self.assertEqual(len(response.findall("{DAV:}propstat/{DAV:}prop")), 1)

        foundUnauthProp = False
        for prop in response.findall("{DAV:}propstat/{DAV:}prop")[0]:
            if prop.tag == "{DAVtest:}unauthprop":
                foundUnauthProp = True

        self.assert_(not foundUnauthProp,
                     "The unauthprop should not be included in the all " \
                     "property response since it has security restrictions.")

    def test_renderAllProperties_unauthorized_included(self):
        # If we request to render all properties, and request to render a
        # property we ain't authorized via the 'include' element then we
        # should get the property back as part of the multistatus response
        # but with a status 401 and no content.
        resource = Resource("some text", 10)
        request = zope.webdav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, request)

        etree = component.getUtility(IEtree)
        includes = etree.fromstring("""<include xmlns="DAV:" xmlns:D="DAVtest:">
<D:unauthprop />
</include>""")

        response = propf.renderAllProperties(resource, request, includes)
        response = response()

        self.assertEqual(len(response.findall("{DAV:}propstat")), 2)

        self.assertMSPropertyValue(
            response, "{DAVtest:}unauthprop", status = 401)

    def test_renderAllProperties_broken_included(self):
        # If we request to render all properties, and to forse render a
        # broken property via the 'include' element then we should get
        # this property back as part of the multistatus response but with a
        # status 500 and no content.
        resource = Resource("some text", 10)
        request = zope.webdav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, request)

        etree = component.getUtility(IEtree)
        includes = etree.fromstring("""<include xmlns="DAV:" xmlns:D="DAVtest:">
<D:brokenprop />
</include>""")

        response = propf.renderAllProperties(resource, request, includes)
        response = response()

        self.assertEqual(len(response.findall("{DAV:}propstat")), 2)

        self.assertMSPropertyValue(
            response, "{DAVtest:}brokenprop", status = 500)

        self.assertEqual(len(self.errUtility.errors), 1)
        exc_info = self.errUtility.errors[0]
        self.assertEqual(isinstance(exc_info[0][1], NotImplementedError), True)


class CollectionSecurityChecker(object):
    # Simple security checker to make the recursive propfind method handle
    # the canAccess call that is made during the processing of these requests.
    interface.implements(IChecker)

    def __init__(self, get_permissions = {}):
        self.get_permissions = get_permissions

    def check_getattr(self, ob, name):
        permission = self.get_permissions.get(name)
        if permission is CheckerPublic:
            return
        raise Unauthorized(object, name, permission)

    def check_setattr(self, ob, name):
        raise NotImplementedError("check_setattr(ob, name) not implemented")

    def check(self, ob, operation):
        raise NotImplementedError("check(ob, operation) not implemented")

    def proxy(self, value):
        raise NotImplementedError("proxy(value) not implemented")


def readDirectory(container):
    container.__Security_checker__ = CollectionSecurityChecker(
        {"values": CheckerPublic})
    return container


class PROPFINDRecuseTest(unittest.TestCase):

    def setUp(self):
        propfindSetUp()
        # make sure the unauthProperty is restricted has otherwise it will
        # break all the renderAllProperties methods.
        unauthProperty.restricted = True

        component.getGlobalSiteManager().registerAdapter(
            readDirectory, (IReadContainer,), provided = IReadDirectory)

    def tearDown(self):
        propfindTearDown()

        component.getGlobalSiteManager().unregisterAdapter(
            readDirectory, (IReadContainer,), provided = IReadDirectory)

    def test_handlePropfindResource(self):
        collection = Collection()
        collection["r1"] = Resource("some text - r1", 2)
        collection["c"] = Collection()
        collection["c"]["r2"] = Resource("some text - r2", 4)
        request = zope.webdav.publisher.WebDAVRequest(StringIO(""), {})
        request.processInputs()
        propf = PROPFIND(collection, request)

        result = propf.PROPFIND()
        etree = component.getUtility(IEtree)
        etree.fromstring(result)

        assertXMLEqual(result, """<ns0:multistatus xmlns:ns0="DAV:">
<ns0:response xmlns:ns0="DAV:">
  <ns0:href xmlns:ns0="DAV:">/collection/</ns0:href>
  <ns0:propstat xmlns:ns0="DAV:">
    <ns0:prop xmlns:ns0="DAV:">
      <ns0:resourcetype xmlns:ns0="DAV:">
        <ns0:collection xmlns:ns0="DAV:"/>
      </ns0:resourcetype>
    </ns0:prop>
    <ns0:status xmlns:ns0="DAV:">HTTP/1.1 200 OK</ns0:status>
  </ns0:propstat>
</ns0:response>
<ns0:response xmlns:ns0="DAV:">
  <ns0:href xmlns:ns0="DAV:">/collection/c/</ns0:href>
  <ns0:propstat xmlns:ns0="DAV:">
    <ns0:prop xmlns:ns0="DAV:">
      <ns0:resourcetype xmlns:ns0="DAV:">
        <ns0:collection xmlns:ns0="DAV:"/>
      </ns0:resourcetype>
    </ns0:prop>
    <ns0:status xmlns:ns0="DAV:">HTTP/1.1 200 OK</ns0:status>
  </ns0:propstat>
</ns0:response>
<ns0:response xmlns:ns0="DAV:" xmlns:ns01="DAVtest:">
  <ns0:href xmlns:ns0="DAV:">/collection/c/r2</ns0:href>
  <ns0:propstat xmlns:ns0="DAV:" xmlns:ns01="DAVtest:">
    <ns0:prop xmlns:ns0="DAV:">
      <ns01:exampletextprop xmlns:ns0="DAVtest:">some text - r2</ns01:exampletextprop>
      <ns01:exampleintprop xmlns:ns0="DAVtest:">4</ns01:exampleintprop>
      <ns0:resourcetype xmlns:ns0="DAV:"/>
    </ns0:prop>
    <ns0:status xmlns:ns0="DAV:">HTTP/1.1 200 OK</ns0:status>
  </ns0:propstat>
</ns0:response>
<ns0:response xmlns:ns0="DAV:" xmlns:ns01="DAVtest:">
  <ns0:href xmlns:ns0="DAV:">/collection/r1</ns0:href>
  <ns0:propstat xmlns:ns0="DAV:" xmlns:ns01="DAVtest:">
    <ns0:prop xmlns:ns0="DAV:">
      <ns01:exampletextprop xmlns:ns0="DAVtest:">some text - r1</ns01:exampletextprop>
      <ns01:exampleintprop xmlns:ns0="DAVtest:">2</ns01:exampleintprop>
      <ns0:resourcetype xmlns:ns0="DAV:"/>
    </ns0:prop>
    <ns0:status xmlns:ns0="DAV:">HTTP/1.1 200 OK</ns0:status>
  </ns0:propstat>
</ns0:response></ns0:multistatus>
        """)

def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(PROPFINDBodyTestCase),
        unittest.makeSuite(PROPFINDTestRender),
        unittest.makeSuite(PROPFINDRecuseTest),
        ))
