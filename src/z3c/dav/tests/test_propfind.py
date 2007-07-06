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

import z3c.dav.properties
import z3c.dav.publisher
import z3c.dav.widgets
import z3c.dav.exceptions
import z3c.dav.coreproperties
from z3c.dav.propfind import PROPFIND
from z3c.etree.testing import etreeSetup, etreeTearDown, assertXMLEqual
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

        assertXMLEqual(response, """<D:response xmlns:D="DAV:">
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

        assertXMLEqual(response(), """<D:response xmlns:D="DAV:">
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
        assertXMLEqual(response(),
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

        assertXMLEqual(response(), """<D:response xmlns:D="DAV:">
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

        assertXMLEqual(response(), """<D:response xmlns:D="DAV:">
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

        assertXMLEqual(response(), """<D:response xmlns:D="DAV:">
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

        assertXMLEqual(response(), """<D:response xmlns:D="DAV:">
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

        assertXMLEqual(response(), """<D:response xmlns:D="DAV:">
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

        assertXMLEqual("""<response xmlns="DAV:">
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

    def test_render_selected_unauthorizedProperty(self):
        resource = Resource("some text", 10)
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        propf = PROPFIND(None, None)

        etree = z3c.etree.getEngine()
        props = etree.fromstring("""<prop xmlns="DAV:" xmlns:D="DAVtest:">
<D:unauthprop />
<D:exampletextprop />
</prop>""")

        response = propf.renderSelectedProperties(resource, request, props)
        response = response()

        # The PROPFIND method should return a 401 when the user is unauthorized
        # to view a property.
        assertXMLEqual("""<response xmlns="DAV:">
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

    def test_renderAllProperties_unauthorized(self):
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
        assertXMLEqual("""<response xmlns="DAV:">
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

        assertXMLEqual("""<response xmlns="DAV:">
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

        assertXMLEqual("""<response xmlns="DAV:">
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
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        request.processInputs()
        propf = PROPFIND(collection, request)

        result = propf.PROPFIND()
        etree = z3c.etree.getEngine()
        etree.fromstring(result)

        assertXMLEqual(result, """<D:multistatus xmlns:D="DAV:">
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


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(PROPFINDBodyTestCase),
        unittest.makeSuite(PROPFINDTestRender),
        unittest.makeSuite(PROPFINDRecuseTest),
        ))
