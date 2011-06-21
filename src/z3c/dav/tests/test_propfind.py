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
"""Test WebDAV propfind method.

It is easier to do this has a unit test has we have complete control over
what properties are defined or not.
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
from zope.container.interfaces import IReadContainer
from zope.error.interfaces import IErrorReportingUtility
from zope.security.interfaces import Unauthorized, IUnauthorized
import zope.security.checker
import zope.security.interfaces

import z3c.dav.properties
import z3c.dav.publisher
import z3c.dav.widgets
import z3c.dav.exceptions
import z3c.dav.coreproperties
from z3c.dav.propfind import PROPFIND
from z3c.etree.testing import etreeSetup, etreeTearDown
from z3c.etree.testing import assertXMLEqual
from z3c.etree.testing import assertXMLEqualIgnoreOrdering
import z3c.etree

from test_proppatch import unauthProperty, UnauthorizedPropertyStorage, \
     IUnauthorizedPropertyStorage

class TestRequest(z3c.dav.publisher.WebDAVRequest):

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

    def test_plaintext_body(self):
        request = z3c.dav.publisher.WebDAVRequest(
            StringIO("some text"), environ = {"CONTENT_TYPE": "text/plain",
                                              "CONTENT_LENGTH": 9})
        request.processInputs()

        propfind = PROPFINDBodyParsed(None, request)
        self.assertRaises(z3c.dav.interfaces.BadRequest, propfind.PROPFIND)

    def test_plaintext_body_strlength(self):
        request = z3c.dav.publisher.WebDAVRequest(
            StringIO("some text"), environ = {"CONTENT_TYPE": "text/plain",
                                              "CONTENT_LENGTH": "9"})
        request.processInputs()

        propfind = PROPFINDBodyParsed(None, request)
        self.assertRaises(z3c.dav.interfaces.BadRequest, propfind.PROPFIND)

    def test_nobody_nolength(self):
        # Need to test that no BadRequest is raised by the PROPFIND method
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), environ = {})
        request.processInputs()

        self.assertEqual(
            request.getHeader("content-length", "missing"), "missing")

        propfind = PROPFINDBodyParsed(None, request)
        result = propfind.PROPFIND()

    def test_nobody_length_0(self):
        # Need to test that no BadRequest is raised by the PROPFIND method
        request = z3c.dav.publisher.WebDAVRequest(
            StringIO(""), environ = {"CONTENT_LENGTH": "0"})
        request.processInputs()

        propfind = PROPFINDBodyParsed(None, request)
        result = propfind.PROPFIND()

    def test_notxml(self):
        self.assertRaises(z3c.dav.interfaces.BadRequest, self.checkPropfind,
            "<propname />", {"CONTENT_TYPE": "text/plain"})

    def test_bad_depthheader(self):
        self.assertRaises(z3c.dav.interfaces.BadRequest, self.checkPropfind,
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
        request = z3c.dav.publisher.WebDAVRequest(StringIO(body), env)
        request.processInputs()

        propf = PROPFINDBodyParsed(None, request)
        self.assertRaises(z3c.dav.interfaces.UnprocessableError,
                          propf.PROPFIND)

    def test_xml_propfind_bad_content(self):
        self.assertRaises(z3c.dav.interfaces.UnprocessableError,
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

exampleIntProperty = z3c.dav.properties.DAVProperty(
    "{DAVtest:}exampleintprop", IExamplePropertyStorage)
exampleTextProperty = z3c.dav.properties.DAVProperty(
    "{DAVtest:}exampletextprop", IExamplePropertyStorage)
extraTextProperty = z3c.dav.properties.DAVProperty(
    "{DAVtest:}extratextprop", IExtraPropertyStorage)
brokenProperty = z3c.dav.properties.DAVProperty(
    "{DAVtest:}brokenprop", IBrokenPropertyStorage)
# this is a hack to make all the render all properties work as this broken
# property then never shows up these tests responses.
brokenProperty.restricted = True


class ExamplePropertyStorage(object):
    interface.implements(IExamplePropertyStorage)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def _getproperty(name):
        def get(self):
            # Don't supply default values to getattr as this hides any
            # exceptions that I need for the tests to run.
            return getattr(self.context, name)
        def set(self, value):
            setattr(self.context, name, value)
        return property(get, set)

    exampleintprop = _getproperty("intprop")

    exampletextprop = _getproperty("text")


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
                        provided = z3c.dav.interfaces.IDAVProperty)
    gsm.registerUtility(exampleTextProperty,
                        name = "{DAVtest:}exampletextprop",
                        provided = z3c.dav.interfaces.IDAVProperty)
    exampleTextProperty.restricted = False
    gsm.registerUtility(extraTextProperty,
                        name = "{DAVtest:}extratextprop",
                        provided = z3c.dav.interfaces.IDAVProperty)
    gsm.registerUtility(z3c.dav.coreproperties.resourcetype,
                        name = "{DAV:}resourcetype")
    gsm.registerUtility(brokenProperty, name = "{DAVtest:}brokenprop",
                        provided = z3c.dav.interfaces.IDAVProperty)
    gsm.registerUtility(unauthProperty, name = "{DAVtest:}unauthprop")
    # make sure that this property is always restricted so that we
    # only try and render this property whenever we want to.
    unauthProperty.restricted = True

    gsm.registerAdapter(ExamplePropertyStorage,
                        (IResource, z3c.dav.interfaces.IWebDAVRequest),
                        provided = IExamplePropertyStorage)
    gsm.registerAdapter(BrokenPropertyStorage,
                        (IResource, z3c.dav.interfaces.IWebDAVRequest),
                        provided = IBrokenPropertyStorage)
    gsm.registerAdapter(UnauthorizedPropertyStorage,
                        (IResource, z3c.dav.interfaces.IWebDAVRequest),
                        provided = IUnauthorizedPropertyStorage)
    gsm.registerAdapter(z3c.dav.coreproperties.ResourceTypeAdapter)

    gsm.registerAdapter(DummyResourceURL,
                        (IResource, z3c.dav.interfaces.IWebDAVRequest))
    gsm.registerAdapter(DummyResourceURL,
                        (ICollection, z3c.dav.interfaces.IWebDAVRequest))

    gsm.registerAdapter(z3c.dav.widgets.TextDAVWidget,
                        (zope.schema.interfaces.IText,
                         z3c.dav.interfaces.IWebDAVRequest))
    gsm.registerAdapter(z3c.dav.widgets.IntDAVWidget,
                        (zope.schema.interfaces.IInt,
                         z3c.dav.interfaces.IWebDAVRequest))
    gsm.registerAdapter(z3c.dav.widgets.ListDAVWidget,
                        (zope.schema.interfaces.IList,
                         z3c.dav.interfaces.IWebDAVRequest))

    gsm.registerAdapter(z3c.dav.exceptions.PropertyNotFoundError,
                        (z3c.dav.interfaces.IPropertyNotFound,
                         z3c.dav.interfaces.IWebDAVRequest))
    gsm.registerAdapter(z3c.dav.exceptions.UnauthorizedError,
                        (IUnauthorized,
                         z3c.dav.interfaces.IWebDAVRequest))
    gsm.registerAdapter(z3c.dav.exceptions.ForbiddenError,
                        (zope.security.interfaces.IForbidden,
                         z3c.dav.interfaces.IWebDAVRequest))


def propfindTearDown():
    etreeTearDown()

    gsm = component.getGlobalSiteManager()

    gsm.unregisterUtility(exampleIntProperty,
                          name = "{DAVtest:}exampleintprop",
                          provided = z3c.dav.interfaces.IDAVProperty)
    gsm.unregisterUtility(exampleTextProperty,
                          name = "{DAVtest:}exampletextprop",
                          provided = z3c.dav.interfaces.IDAVProperty)
    gsm.unregisterUtility(extraTextProperty,
                          name = "{DAVtest:}extratextprop",
                          provided = z3c.dav.interfaces.IDAVProperty)
    gsm.unregisterUtility(z3c.dav.coreproperties.resourcetype,
                          name = "{DAV:}resourcetype")
    gsm.unregisterUtility(brokenProperty, name = "{DAVtest:}brokenprop",
                          provided = z3c.dav.interfaces.IDAVProperty)
    gsm.unregisterUtility(unauthProperty, name = "{DAVtest:}unauthprop")

    gsm.unregisterAdapter(ExamplePropertyStorage,
                          (IResource, z3c.dav.interfaces.IWebDAVRequest),
                          provided = IExamplePropertyStorage)
    gsm.unregisterAdapter(BrokenPropertyStorage,
                          (IResource, z3c.dav.interfaces.IWebDAVRequest),
                          provided = IBrokenPropertyStorage)
    gsm.registerAdapter(UnauthorizedPropertyStorage,
                        (IResource, z3c.dav.interfaces.IWebDAVRequest),
                        provided = IUnauthorizedPropertyStorage)
    gsm.unregisterAdapter(z3c.dav.coreproperties.ResourceTypeAdapter)

    gsm.unregisterAdapter(DummyResourceURL,
                          (IResource, z3c.dav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(DummyResourceURL,
                          (ICollection, z3c.dav.interfaces.IWebDAVRequest))

    gsm.unregisterAdapter(z3c.dav.widgets.TextDAVWidget,
                          (zope.schema.interfaces.IText,
                           z3c.dav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(z3c.dav.widgets.IntDAVWidget,
                          (zope.schema.interfaces.IInt,
                           z3c.dav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(z3c.dav.exceptions.PropertyNotFoundError,
                          (z3c.dav.interfaces.IPropertyNotFound,
                           z3c.dav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(z3c.dav.exceptions.UnauthorizedError,
                          (IUnauthorized,
                           z3c.dav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(z3c.dav.exceptions.ForbiddenError,
                          (zope.security.interfaces.IForbidden,
                           z3c.dav.interfaces.IWebDAVRequest))
    gsm.unregisterAdapter(z3c.dav.widgets.ListDAVWidget,
                          (zope.schema.interfaces.IList,
                           z3c.dav.interfaces.IWebDAVRequest))


class ErrorReportingUtility(object):
    interface.implements(IErrorReportingUtility)

    def __init__(self):
        self.errors = []

    def raising(self, exc_info, request):
        self.errors.append((exc_info, request))


class PROPFINDTestRender(unittest.TestCase):
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
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})

        propf = PROPFIND(None, None)
        response = propf.renderPropnames(resource, request, None)

        # call the response to render to an XML fragment.
        response = response()

        assertXMLEqualIgnoreOrdering(response, """<D:response xmlns:D="DAV:">
