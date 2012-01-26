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
"""Test WebDAV proppatch method.

It is easier to do this has a unit test has we have complete control over
what properties are defined or not.
"""

import unittest
from cStringIO import StringIO
from xml.etree import ElementTree

from zope import event
from zope import interface
from zope import component
from zope import schema
import zope.schema.interfaces
from zope.traversing.browser.interfaces import IAbsoluteURL
from zope.security.interfaces import Unauthorized
from zope.lifecycleevent.interfaces import IObjectModifiedEvent, \
     ISequence, IAttributes
import zope.lifecycleevent

import z3c.dav.coreproperties
import z3c.dav.proppatch
import z3c.dav.publisher
import z3c.dav.interfaces

from z3c.etree.testing import etreeSetup, etreeTearDown, assertXMLEqual

class TestRequest(z3c.dav.publisher.WebDAVRequest):

    def __init__(self, set_properties = None, remove_properties = None,
                 environ = {}, content_type = "text/xml"):
        set_body = ""
        if set_properties is not None:
            set_body = "<set><prop>%s</prop></set>" % set_properties

        remove_body = ""
        if remove_properties is not None:
            remove_body = "<remove><prop>%s</prop></remove>" % remove_properties

        body = """<?xml version="1.0" encoding="utf-8" ?>
<D:propertyupdate xmlns:D="DAV:" xmlns="DAV:">
  %s %s
</D:propertyupdate>
        """ %(set_body, remove_body)
        body = body.encode("utf-8")

        env = environ.copy()
        env.setdefault("REQUEST_METHOD", "PROPPATCH")
        env.setdefault("CONTENT_TYPE", content_type)
        env.setdefault("CONTENT_LENGTH", len(body))

        super(TestRequest, self).__init__(StringIO(body), env)

        # call processInputs now since we are in a unit test.
        self.processInputs()


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
        else:
            raise ValueError("unknown context type")

        return path

    __call__ = __str__


class PROPPATCHHandler(z3c.dav.proppatch.PROPPATCH):

    def __init__(self, context, request):
        super(PROPPATCHHandler, self).__init__(context, request)

        self.setprops = []
        self.removeprops = []

    def handleSet(self, prop):
        self.setprops.append(prop.tag)
        # The unit tests have no idea where the property lives.
        return [zope.lifecycleevent.Attributes(interface.Interface)]

    def handleRemove(self, prop):
        self.removeprops.append(prop.tag)
        # The unit tests have no idea where the property lives.
        return [zope.lifecycleevent.Attributes(interface.Interface)]