<D:href>/resource</D:href>
<D:propstat xmlns:D1="DAVtest:">
  <D:prop>
    <ns1:brokenprop xmlns:ns1="DAVtest:"/>
    <ns1:exampletextprop xmlns:ns1="DAVtest:"/>
    <D:resourcetype />
    <ns1:exampleintprop xmlns:ns1="DAVtest:"/>
    <ns1:unauthprop xmlns:ns1="DAVtest:"/>
  </D:prop>
  <D:status>HTTP/1.1 200 Ok</D:status>
</D:propstat></D:response>""")

    def test_renderSelected(self):
        resource = Resource("some text", 10)
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        etree = z3c.etree.getEngine()
        props = etree.fromstring("""<prop xmlns="DAV:" xmlns:D="DAVtest:">
<D:exampletextprop />
<D:exampleintprop />
</prop>""")
        response = propf.renderSelectedProperties(resource, request, props)

        assertXMLEqualIgnoreOrdering(response(), """<D:response xmlns:D="DAV:">
<D:href>/resource</D:href>
<D:propstat xmlns:D1="DAVtest:">
  <D:prop>
    <D1:exampletextprop xmlns:D="DAVtest:">some text</D1:exampletextprop>
    <D1:exampleintprop xmlns:D="DAVtest:">10</D1:exampleintprop>
  </D:prop>
  <D:status>HTTP/1.1 200 Ok</D:status>
</D:propstat></D:response>""")

    def test_renderSelected_badProperty(self):
        resource = Resource("some text", 10)
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        etree = z3c.etree.getEngine()
        props = etree.Element(etree.QName("DAV:", "prop"))
        prop = etree.Element("{}bar")
        prop.tag = "{}bar" # lxml ignores the namespace in the above element
        props.append(prop)

        self.assertRaises(z3c.dav.interfaces.BadRequest,
                          propf.renderSelectedProperties,
                          resource, request, props)

    def test_renderSelected_badProperty2(self):
        resource = Resource("some text", 10)
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        etree = z3c.etree.getEngine()
        props = etree.Element(etree.QName("DAV:", "prop"))
        prop = etree.Element("bar")
        props.append(prop)

        response = propf.renderSelectedProperties(resource, request, props)
        assertXMLEqualIgnoreOrdering(response(),
                       """<D:response xmlns:D="DAV:">
<D:href>/resource</D:href>
<D:propstat>
  <D:prop>
    <bar />
  </D:prop>
  <D:status>HTTP/1.1 404 Not Found</D:status>
</D:propstat>
</D:response>""")

    def test_renderSelected_notfound(self):
        resource = Resource("some text", 10)
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        etree = z3c.etree.getEngine()
        props = etree.fromstring("""<prop xmlns="DAV:" xmlns:D="DAVtest:">
<D:exampletextprop />
<D:extratextprop />
</prop>""")
        response = propf.renderSelectedProperties(resource, request, props)

        assertXMLEqualIgnoreOrdering(response(), """<D:response xmlns:D="DAV:">
<D:href>/resource</D:href>
<D:propstat>
  <D:prop>
    <D1:exampletextprop xmlns:D1="DAVtest:">some text</D1:exampletextprop>
  </D:prop>
  <D:status>HTTP/1.1 200 Ok</D:status>
</D:propstat>
<D:propstat>
  <D:prop>
    <D1:extratextprop xmlns:D1="DAVtest:" />
  </D:prop>
  <D:status>HTTP/1.1 404 Not Found</D:status>
</D:propstat>
</D:response>""")

    def test_renderAllProperties(self):
        resource = Resource("some text", 10)
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        response = propf.renderAllProperties(resource, request, None)

        assertXMLEqualIgnoreOrdering(response(), """<D:response xmlns:D="DAV:">
<D:href>/resource</D:href>
<D:propstat>
  <D:prop>
    <D1:exampletextprop xmlns:D1="DAVtest:">some text</D1:exampletextprop>
    <D:resourcetype />
    <D1:exampleintprop xmlns:D1="DAVtest:">10</D1:exampleintprop>
  </D:prop>
  <D:status>HTTP/1.1 200 Ok</D:status>
</D:propstat></D:response>""")

    def test_renderAllProperties_withInclude(self):
        resource = Resource("some text", 10)
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        etree = z3c.etree.getEngine()
        include = etree.fromstring("""<include xmlns="DAV:" xmlns:D="DAVtest:">
<D:exampletextprop />
</include>""")
        response = propf.renderAllProperties(resource, request, include)

        assertXMLEqualIgnoreOrdering(response(), """<D:response xmlns:D="DAV:">
<D:href>/resource</D:href>
<D:propstat>
  <D:prop>
    <D1:exampletextprop xmlns:D1="DAVtest:">some text</D1:exampletextprop>
    <D:resourcetype />
    <D1:exampleintprop xmlns:D1="DAVtest:">10</D1:exampleintprop>
  </D:prop>
  <D:status>HTTP/1.1 200 Ok</D:status>
</D:propstat></D:response>""")

    def test_renderAllProperties_withRestrictedProp(self):
        resource = Resource("some text", 10)
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        exampleTextProperty.restricted = True
        response = propf.renderAllProperties(resource, request, None)

        assertXMLEqualIgnoreOrdering(response(), """<D:response xmlns:D="DAV:">
<D:href>/resource</D:href>
<D:propstat>
  <D:prop>
    <D:resourcetype />
    <D1:exampleintprop xmlns:D1="DAVtest:">10</D1:exampleintprop>
  </D:prop>
  <D:status>HTTP/1.1 200 Ok</D:status>
</D:propstat></D:response>""")

    def test_renderAllProperties_withRestrictedProp_include(self):
        resource = Resource("some text", 10)
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        exampleTextProperty.restricted = True
        etree = z3c.etree.getEngine()
        include = etree.fromstring("""<include xmlns="DAV:" xmlns:D="DAVtest:">
<D:exampletextprop />
</include>""")
        response = propf.renderAllProperties(resource, request, include)

        assertXMLEqualIgnoreOrdering(response(), """<D:response xmlns:D="DAV:">
<D:href>/resource</D:href>
<D:propstat>
  <D:prop>
    <D1:exampletextprop xmlns:D1="DAVtest:">some text</D1:exampletextprop>
    <D:resourcetype />
    <D1:exampleintprop xmlns:D1="DAVtest:">10</D1:exampleintprop>
  </D:prop>
  <D:status>HTTP/1.1 200 Ok</D:status>
</D:propstat></D:response>""")

    def test_renderBrokenProperty(self):
        resource = Resource("some text", 10)
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        etree = z3c.etree.getEngine()
        props = etree.fromstring("""<prop xmlns="DAV:" xmlns:D="DAVtest:">
<D:brokenprop />
</prop>""")
        response = propf.renderSelectedProperties(resource, request, props)
        response = response()

        assertXMLEqualIgnoreOrdering("""<response xmlns="DAV:">