class PROPPATCHXmlParsing(unittest.TestCase):

    def setUp(self):
        etreeSetup(key = "py25")

        gsm = component.getGlobalSiteManager()

        gsm.registerAdapter(DummyResourceURL,
                            (IResource, z3c.dav.interfaces.IWebDAVRequest))

    def tearDown(self):
        etreeTearDown()

        gsm = component.getGlobalSiteManager()

        gsm.unregisterAdapter(DummyResourceURL,
                              (IResource,
                               z3c.dav.interfaces.IWebDAVRequest))

    def test_noxml(self):
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        request.processInputs()
        propp = PROPPATCHHandler(Resource(), request)
        self.assertRaises(z3c.dav.interfaces.BadRequest, propp.PROPPATCH)

    def test_nodata_but_xmlcontenttype(self):
        request = z3c.dav.publisher.WebDAVRequest(
            StringIO(""), {"CONTENT_TYPE": "application/xml"})
        request.processInputs()
        propp = PROPPATCHHandler(Resource(), request)
        self.assertRaises(z3c.dav.interfaces.BadRequest, propp.PROPPATCH)

    def test_notxml(self):
        request = z3c.dav.publisher.WebDAVRequest(
            StringIO("content"), {"CONTENT_TYPE": "text/plain",
                                  "CONTENT_LENGTH": 7})
        propp = PROPPATCHHandler(Resource(), request)
        request.processInputs()
        self.assertRaises(z3c.dav.interfaces.BadRequest, propp.PROPPATCH)

    def test_notproppatch(self):
        body = """<?xml version="1.0" encoding="utf-8" ?>
<D:notpropertyupdate xmlns:D="DAV:" xmlns="DAV:">
  Not a propertyupdate element.
</D:notpropertyupdate>
        """

        request = z3c.dav.publisher.WebDAVRequest(
            StringIO(body), {"CONTENT_TYPE": "text/xml",
                             "CONTENT_LENGTH": len(body)})
        request.processInputs()

        propp = PROPPATCHHandler(Resource(), request)
        self.assertRaises(
            z3c.dav.interfaces.UnprocessableError,
            propp.PROPPATCH)

    def test_not_set_element(self):
        body = """<?xml version="1.0" encoding="utf-8" ?>
<propertyupdate xmlns:D="DAV:" xmlns="DAV:">
  <notset><prop><displayname>Display name</displayname></prop></notset>
</propertyupdate>
        """

        request = z3c.dav.publisher.WebDAVRequest(
            StringIO(body), {"CONTENT_TYPE": "text/xml",
                             "CONTENT_LENGTH": len(body)})
        request.processInputs()

        propp = PROPPATCHHandler(Resource(), request)
        propp.PROPPATCH()

        self.assertEqual(propp.setprops, [])
        self.assertEqual(propp.removeprops, [])

    def test_not_prop_element(self):
        body = """<?xml version="1.0" encoding="utf-8" ?>
<propertyupdate xmlns:D="DAV:" xmlns="DAV:">
  <set><notprop><displayname>Display name</displayname></notprop></set>
</propertyupdate>
        """

        request = z3c.dav.publisher.WebDAVRequest(
            StringIO(body), {"CONTENT_TYPE": "text/xml",
                             "CONTENT_LENGTH": len(body)})
        request.processInputs()

        propp = PROPPATCHHandler(Resource(), request)
        propp.PROPPATCH()

        self.assertEqual(propp.setprops, [])
        self.assertEqual(propp.removeprops, [])

    def test_not_remove_element(self):
        body = """<?xml version="1.0" encoding="utf-8" ?>
<propertyupdate xmlns:D="DAV:" xmlns="DAV:">
  <notremove><prop><displayname>Display name</displayname></prop></notremove>
</propertyupdate>
        """

        request = z3c.dav.publisher.WebDAVRequest(
            StringIO(body), {"CONTENT_TYPE": "text/xml",
                             "CONTENT_LENGTH": len(body)})
        request.processInputs()

        propp = PROPPATCHHandler(Resource(), request)
        propp.PROPPATCH()

        self.assertEqual(propp.setprops, [])
        self.assertEqual(propp.removeprops, [])

    def test_set_none_prop(self):
        request = TestRequest()
        propp = PROPPATCHHandler(Resource(), request)
        propp.PROPPATCH()

        self.assertEqual(propp.setprops, [])
        self.assertEqual(propp.removeprops, [])

    def test_invalid_namespace_prop(self):
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        # Manually set up the xmlDataSource as some  etree `parse` method
        # raise a syntax error with the prop element with an empty namespace
        # which we are trying to test
        request.content_type = "application/xml"
        request.xmlDataSource = ElementTree.fromstring("""<?xml version="1.0" encoding="utf-8" ?>
<D:propertyupdate xmlns:D="DAV:" xmlns="DAV:">
  <set>
    <prop>
    </prop>
  </set>
</D:propertyupdate>""")
        prop = ElementTree.Element("{}bar")
        prop.tag = "{}bar"
        request.xmlDataSource[0][0].append(prop)
        propp = PROPPATCHHandler(Resource(), request)

        self.assertRaises(z3c.dav.interfaces.BadRequest,
                          propp.PROPPATCH)

    def test_none_namespace_prop(self):
        request = z3c.dav.publisher.WebDAVRequest(StringIO(""), {})
        # Manually set up the xmlDataSource as some  etree `parse` method
        # raise a syntax error with the prop element with an empty namespace
        # which we are trying to test
        request.content_type = "application/xml"
        request.xmlDataSource = ElementTree.fromstring("""<?xml version="1.0" encoding="utf-8" ?>
<D:propertyupdate xmlns:D="DAV:" xmlns="DAV:">
  <set>
    <prop>
    </prop>
  </set>
</D:propertyupdate>""")
        prop = ElementTree.Element("bar")
        prop.tag = "bar"
        request.xmlDataSource[0][0].append(prop)
        propp = PROPPATCHHandler(Resource(), request)
        propp.PROPPATCH()

        self.assertEqual(propp.setprops, ["bar"])
        self.assertEqual(propp.removeprops, [])

    def test_set_propnullns(self):
        # test litmus #15
        body = """<?xml version="1.0" encoding="utf-8" ?><propertyupdate xmlns="DAV:"><set><prop><nonamespace xmlns="">randomvalue</nonamespace></prop></set></propertyupdate>"""
        env = {
            "REQUEST_METHOD": "PROPPATCH",
            "CONTENT_TYPE": "",
            "CONTENT_LENGTH": len(body)
            }
        request = z3c.dav.publisher.WebDAVRequest(StringIO(body), env)
        request.processInputs()

        propp = PROPPATCHHandler(Resource(), request)
        propp.PROPPATCH()    

    def test_set_one_prop(self):
        request = TestRequest(
            set_properties = "<displayname>Display name</displayname>")
        propp = PROPPATCHHandler(Resource(), request)
        propp.PROPPATCH()

        self.assertEqual(propp.setprops, ["{DAV:}displayname"])
        self.assertEqual(propp.removeprops, [])

    def test_remove_one_prop(self):
        request = TestRequest(
            remove_properties = "<displayname>Display name</displayname>")
        propp = PROPPATCHHandler(Resource(), request)
        propp.PROPPATCH()

        self.assertEqual(propp.setprops, [])
        self.assertEqual(propp.removeprops, ["{DAV:}displayname"])

    def test_multiset(self):
        request = TestRequest(
            set_properties = "<displayname>Display name</displayname><getcontenttype>text/plain</getcontenttype>")
        propp = PROPPATCHHandler(Resource(), request)
        propp.PROPPATCH()

        self.assertEqual(propp.setprops, ["{DAV:}displayname",
                                          "{DAV:}getcontenttype"])
        self.assertEqual(propp.removeprops, [])

    def test_multiremove(self):
        request = TestRequest(
            remove_properties = "<displayname>Display name</displayname><getcontenttype>text/plain</getcontenttype>")
        propp = PROPPATCHHandler(Resource(), request)
        propp.PROPPATCH()

        self.assertEqual(propp.setprops, [])
        self.assertEqual(propp.removeprops, ["{DAV:}displayname",
                                             "{DAV:}getcontenttype"])

    def test_set_remove_prop(self):
        request = TestRequest(
            remove_properties = "<displayname>Display name</displayname>",
            set_properties = "<getcontenttype>text/plain</getcontenttype>")
        propp = PROPPATCHHandler(Resource(), request)
        propp.PROPPATCH()

        self.assertEqual(propp.setprops, ["{DAV:}getcontenttype"])
        self.assertEqual(propp.removeprops, ["{DAV:}displayname"])

    def test_error_set_prop(self):
        class PROPPATCHHandlerError(PROPPATCHHandler):
            def handleSet(self, prop):
                raise z3c.dav.interfaces.PropertyNotFound(
                    self.context, "getcontenttype", u"property is missing")

        request = TestRequest(
            set_properties = "<getcontenttype>text/plain</getcontenttype>")
        propp = PROPPATCHHandlerError(Resource(), request)
        self.assertRaises(z3c.dav.interfaces.WebDAVPropstatErrors,
                          propp.PROPPATCH)

        self.assertEqual(propp.setprops, [])
        self.assertEqual(propp.removeprops, [])

    def test_error_set_prop_with_remove(self):
        class PROPPATCHHandlerError(PROPPATCHHandler):
            def handleSet(self, prop):
                raise z3c.dav.interfaces.PropertyNotFound(
                    self.context, "getcontenttype", u"property is missing")

        request = TestRequest(
            remove_properties = "<displayname>Test Name</displayname>",
            set_properties = "<getcontenttype>text/plain</getcontenttype>")
        propp = PROPPATCHHandlerError(Resource(), request)
        self.assertRaises(z3c.dav.interfaces.WebDAVPropstatErrors,
                          propp.PROPPATCH)

        self.assertEqual(propp.setprops, [])
        self.assertEqual(propp.removeprops, ['{DAV:}displayname'])

    def test_response(self):
        request = TestRequest(
            remove_properties = "<displayname>Display name</displayname>",
            set_properties = "<getcontenttype>text/plain</getcontenttype>")
        propp = PROPPATCHHandler(Resource(), request)
        result = propp.PROPPATCH()

        assertXMLEqual(result, """<multistatus xmlns="DAV:">
<response>
  <href>/resource</href>
  <propstat>
    <prop>
      <getcontenttype />
      <displayname />
    </prop>
    <status>HTTP/1.1 200 Ok</status>
  </propstat>
</response></multistatus>""")