<href>/resource</href>
<propstat>
  <prop>
    <ns1:brokenprop xmlns:ns1="DAVtest:" />
  </prop>
  <status>HTTP/1.1 500 Internal Server Error</status>
</propstat>
</response>""", response)

        # now check that the error reporting utility caught the error.
        self.assertEqual(len(self.errUtility.errors), 1)
        error = self.errUtility.errors[0]
        self.assertEqual(isinstance(error[0][1], NotImplementedError), True)

    def test_render_selected_unauthorizedProperty_toplevel(self):
        # If during the processing of a PROPFIND request and access to a
        # property on the requested resource is unauthorized to the current
        # user then we raise an `Unauthorized' requesting the user to log in.
        resource = Resource("some text", 10)
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        etree = z3c.etree.getEngine()
        props = etree.fromstring("""<prop xmlns="DAV:" xmlns:D="DAVtest:">
<D:unauthprop />
<D:exampletextprop />
</prop>""")

        self.assertRaises(
            zope.security.interfaces.Unauthorized,
            propf.renderSelectedProperties, resource, request, props)

    def test_render_selected_unauthorizedProperty_sublevel(self):
        # This is the same as the previous test but since we are rendering
        # a sub-resource to the requested resource - we render the forbidden
        # error as part of the successful `multistatus' response. This stops
        # errors from raising to the user when they might not ever have access
        # to the particular resource but they are still continue using the
        # system. Where as the previous test shows that they can still get
        # access to the system.
        resource = Resource("some text", 10)
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        etree = z3c.etree.getEngine()
        props = etree.fromstring("""<prop xmlns="DAV:" xmlns:D="DAVtest:">
<D:unauthprop />
<D:exampletextprop />
</prop>""")

        # The current `level' is the last argument to this method.
        response = propf.renderSelectedProperties(resource, request, props, 1)
        response = response()

        # The PROPFIND method should return a 401 when the user is unauthorized
        # to view a property.
        assertXMLEqualIgnoreOrdering("""<response xmlns="DAV:">
<href>/resource</href>
<propstat>
  <prop>
    <ns1:exampletextprop xmlns:ns1="DAVtest:">some text</ns1:exampletextprop>
  </prop>
  <status>HTTP/1.1 200 Ok</status>
</propstat>
<propstat>
  <prop>
    <ns1:unauthprop xmlns:ns1="DAVtest:" />
  </prop>
  <status>HTTP/1.1 401 Unauthorized</status>
</propstat>
</response>""", response)

        # PROPFIND does catch all exceptions during the main PROPFIND method
        # but instead we need to make sure that the renderSelectedProperties
        # does throw the exception.

    def test_renderAllProperties_unauthorized_toplevel(self):
        # If we request to render all property but we are unauthorized to
        # access one of the propertues then this property should be threated
        # as if it were restricted property and not returned to the user.
        resource = Resource("some text", 10)
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, request)

        # Set the unauthproperty as un-restricted so that the
        # renderAllProperties will render all the properties.
        unauthProperty.restricted = False

        # PROPFIND does catch all exceptions during the main PROPFIND method
        # but instead we need to make sure that the renderSelectedProperties
        # does throw the exception.
        response = propf.renderAllProperties(resource, request, None)
        response = response()

        # Note that the unauthprop is not included in the response.
        assertXMLEqualIgnoreOrdering("""<response xmlns="DAV:">
<href>/resource</href>
<propstat>
  <prop>
    <ns1:exampletextprop xmlns:ns1="DAVtest:">some text</ns1:exampletextprop>
    <resourcetype />
    <ns1:exampleintprop xmlns:ns1="DAVtest:">10</ns1:exampleintprop>
  </prop>
  <status>HTTP/1.1 200 Ok</status>
</propstat>
</response>""", response)

        # Since we silenty ignored returning a property. We now log the
        # Unauthorized exception so debuging and logging purposes.
        self.assertEqual(len(self.errUtility.errors), 1)
        exc_info = self.errUtility.errors[0]
        self.assertEqual(isinstance(exc_info[0][1], Unauthorized), True)

    def test_renderAllProperties_unauthorized_sublevel(self):
        # If we request to render all property but we are unauthorized to
        # access one of the propertues then this property should be threated
        # as if it were restricted property and not returned to the user.
        resource = Resource("some text", 10)
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, request)

        # Set the unauthproperty as un-restricted so that the
        # renderAllProperties will render all the properties.
        unauthProperty.restricted = False

        # PROPFIND does catch all exceptions during the main PROPFIND method
        # but instead we need to make sure that the renderSelectedProperties
        # does throw the exception.
        # The current `level' is the last argument to this method.
        response = propf.renderAllProperties(resource, request, None, 1)
        response = response()

        # Note that the unauthprop is not included in the response.
        assertXMLEqualIgnoreOrdering("""<response xmlns="DAV:">
<href>/resource</href>
<propstat>
  <prop>
    <ns1:exampletextprop xmlns:ns1="DAVtest:">some text</ns1:exampletextprop>
    <resourcetype />
    <ns1:exampleintprop xmlns:ns1="DAVtest:">10</ns1:exampleintprop>
  </prop>
  <status>HTTP/1.1 200 Ok</status>
</propstat>
</response>""", response)

        # Since we silenty ignored returning a property. We now log the
        # Unauthorized exception so debuging and logging purposes.
        self.assertEqual(len(self.errUtility.errors), 1)
        exc_info = self.errUtility.errors[0]
        self.assertEqual(isinstance(exc_info[0][1], Unauthorized), True)

    def test_renderAllProperties_unauthorized_included(self):
        # If we request to render all properties, and request to render a
        # property we ain't authorized via the 'include' element then we
        # should get the property back as part of the multistatus response
        # but with a status 401 and no content.
        resource = Resource("some text", 10)
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, request)

        etree = z3c.etree.getEngine()
        includes = etree.fromstring("""<include xmlns="DAV:" xmlns:D="DAVtest:">
<D:unauthprop />
</include>""")

        response = propf.renderAllProperties(resource, request, includes)
        response = response()

        assertXMLEqualIgnoreOrdering("""<response xmlns="DAV:">
<href>/resource</href>
<propstat>
  <prop>
    <ns1:exampletextprop xmlns:ns1="DAVtest:">some text</ns1:exampletextprop>
    <resourcetype />
    <ns1:exampleintprop xmlns:ns1="DAVtest:">10</ns1:exampleintprop>
  </prop>
  <status>HTTP/1.1 200 Ok</status>
</propstat>
<propstat>
  <prop>
    <ns1:unauthprop xmlns:ns1="DAVtest:" />
  </prop>
  <status>HTTP/1.1 401 Unauthorized</status>
</propstat>
</response>""", response)

    def test_renderAllProperties_broken_included(self):
        # If we request to render all properties, and to forse render a
        # broken property via the 'include' element then we should get
        # this property back as part of the multistatus response but with a
        # status 500 and no content.
        resource = Resource("some text", 10)
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, request)

        etree = z3c.etree.getEngine()
        includes = etree.fromstring("""<include xmlns="DAV:" xmlns:D="DAVtest:">
<D:brokenprop />
</include>""")

        response = propf.renderAllProperties(resource, request, includes)
        response = response()

        assertXMLEqualIgnoreOrdering("""<response xmlns="DAV:">
<href>/resource</href>
<propstat>
  <prop>
    <ns1:exampletextprop xmlns:ns1="DAVtest:">some text</ns1:exampletextprop>
    <resourcetype />
    <ns1:exampleintprop xmlns:ns1="DAVtest:">10</ns1:exampleintprop>
  </prop>
  <status>HTTP/1.1 200 Ok</status>
</propstat>
<propstat>
  <prop>
    <ns1:brokenprop xmlns:ns1="DAVtest:" />
  </prop>
  <status>HTTP/1.1 500 Internal Server Error</status>
</propstat>
</response>""", response)

        self.assertEqual(len(self.errUtility.errors), 1)
        exc_info = self.errUtility.errors[0]
        self.assertEqual(isinstance(exc_info[0][1], NotImplementedError), True)


class SecurityChecker(object):
    # Custom security checker to make the recursive propfind method handle
    # authentication errors properly. We use this checker instead of the
    # zope.security.checker.Checker object when we want to raise Unauthorized
    # errors and not Forbidden errors.
    interface.implements(zope.security.interfaces.IChecker)

    def __init__(self, get_permissions = {}):
        self.get_permissions = get_permissions

    def check_getattr(self, ob, name):
        if name in ("__provides__",):
            return
        permission = self.get_permissions.get(name)
        if permission is zope.security.checker.CheckerPublic:
            return
        raise Unauthorized(object, name, permission)

    def check_setattr(self, ob, name):
        raise NotImplementedError("check_setattr(ob, name) not implemented")

    def check(self, ob, operation):
        raise NotImplementedError("check(ob, operation) not implemented")

    def proxy(self, value):
        if type(value) is zope.security.checker.Proxy:
            return value
        checker = getattr(value, '__Security_checker__', None)
        if checker is None:
            checker = zope.security.checker.selectChecker(value)
            if checker is None:
                return value

        return zope.security.checker.Proxy(value, checker)


def readDirectoryNoOp(container):
    return container


class PROPFINDSecurityTestCase(unittest.TestCase):
    # When processing PROPFIND requests with depth `infinity' sometimes we
    # run into problems. These can include users been unauthorized to certain
    # items. This test implements a custom security policy in `SecurityChecker'
    # to test the use case of finding security problems in rendering these
    # requests.
    # This really needs to be a doctest:
    # - test_handlePropfindResource
    # - test_handlePropfind_forbiddenResourceProperty
    # - test_handlePropfind_forbiddenRequestedResourceProperty
    # - test_handlePropfind_unauthorizedRequestedResourceProperty
    # - test_handlePropfind_forbiddenCollection_listing
    # - test_handlePropfind_unauthorizedCollection_listing
    # - test_handlePropfind_forbiddenRootCollection_listing
    # - test_handlePropfind_unauthorizedRootCollection_listing
    # - test_handlePropfindResource_unauthorizedResource

    def setUp(self):
        propfindSetUp()
        # make sure the unauthProperty is restricted has otherwise it will
        # break all the renderAllProperties methods.
        unauthProperty.restricted = True

        component.getGlobalSiteManager().registerAdapter(
            readDirectoryNoOp, (IReadContainer,), provided = IReadDirectory)

        self.errUtility = ErrorReportingUtility()
        component.getGlobalSiteManager().registerUtility(self.errUtility)

        # Collect all the checkers we define so that we can remove them later.
        self.undefine_type_checkers = []

        self.collection = Collection()
        self.collection["r1"] = Resource("some text - r1", 2)
        self.collection["c"] = Collection()
        self.collection["c"]["r2"] = Resource("some text - r2", 4)

    def tearDown(self):
        propfindTearDown()

        component.getGlobalSiteManager().unregisterAdapter(
            readDirectoryNoOp, (IReadContainer,), provided = IReadDirectory)

        component.getGlobalSiteManager().unregisterUtility(self.errUtility)
        del self.errUtility

        for type_ in self.undefine_type_checkers:
            zope.security.checker.undefineChecker(type_)

    def addChecker(self, obj, checker):
        self.undefine_type_checkers.append(obj.__class__)
        zope.security.checker.defineChecker(obj.__class__, checker)
        return zope.security.checker.ProxyFactory(obj)

    def test_handlePropfindResource(self):
        # Just make sure that the custom security checker works by giving
        # access to all the resources and subcollections.
        self.addChecker(
            self.collection["r1"], zope.security.checker.Checker({
                "text": zope.security.checker.CheckerPublic,
                "intprop": zope.security.checker.CheckerPublic}))
        collection = self.addChecker(
            self.collection, zope.security.checker.Checker({
                "values": zope.security.checker.CheckerPublic}))

        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        request.processInputs()
        propf = PROPFIND(collection, request)

        result = propf.PROPFIND()

        self.assertEqual(request.response.getStatus(), 207)
        assertXMLEqualIgnoreOrdering(result, """<D:multistatus xmlns:D="DAV:">