class IExamplePropertyStorage(interface.Interface):

    exampleintprop = schema.Int(
        title = u"Example Integer Property")

    exampletextprop = schema.Text(
        title = u"Example Text Property")

class IUnauthorizedPropertyStorage(interface.Interface):

    unauthprop = schema.TextLine(
        title = u"Property that you are not allowed to set")

exampleIntProperty = z3c.dav.properties.DAVProperty(
    "{DAVtest:}exampleintprop", IExamplePropertyStorage)
exampleTextProperty = z3c.dav.properties.DAVProperty(
    "{DAVtest:}exampletextprop", IExamplePropertyStorage)
unauthProperty = z3c.dav.properties.DAVProperty(
    "{DAVtest:}unauthprop", IUnauthorizedPropertyStorage)
unauthProperty.restricted = True


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


class UnauthorizedPropertyStorage(object):
    interface.implements(IUnauthorizedPropertyStorage)

    def __init__(self, context, request):
        pass

    @apply
    def unauthprop():
        def get(self):
            raise Unauthorized("You are not allowed to read this property")
        def set(self, value):
            raise Unauthorized("You are not allowed to set this property!")
        return property(get, set)


class PROPPATCHHandlePropertyModification(unittest.TestCase):

    def eventLog(self, event):
        self.events.append(event)

    def setUp(self):
        etreeSetup(key = "py25")

        gsm = component.getGlobalSiteManager()

        gsm.registerUtility(exampleIntProperty,
                            name = "{DAVtest:}exampleintprop",
                            provided = z3c.dav.interfaces.IDAVProperty)
        gsm.registerUtility(exampleTextProperty,
                            name = "{DAVtest:}exampletextprop",
                            provided = z3c.dav.interfaces.IDAVProperty)
        exampleTextProperty.field.readonly = False
        gsm.registerUtility(unauthProperty, name = "{DAVtest:}unauthprop")

        gsm.registerAdapter(ExamplePropertyStorage,
                            (IResource, z3c.dav.interfaces.IWebDAVRequest),
                            provided = IExamplePropertyStorage)
        gsm.registerAdapter(UnauthorizedPropertyStorage,
                            (IResource, z3c.dav.interfaces.IWebDAVRequest),
                            provided = IUnauthorizedPropertyStorage)

        gsm.registerAdapter(z3c.dav.widgets.IntDAVInputWidget,
                            (zope.schema.interfaces.IInt,
                             z3c.dav.interfaces.IWebDAVRequest))
        gsm.registerAdapter(z3c.dav.widgets.TextDAVInputWidget,
                            (zope.schema.interfaces.IText,
                             z3c.dav.interfaces.IWebDAVRequest))

        gsm.registerAdapter(DummyResourceURL,
                            (IResource, z3c.dav.interfaces.IWebDAVRequest))

        # PROPPATCH and the resourcetype properties highlighted a bug
        gsm.registerUtility(z3c.dav.coreproperties.resourcetype,
                            name = "{DAV:}resourcetype")
        gsm.registerAdapter(z3c.dav.coreproperties.ResourceTypeAdapter)

        self.events = []
        zope.event.subscribers.append(self.eventLog)

    def tearDown(self):
        etreeTearDown()

        gsm = component.getGlobalSiteManager()

        gsm.unregisterUtility(exampleIntProperty,
                              name = "{DAVtest:}exampleintprop",
                              provided = z3c.dav.interfaces.IDAVProperty)
        gsm.unregisterUtility(exampleTextProperty,
                              name = "{DAVtest:}exampletextprop",
                              provided = z3c.dav.interfaces.IDAVProperty)
        gsm.unregisterUtility(unauthProperty, name = "{DAVtest:}unauthprop")

        gsm.unregisterAdapter(ExamplePropertyStorage,
                              (IResource,
                               z3c.dav.interfaces.IWebDAVRequest),
                              provided = IExamplePropertyStorage)
        gsm.unregisterAdapter(UnauthorizedPropertyStorage,
                              (IResource,
                               z3c.dav.interfaces.IWebDAVRequest),
                              provided = IUnauthorizedPropertyStorage)

        gsm.unregisterAdapter(z3c.dav.widgets.IntDAVInputWidget,
                              (zope.schema.interfaces.IInt,
                               z3c.dav.interfaces.IWebDAVRequest))
        gsm.unregisterAdapter(z3c.dav.widgets.TextDAVInputWidget,
                              (zope.schema.interfaces.IText,
                               z3c.dav.interfaces.IWebDAVRequest))

        gsm.unregisterAdapter(DummyResourceURL,
                              (IResource,
                               z3c.dav.interfaces.IWebDAVRequest))

        gsm.unregisterUtility(z3c.dav.coreproperties.resourcetype,
                              name = "{DAV:}resourcetype")
        gsm.unregisterAdapter(z3c.dav.coreproperties.ResourceTypeAdapter)

        self.events = []
        zope.event.subscribers.remove(self.eventLog)

    def test_handleSetProperty(self):
        propel = ElementTree.Element("{DAVtest:}exampletextprop")
        propel.text = "Example Text Prop"

        request = TestRequest(
            set_properties = """<Dt:exampletextprop xmlns:Dt="DAVtest:">Example Text Prop</Dt:exampletextprop>""")
        resource = Resource("Text Prop", 10)

        propp = z3c.dav.proppatch.PROPPATCH(resource, request)

        propset = propp.handleSet(propel)
        self.assertEqual(len(propset), 1)
        self.assertEqual(IAttributes.providedBy(propset[0]), True)
        self.assertEqual(propset[0].interface, IExamplePropertyStorage)
        self.assertEqual(propset[0].attributes, ("exampletextprop",))

        self.assertEqual(resource.text, "Example Text Prop")

    def test_handleSetProperty_samevalue(self):
        propel = ElementTree.Element("{DAVtest:}exampletextprop")
        propel.text = "Text Prop"

        request = TestRequest(
            set_properties = """<Dt:exampletextprop xmlns:Dt="DAVtest:">Text Prop</Dt:exampletextprop>""")
        resource = Resource("Text Prop", 10)

        propp = z3c.dav.proppatch.PROPPATCH(resource, request)
        self.assertEqual(propp.handleSet(propel), [])
        self.assertEqual(resource.text, "Text Prop")

    def test_handleSet_forbidden_property(self):
        propel = ElementTree.Element("{DAVtest:}exampletextprop")
        propel.text = "Example Text Prop"

        exampleTextProperty.field.readonly = True

        request = TestRequest(
            set_properties = """<Dt:exampletextprop xmlns:Dt="DAVtest:">Example Text Prop</Dt:exampletextprop>""")
        resource = Resource("Text Prop", 10)

        propp = z3c.dav.proppatch.PROPPATCH(resource, request)
        self.assertRaises(z3c.dav.interfaces.ForbiddenError,
                          propp.handleSet,
                          propel)

    def test_handleSet_unauthorized(self):
        propel = ElementTree.Element("{DAVtest:}unauthprop")
        propel.text = "Example Text Prop"

        request = TestRequest(
            set_properties = """<Dt:unauthprop xmlns:Dt="DAVtest:">Example Text Prop</Dt:unauthprop>""")
        resource = Resource("Text Prop", 10)

        propp = z3c.dav.proppatch.PROPPATCH(resource, request)
        self.assertRaises(Unauthorized, propp.handleSet, propel)

    def test_handleSet_property_notfound(self):
        propel = ElementTree.Element("{DAVtest:}exampletextpropmissing")
        propel.text = "Example Text Prop"

        request = TestRequest(
            set_properties = """<Dt:exampletextprop xmlns:Dt="DAVtest:">Example Text Prop</Dt:exampletextprop>""")
        resource = Resource("Text Prop", 10)

        propp = z3c.dav.proppatch.PROPPATCH(resource, request)
        self.assertRaises(z3c.dav.interfaces.PropertyNotFound,
                          propp.handleSet,
                          propel)

    def test_handleRemove_live_property(self):
        propel = ElementTree.Element("{DAVtest:}exampletextprop")
        propel.text = "Example Text Prop"

        request = TestRequest(
            remove_properties = """<Dt:exampletextprop xmlns:Dt="DAVtest:">Example Text Prop</Dt:exampletextprop>""")
        resource = Resource("Text Prop", 10)

        propp = z3c.dav.proppatch.PROPPATCH(resource, request)
        self.assertRaises(z3c.dav.interfaces.ConflictError,
                          propp.handleRemove,
                          propel)

    def test_handleRemove_no_dead_properties(self):
        propel = ElementTree.Element("{example:}exampledeadprop")
        propel.text = "Example Text Prop"

        request = TestRequest(
            remove_properties = """<Dt:exampletextprop xmlns:Dt="DAVtest:">Example Text Prop</Dt:exampletextprop>""")
        resource = Resource("Text Prop", 10)

        propp = z3c.dav.proppatch.PROPPATCH(resource, request)
        self.assertEqual(propp.handleRemove(propel), [])

    def test_event_onsetProperty(self):
        request = TestRequest(
            set_properties = """<Dt:exampletextprop xmlns:Dt="DAVtest:">Example Text Prop</Dt:exampletextprop>""")
        resource = Resource("Text Prop", 10)

        propp = z3c.dav.proppatch.PROPPATCH(resource, request)
        propp.PROPPATCH()

        self.assertEqual(resource.text, "Example Text Prop") # property modified
        self.assertEqual(len(self.events), 1)
        self.assert_(IObjectModifiedEvent.providedBy(self.events[0]))
        self.assertEqual(self.events[0].object, resource)

    def test_event_onsetProperty_sameValue(self):
        request = TestRequest(
            set_properties = """<Dt:exampletextprop xmlns:Dt="DAVtest:">Text Prop</Dt:exampletextprop>""")
        resource = Resource("Text Prop", 10)

        propp = z3c.dav.proppatch.PROPPATCH(resource, request)
        propp.PROPPATCH()

        self.assertEqual(resource.text, "Text Prop")
        self.assertEqual(len(self.events), 0)

    def test_event_multipleProperty(self):
        request = TestRequest(
            set_properties = """
<Dt:exampletextprop xmlns:Dt="DAVtest:">Text Prop</Dt:exampletextprop>
<Dt:exampleintprop xmlns:Dt="DAVtest:">14</Dt:exampleintprop>
""")
        resource = Resource("Text Prop", 10)

        propp = z3c.dav.proppatch.PROPPATCH(resource, request)
        propp.PROPPATCH()

        self.assertEqual(resource.text, "Text Prop")
        self.assertEqual(resource.intprop, 14)
        self.assertEqual(len(self.events), 1)
        self.assertEqual(IObjectModifiedEvent.providedBy(self.events[0]), True)
        self.assertEqual(self.events[0].object, resource)

    def test_unauthorized_proppatch(self):
        request = TestRequest(
            set_properties = """<Dt:unauthprop xmlns:Dt="DAVtest:">Example Text Prop</Dt:unauthprop>""")
        resource = Resource("Text Prop", 10)

        propp = z3c.dav.proppatch.PROPPATCH(resource, request)
        self.assertRaises(Unauthorized, propp.PROPPATCH)

    def test_set_readonly_resourcetype(self):
        # When trying to set a value on the `{DAV:}resourcetype` property
        # we need to first check that the field is readonly as the resourcetype
        # property has no input widget registered for it.
        resourcetype = ElementTree.Element("{DAV:}resourcetype")
        resourcetype.append(ElementTree.Element("{DAV:}collection"))
        request = TestRequest(set_properties = """<D:resourcetype />""")
        resource = Resource("Test prop", 10)

        propp = z3c.dav.proppatch.PROPPATCH(resource, request)
        self.assertRaises(z3c.dav.interfaces.ForbiddenError,
                          propp.handleSet, resourcetype)

    def test_set_readonly_resourcetype_samevalue(self):
        # Make sure we get the same error as the previous test but this time
        # trying to set the resourcetype to same value.
        resourcetype = ElementTree.Element("{DAV:}resourcetype")
        request = TestRequest(set_properties = """<D:resourcetype />""")
        resource = Resource("Test prop", 10)

        propp = z3c.dav.proppatch.PROPPATCH(resource, request)
        self.assertRaises(z3c.dav.interfaces.ForbiddenError,
                          propp.handleSet, resourcetype)