<D:response>
  <D:href>/collection/</D:href>
  <D:propstat>
    <D:prop>
      <D:resourcetype>
        <D:collection />
      </D:resourcetype>
    </D:prop>
    <D:status>HTTP/1.1 200 Ok</D:status>
  </D:propstat>
</D:response>
<D:response>
  <D:href>/collection/c/</D:href>
  <D:propstat>
    <D:prop>
      <D:resourcetype>
        <D:collection />
      </D:resourcetype>
    </D:prop>
    <D:status>HTTP/1.1 200 Ok</D:status>
  </D:propstat>
</D:response>
<D:response>
  <D:href>/collection/c/r2</D:href>
  <D:propstat>
    <D:prop>
      <D1:exampletextprop xmlns:D1="DAVtest:">some text - r2</D1:exampletextprop>
      <D:resourcetype />
      <D1:exampleintprop xmlns:D1="DAVtest:">4</D1:exampleintprop>
    </D:prop>
    <D:status>HTTP/1.1 200 Ok</D:status>
  </D:propstat>
</D:response>
<D:response>
  <D:href>/collection/r1</D:href>
  <D:propstat>
    <D:prop>
      <D1:exampletextprop xmlns:D1="DAVtest:">some text - r1</D1:exampletextprop>
      <D:resourcetype />
      <D1:exampleintprop xmlns:D1="DAVtest:">2</D1:exampleintprop>
    </D:prop>
    <D:status>HTTP/1.1 200 Ok</D:status>
  </D:propstat>
</D:response></D:multistatus>
        """)

        self.assertEqual(len(self.errUtility.errors), 0)

    def test_handlePropfind_forbiddenResourceProperty(self):
        # Remove access to the `exampleintprop' on the collection['r1']
        # resource. Since this not the requested resource we render the
        # error and include it in the `{DAV:}response' for the corresponding
        # resource but with no value and a `403' status.
        self.collection.data["r1"] = zope.security.checker.ProxyFactory(
            self.collection["r1"], zope.security.checker.Checker({
                "text": zope.security.checker.CheckerPublic}))
        self.addChecker(
            self.collection["c"]["r2"], zope.security.checker.Checker({
                "text": zope.security.checker.CheckerPublic,
                "intprop": zope.security.checker.CheckerPublic}))
        collection = self.addChecker(
            self.collection, zope.security.checker.Checker({
                "values": zope.security.checker.CheckerPublic}))

        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        request.processInputs()
        propf = PROPFIND(collection, request)

        result = propf.PROPFIND()

        self.assertEqual(request.response.getStatus(), 207)
        assertXMLEqualIgnoreOrdering(result, """<D:multistatus xmlns:D="DAV:">
<D:response>
  <D:href>/collection/</D:href>
  <D:propstat>
    <D:prop>
      <D:resourcetype>
        <D:collection />
      </D:resourcetype>
    </D:prop>
    <D:status>HTTP/1.1 200 Ok</D:status>
  </D:propstat>
</D:response>
<D:response>
  <D:href>/collection/c/</D:href>
  <D:propstat>
    <D:prop>
      <D:resourcetype>
        <D:collection />
      </D:resourcetype>
    </D:prop>
    <D:status>HTTP/1.1 200 Ok</D:status>
  </D:propstat>
</D:response>
<D:response>
  <D:href>/collection/c/r2</D:href>
  <D:propstat>
    <D:prop>
      <D1:exampletextprop xmlns:D1="DAVtest:">some text - r2</D1:exampletextprop>
      <D:resourcetype />
      <D1:exampleintprop xmlns:D1="DAVtest:">4</D1:exampleintprop>
    </D:prop>
    <D:status>HTTP/1.1 200 Ok</D:status>
  </D:propstat>
</D:response>
<D:response>
  <D:href>/collection/r1</D:href>
  <D:propstat>
    <D:prop>
      <D1:exampletextprop xmlns:D1="DAVtest:">some text - r1</D1:exampletextprop>
      <D:resourcetype />
    </D:prop>
    <D:status>HTTP/1.1 200 Ok</D:status>
  </D:propstat>
  <D:propstat>
    <D:prop>
      <D1:exampleintprop xmlns:D1="DAVtest:" />
    </D:prop>
    <D:status>HTTP/1.1 403 Forbidden</D:status>
  </D:propstat>
</D:response></D:multistatus>
        """)

        # Note that the `{DAVtest:}exampleintprop' was not rendered because
        # we didn't give access to this property is our dummy security proxy.
        self.assertEqual(len(self.errUtility.errors), 1)
        self.assert_(
            isinstance(self.errUtility.errors[0][0][1],
                       zope.security.interfaces.Forbidden),
            "We didn't raise an `Forbidden' error.")

    def test_handlePropfind_forbiddenRequestedResourceProperty(self):
        # Remove access to the `exampleintprop' on the collection['r1']
        # resource and render this resource as the requested resource. But
        # since we get a forbidden error we render all the properties but the
        # `exampleintprop' is still rendered with no value and a `403' status.
        self.collection.data["r1"] = zope.security.checker.ProxyFactory(
            self.collection["r1"], zope.security.checker.Checker({
                "text": zope.security.checker.CheckerPublic}))

        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        request.processInputs()
        propf = PROPFIND(self.collection["r1"], request)

        result = propf.PROPFIND()

        self.assertEqual(request.response.getStatus(), 207)
        assertXMLEqualIgnoreOrdering(result, """<D:multistatus xmlns:D="DAV:">
<D:response>
  <D:href>/collection/r1</D:href>
  <D:propstat>
    <D:prop>
      <D1:exampletextprop xmlns:D1="DAVtest:">some text - r1</D1:exampletextprop>
      <D:resourcetype />
    </D:prop>
    <D:status>HTTP/1.1 200 Ok</D:status>
  </D:propstat>
  <D:propstat>
    <D:prop>
      <D1:exampleintprop xmlns:D1="DAVtest:" />
    </D:prop>
    <D:status>HTTP/1.1 403 Forbidden</D:status>
  </D:propstat>
</D:response></D:multistatus>
        """)

        # Note that the `{DAVtest:}exampleintprop' was not rendered because
        # we didn't give access to this property is our dummy security proxy.
        self.assertEqual(len(self.errUtility.errors), 1)
        self.assert_(
            isinstance(self.errUtility.errors[0][0][1],
                       zope.security.interfaces.Forbidden),
            "We didn't raise an `Forbidden' error.")

    def test_handlePropfind_unauthorizedRequestedResourceProperty(self):
        # Remove access to the `exampleintprop' on the collection['r1']
        # resource and render this resource as the requested resource. Since
        # we requested to render all properties we silently ignore the
        # `exampleintprop' property. But we still log this error.
        self.collection.data["r1"] = zope.security.checker.ProxyFactory(
            self.collection["r1"], SecurityChecker({
                "__name__": zope.security.checker.CheckerPublic,
                "__parent__": zope.security.checker.CheckerPublic,
                "text": zope.security.checker.CheckerPublic,
                "__providedBy__": zope.security.checker.CheckerPublic,
                }))

        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        request.processInputs()
        propf = PROPFIND(self.collection["r1"], request)

        result = propf.PROPFIND()

        self.assertEqual(request.response.getStatus(), 207)
        assertXMLEqualIgnoreOrdering(result, """<D:multistatus xmlns:D="DAV:">
<D:response>
  <D:href>/collection/r1</D:href>
  <D:propstat>
    <D:prop>
      <D1:exampletextprop xmlns:D1="DAVtest:">some text - r1</D1:exampletextprop>
      <D:resourcetype />
    </D:prop>
    <D:status>HTTP/1.1 200 Ok</D:status>
  </D:propstat>
</D:response></D:multistatus>
        """)

        # Note that the `{DAVtest:}exampleintprop' was not rendered because
        # we didn't give access to this property is our dummy security proxy.
        self.assertEqual(len(self.errUtility.errors), 1)
        self.assert_(
            isinstance(self.errUtility.errors[0][0][1],
                       zope.security.interfaces.Unauthorized),
            "We didn't raise an `Unauthorized' error.")

    def test_handlePropfind_forbiddenCollection_listing(self):
        # Remove permission to the collections `values' method. We get a
        # `Forbidden' exception in this case. Since this folder isn't the
        # request resource but a sub-resource of it we ignore the folder
        # listing on this folder so that users can continue managing the
        # content the content they do have access to but we still render
        # the properties of this folder since we do have access to it.
        self.collection.data["c"] = zope.security.checker.ProxyFactory(
            self.collection["c"], zope.security.checker.Checker({}))
        self.addChecker(self.collection["r1"], zope.security.checker.Checker({
            "text": zope.security.checker.CheckerPublic,
            "intprop": zope.security.checker.CheckerPublic}))
        collection = self.addChecker(
            self.collection, zope.security.checker.Checker({
                "values": zope.security.checker.CheckerPublic}))

        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        request.processInputs()
        propf = PROPFIND(collection, request)

        result = propf.PROPFIND()

        self.assertEqual(request.response.getStatus(), 207)
        assertXMLEqualIgnoreOrdering(result, """<D:multistatus xmlns:D="DAV:">
<D:response>
  <D:href>/collection/</D:href>
  <D:propstat>
    <D:prop>
      <D:resourcetype>
        <D:collection />
      </D:resourcetype>
    </D:prop>
    <D:status>HTTP/1.1 200 Ok</D:status>
  </D:propstat>
</D:response>
<D:response>
  <D:href>/collection/c/</D:href>
  <D:propstat>
    <D:prop>
      <D:resourcetype>
        <D:collection />
      </D:resourcetype>
    </D:prop>
    <D:status>HTTP/1.1 200 Ok</D:status>
  </D:propstat>
</D:response>
<D:response>
  <D:href>/collection/r1</D:href>
  <D:propstat>
    <D:prop>
      <D1:exampletextprop xmlns:D1="DAVtest:">some text - r1</D1:exampletextprop>
      <D:resourcetype />
      <D1:exampleintprop xmlns:D1="DAVtest:">2</D1:exampleintprop>
    </D:prop>
    <D:status>HTTP/1.1 200 Ok</D:status>
  </D:propstat>
</D:response></D:multistatus>
        """)

        self.assertEqual(len(self.errUtility.errors), 1)
        self.assert_(
            isinstance(self.errUtility.errors[0][0][1],
                       zope.security.interfaces.Forbidden),
            "We didn't raise an `Forbidden' error.")

    def test_handlePropfind_unauthorizedCollection_listing(self):
        # Remove permission to the collections `values' method for the `c'
        # resource. In this case the user isn't presented with a 401 error
        # but instead we ignore the the listing of this folder and return
        # the information on the rest of the documents. The reason is that
        # the user mightnot have access to this folder so we shouldn't
        # interfere with there access to the folder. This only applies to a
        # PROPFIND request with depth equal to `0' or `infinity'.
        self.collection.data["c"] = zope.security.checker.ProxyFactory(
            self.collection["c"], SecurityChecker({
                "__name__": zope.security.checker.CheckerPublic,
                "__parent__": zope.security.checker.CheckerPublic,
                "__providedBy__": zope.security.checker.CheckerPublic,
            }))
        self.addChecker(self.collection["r1"], zope.security.checker.Checker({
            "text": zope.security.checker.CheckerPublic,
            "intprop": zope.security.checker.CheckerPublic}))
        collection = self.addChecker(
            self.collection, zope.security.checker.Checker({
                "values": zope.security.checker.CheckerPublic}))

        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        request.processInputs()
        propf = PROPFIND(collection, request)

        result = propf.PROPFIND()

        self.assertEqual(request.response.getStatus(), 207)
        assertXMLEqualIgnoreOrdering(result, """<D:multistatus xmlns:D="DAV:">