class DEADProperties(object):
    interface.implements(z3c.dav.interfaces.IOpaquePropertyStorage)

    def __init__(self, context):
        self.data = context.props = getattr(context, "props", {})

    def getAllProperties(self):
        for tag in self.data:
            yield tag

    def hasProperty(self, tag):
        return tag in self.data

    def getProperty(self, tag):
        return self.data[tag]

    def setProperty(self, tag, value):
        self.data[tag] = value

    def removeProperty(self, tag):
        del self.data[tag]


class PROPPATCHHandlePropertyRemoveDead(unittest.TestCase):

    def eventLog(self, event):
        self.events.append(event)

    def setUp(self):
        etreeSetup(key = "py25")

        gsm = component.getGlobalSiteManager()

        gsm.registerAdapter(DEADProperties, (IResource,))

        gsm.registerAdapter(DummyResourceURL,
                            (IResource, z3c.dav.interfaces.IWebDAVRequest))

        self.events = []
        zope.event.subscribers.append(self.eventLog)

    def tearDown(self):
        etreeTearDown()

        gsm = component.getGlobalSiteManager()

        gsm.unregisterAdapter(DEADProperties, (IResource,))

        gsm.unregisterAdapter(DummyResourceURL,
                              (IResource,
                               z3c.dav.interfaces.IWebDAVRequest))

        self.events = []
        zope.event.subscribers.remove(self.eventLog)

    def test_remove_no_storage(self):
        propel = ElementTree.Element("{example:}exampledeadprop")
        propel.text = "Example Text Prop"

        request = TestRequest(
            remove_properties = """<Dt:exampledeadprop xmlns:Dt="example:">Example Text Prop</Dt:exampledeadprop>""")
        resource = Resource("Text Prop", 10)

        propp = z3c.dav.proppatch.PROPPATCH(resource, request)
        self.assertEqual(propp.handleRemove(propel), [])

    def test_remove_not_there(self):
        propel = ElementTree.Element("{example:}exampledeadprop")
        propel.text = "Example Text Prop"

        request = TestRequest(
            remove_properties = """<Dt:exampletextprop xmlns:Dt="DAVtest:">Example Text Prop</Dt:exampletextprop>""")
        resource = Resource("Text Prop", 10)

        propp = z3c.dav.proppatch.PROPPATCH(resource, request)
        self.assertEqual(propp.handleRemove(propel), [])
        self.assertEqual(self.events, [])

    def test_remove_prop(self):
        propel = ElementTree.Element("{example:}exampledeadprop")
        propel.text = "Example Text Prop"

        request = TestRequest(
            remove_properties = """<Dt:exampletextprop xmlns:Dt="DAVtest:">Example Text Prop</Dt:exampletextprop>""")
        resource = Resource("Text Prop", 10)

        testprop = "{example:}exampledeadprop"

        deadprops = DEADProperties(resource)
        deadprops.setProperty(testprop, "Example Text Prop")
        self.assertEqual(deadprops.hasProperty(testprop), True)
        self.assertEqual(deadprops.getProperty(testprop), "Example Text Prop")

        propp = z3c.dav.proppatch.PROPPATCH(resource, request)

        removed = propp.handleRemove(propel)
        self.assertEqual(len(removed), 1)
        self.assertEqual(ISequence.providedBy(removed[0]), True)
        self.assertEqual(
            removed[0].interface, z3c.dav.interfaces.IOpaquePropertyStorage)
        self.assertEqual(removed[0].keys, ("{example:}exampledeadprop",))
        self.assertEqual(deadprops.hasProperty(testprop), False)

    def test_event_on_remove_property(self):
        request = TestRequest(
            remove_properties = """<Dt:exampledeadprop xmlns:Dt="example:">Example Text Prop</Dt:exampledeadprop>""")

        testprop = "{example:}exampledeadprop"

        resource = Resource("Text Prop", 10)
        deadprops = DEADProperties(resource)
        deadprops.setProperty(testprop, "Example Text Prop")

        propp = z3c.dav.proppatch.PROPPATCH(resource, request)
        propp.PROPPATCH()

        self.assertEqual(deadprops.hasProperty(testprop), False)

        self.assertEqual(len(self.events), 1)
        self.assertEqual(IObjectModifiedEvent.providedBy(self.events[0]), True)
        self.assertEqual(self.events[0].object, resource)


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(PROPPATCHXmlParsing),
        unittest.makeSuite(PROPPATCHHandlePropertyModification),
        unittest.makeSuite(PROPPATCHHandlePropertyRemoveDead),
        ))