<D:response>
  <D:href>/collection/</D:href>
  <D:propstat>
    <D:prop>
      <D:resourcetype>
        <D:collection />
      </D:resourcetype>
    </D:prop>
    <D:status>HTTP/1.1 200 Ok</D:status>
  </D:propstat>
</D:response>
<D:response>
  <D:href>/collection/c/</D:href>
  <D:propstat>
    <D:prop>
      <D:resourcetype>
        <D:collection />
      </D:resourcetype>
    </D:prop>
    <D:status>HTTP/1.1 200 Ok</D:status>
  </D:propstat>
</D:response>
<D:response>
  <D:href>/collection/r1</D:href>
  <D:propstat>
    <D:prop>
      <D1:exampletextprop xmlns:D1="DAVtest:">some text - r1</D1:exampletextprop>
      <D:resourcetype />
      <D1:exampleintprop xmlns:D1="DAVtest:">2</D1:exampleintprop>
    </D:prop>
    <D:status>HTTP/1.1 200 Ok</D:status>
  </D:propstat>
</D:response></D:multistatus>
        """)

        # Make sure that we handled the excepted failure.
        self.assertEqual(len(self.errUtility.errors), 1)
        self.assert_(
            isinstance(self.errUtility.errors[0][0][1],
                       zope.security.interfaces.Unauthorized),
            "We didn't raise an `Unauthorized' error.")

    def test_handlePropfind_forbiddenRootCollection_listing(self):
        # Remove permission to the root collections `values' method. This
        # raises an Forbidden exception - not sure why not an Unauthorized
        # exception. In this case we just return the properties of the
        # resource - since the user can't list the folder and might not have
        # the permissions to do so.
        # XXX - this seems correct but ...
        self.addChecker(self.collection["r1"], zope.security.checker.Checker({
            "text": zope.security.checker.CheckerPublic,
            "intprop": zope.security.checker.CheckerPublic}))
        collection = self.addChecker(
            self.collection, zope.security.checker.Checker({}))

        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        request.processInputs()
        propf = PROPFIND(collection, request)

        result = propf.PROPFIND()

        self.assertEqual(request.response.getStatus(), 207)
        assertXMLEqualIgnoreOrdering(result, """<D:multistatus xmlns:D="DAV:">
<D:response>
  <D:href>/collection/</D:href>
  <D:propstat>
    <D:prop>
      <D:resourcetype>
        <D:collection />
      </D:resourcetype>
    </D:prop>
    <D:status>HTTP/1.1 200 Ok</D:status>
  </D:propstat>
</D:response></D:multistatus>
        """)

        self.assertEqual(len(self.errUtility.errors), 1)
        self.assert_(
            isinstance(self.errUtility.errors[0][0][1],
                       zope.security.interfaces.Forbidden),
            "We didn't raise an `Forbidden' error.")

    def test_handlePropfind_unauthorizedRootCollection_listing(self):
        # Remove permission to the root collections `values' method. This
        # raises an Unauthorized exception. In this case we just return the
        # properties of the resource - since the user can't list the folder
        # and might not have the permissions to do so. Even though we could
        # have just rendered the properties on this folder.
        self.addChecker(self.collection["r1"], zope.security.checker.Checker({
            "text": zope.security.checker.CheckerPublic,
            "intprop": zope.security.checker.CheckerPublic}))
        collection = zope.security.checker.ProxyFactory(
            self.collection, SecurityChecker({
                "__name__": zope.security.checker.CheckerPublic,
                "__parent__": zope.security.checker.CheckerPublic,
                "__providedBy__": zope.security.checker.CheckerPublic,
            }))

        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        request.processInputs()
        propf = PROPFIND(collection, request)

        self.assertRaises(zope.security.interfaces.Unauthorized, propf.PROPFIND)

        # Since we raise the `Unauthorized' exception the publisher will
        # automatically log this exception when we handle the exception.
        self.assertEqual(len(self.errUtility.errors), 0)

    def test_handlePropfindResource_unauthorizedResource(self):
        # This is an edge case. By removing access to the `__name__' and
        # `__parent__' attributes on the `collection["r1"]' resource we
        # can no longer generate a URL for this resource and get an
        # Unauthorized exception. Can't do much about this but it doesn't
        # really come up.
        self.collection.data["r1"] = zope.security.checker.ProxyFactory(
            self.collection["r1"], SecurityChecker({
                "__name__": 1, # disable access to the `__name__' attribute
                "__parent__": 1,
                "text": zope.security.checker.CheckerPublic,
                "intprop": zope.security.checker.CheckerPublic,
                "__providedBy__": zope.security.checker.CheckerPublic,
                }))
        self.addChecker(
            self.collection["c"]["r2"], zope.security.checker.Checker({
                "text": zope.security.checker.CheckerPublic,
                "intprop": zope.security.checker.CheckerPublic,
                "__providedBy__": zope.security.checker.CheckerPublic,
                }))
        collection = self.addChecker(
            self.collection, zope.security.checker.Checker({
                "values": zope.security.checker.CheckerPublic,
                "__providedBy__": zope.security.checker.CheckerPublic,
                }))

        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        request.processInputs()
        propf = PROPFIND(collection, request)

        self.assertRaises(
            zope.security.interfaces.Unauthorized, propf.PROPFIND)

        self.assertEqual(len(self.errUtility.errors), 0)


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(PROPFINDBodyTestCase),
        unittest.makeSuite(PROPFINDTestRender),
        unittest.makeSuite(PROPFINDSecurityTestCase),
        ))
