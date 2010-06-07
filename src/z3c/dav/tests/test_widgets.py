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
"""Test the WebDAV widget framework.

$Id$
"""

import unittest
import datetime
from cStringIO import StringIO

from zope import schema
from zope import component
import zope.schema.interfaces
from zope.interface import Interface, implements
from zope.interface.verify import verifyObject
from zope.datetime import tzinfo

from z3c.dav import widgets
import z3c.dav.interfaces
from z3c.dav.publisher import WebDAVRequest
from z3c.etree.testing import etreeSetup, etreeTearDown, assertXMLEqual


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
            f = StringIO("")

        super(TestWebDAVRequest, self).__init__(
            f, {"CONTENT_TYPE": "text/xml",
                "CONTENT_LENGTH": len(f.getvalue()),
                })

        # processInputs to test request
        self.processInputs()

        # if elem is given insert it into the proppatch request.
        if elem is not None:
            self.xmlDataSource[0][0].append(elem)


class _WebDAVWidgetTest(unittest.TestCase):

    namespace = u"testns:"
    name = u"foo"
    missing_name = u"someotherproperty"

    field_content = u"" # field value assigned to the demo content.
    rendered_content = u"" # string value of the some value in ...

    _FieldFactory = None
    _WidgetFactory = None

    def tearDown(self):
        etreeTearDown()

    def setUp(self):
        self.etree = etreeSetup()

    def setUpContent(self, desc = u'', title = u'Foo Title', element = None):
        ## setup the field first to stop some really weird errors
        foofield = self._FieldFactory(
            __name__ = self.name,
            title = title,
            description = desc)
        class IDemoContent(Interface):
            foo = foofield

        class DemoContent(object):
            implements(IDemoContent)

        self.content = DemoContent()
        field = IDemoContent['foo']
        self.field = field.bind(self.content)
        self.setUpWidget(element)

    def setUpWidget(self, element = None):
        self.request = TestWebDAVRequest(element)
        self.widget = self._WidgetFactory(self.field, self.request)
        self.widget.namespace = self.namespace


class WebDAVBaseWidgetTest(_WebDAVWidgetTest):

    _FieldFactory = schema.Text
    _WidgetFactory = widgets.DAVWidget

    def setUp(self):
        super(WebDAVBaseWidgetTest, self).setUp()
        self.setUpContent()

    def test_dontuseDAVWidgetRender(self):
        self.assertRaises(NotImplementedError, self.widget.render)

    def test_dontuseDAVWidgetToDAVValue(self):
        self.assertRaises(NotImplementedError, self.widget.toDAVValue, u"test")


class WebDAVWidgetTest(_WebDAVWidgetTest):

    _FieldFactory = schema.Text
    _WidgetFactory = widgets.TextDAVWidget

    def test_interface(self):
        self.assertEqual(
            verifyObject(z3c.dav.interfaces.IDAVWidget, self.widget), True)

    def test_render(self):
        self.widget.setRenderedValue(self.field_content)
        self.content.foo = self.field_content
        element = self.widget.render()
        assertXMLEqual(self.etree.tostring(element),
            '<ns0:foo xmlns:ns0="testns:">%s</ns0:foo>' % self.rendered_content)

    def test_nofieldValue(self):
        request = TestWebDAVRequest()
        widget = self._WidgetFactory(self.field, request)
        widget.namespace = self.namespace
        element = widget.render()
        assertXMLEqual(self.etree.tostring(element),
                         '<ns0:foo xmlns:ns0="testns:" />')


class TextWebDAVWidgetTest(WebDAVWidgetTest):

    _FieldFactory  = schema.Text
    _WidgetFactory = widgets.TextDAVWidget

    field_content = u'Foo Value'
    rendered_content = u'Foo Value'

    def setUp(self):
        super(TextWebDAVWidgetTest, self).setUp()
        self.setUpContent()


class IntWebDAVWidgetTest(WebDAVWidgetTest):

    _FieldFactory  = schema.Int
    _WidgetFactory = widgets.IntDAVWidget

    field_content = 10
    rendered_content = u'10'

    def setUp(self):
        super(IntWebDAVWidgetTest, self).setUp()
        self.setUpContent()


class FloatWebDAVWidgetTest(WebDAVWidgetTest):

    _FieldFactory  = schema.Float
    _WidgetFactory = widgets.IntDAVWidget

    field_content = 10.0
    rendered_content = u"10.0"

    def setUp(self):
        super(FloatWebDAVWidgetTest, self).setUp()
        self.setUpContent()


class DatetimeWebDAVWidgetTest(WebDAVWidgetTest):

    _FieldFactory  = schema.Datetime
    _WidgetFactory = widgets.DatetimeDAVWidget

    rendered_content = u"Tue, 23 May 2006 23:00:58 GMT"
    field_content = datetime.datetime(2006, 5, 24, 0, 0, 58,
                                      tzinfo = tzinfo(60))

    def setUp(self):
        super(DatetimeWebDAVWidgetTest, self).setUp()
        self.setUpContent()


class DatetimeWebDAVWidgetNoTZInfoTest(WebDAVWidgetTest):

    _FieldFactory  = schema.Datetime
    _WidgetFactory = widgets.DatetimeDAVWidget

    rendered_content = u"Wed, 24 May 2006 00:00:58 GMT"
    field_content = datetime.datetime(2006, 5, 24, 0, 0, 58)

    def setUp(self):
        super(DatetimeWebDAVWidgetNoTZInfoTest, self).setUp() 
        self.setUpContent()


class ISO8601DatetimeWebDAVWidgetTest(DatetimeWebDAVWidgetTest):

    _WidgetFactory = widgets.ISO8601DatetimeDAVWidget

    rendered_content = u"2006-05-24T00:00:58+01:00"


class ISO8601DatetimeWebDAVWidgetNoTZInfoTest(DatetimeWebDAVWidgetNoTZInfoTest):

    _WidgetFactory = widgets.ISO8601DatetimeDAVWidget

    rendered_content = u"2006-05-24T00:00:58Z"


class DateWebDAVWidgetTest(WebDAVWidgetTest):

    _FieldFactory  = schema.Date
    _WidgetFactory = widgets.DateDAVWidget

    field_content = datetime.date(2006, 5, 23)
    rendered_content = u"Tue, 23 May 2006 00:00:00 GMT"

    def setUp(self):
        super(DateWebDAVWidgetTest, self).setUp()
        self.setUpContent()


class ISO8601DateWebDAVWidgetTest(DateWebDAVWidgetTest):

    _WidgetFactory = widgets.ISO8601DatetimeDAVWidget

    field_content = datetime.date(2006, 5, 23)
    rendered_content = u"2006-05-23"


class ListWebDAVWidgetTest(WebDAVWidgetTest):

    _FieldFactory  = schema.List
    _WidgetFactory = widgets.ListDAVWidget

    field_content = [u'collection']
    rendered_content = '<ns0:collection />'

    def setUp(self):
        super(ListWebDAVWidgetTest, self).setUp()
        self.setUpContent()


class ListTextWebDAVWidgetTest(WebDAVWidgetTest):

    _FieldFactory = schema.List
    _WidgetFactory = widgets.ListDAVWidget

    rendered_content = "<ns0:name>firstitem</ns0:name><ns0:name>seconditem</ns0:name>"

    def setUp(self):
        self.etree = etreeSetup()
        component.getGlobalSiteManager().registerAdapter(
            widgets.TextDAVWidget,
            (zope.schema.interfaces.ITextLine,
             z3c.dav.interfaces.IWebDAVRequest))

        foofield = schema.List(__name__ = self.name,
                               title = u"Foo Title",
                               description = u"Foo field",
                               value_type = schema.TextLine(
                                   __name__ = "name",
                                   title = u"Foo Title",
                                   description = u"Foo field"))

        class IDemoContent(Interface):
            foo = foofield

        class DemoContent(object):
            implements(IDemoContent)

        self.field_content = [u"firstitem", u"seconditem"]
        self.content = DemoContent()
        field = IDemoContent['foo']
        self.field = field.bind(self.content)
        self.setUpWidget()

    def tearDown(self):
        component.getGlobalSiteManager().unregisterAdapter(
            widgets.TextDAVWidget,
            (zope.schema.interfaces.ITextLine,
             z3c.dav.interfaces.IWebDAVRequest))
        super(ListTextWebDAVWidgetTest, self).tearDown()


class ISimpleInterface(Interface):
    name = schema.TextLine(
        title = u"Name subproperty",
        description = u"",
        required = False)

    age = schema.Int(
        title = u"Age subproject",
        description = u"",
        required = True)


class SimpleObject(object):
    implements(ISimpleInterface)

    def __init__(self, **kw):
        self.__dict__.update(kw)


class ObjectDAVWidgetTest(WebDAVWidgetTest):

    _WidgetFactory = widgets.ObjectDAVWidget

    rendered_content = """<ns0:name>Michael Kerrin</ns0:name>
                          <ns0:age>26</ns0:age>"""

    def setUp(self):
        self.etree = etreeSetup()

        foofield = schema.Object(__name__ = self.name,
                                 title = u"Foo Title",
                                 description = u"Foo field",
                                 schema = ISimpleInterface)
        class IDemoContent(Interface):
            foo = foofield

        class DemoContent(object):
            implements(IDemoContent)

        self.field_content = SimpleObject(name = u"Michael Kerrin",
                                          age = 26)
        self.content = DemoContent()
        field = IDemoContent['foo']
        self.field = field.bind(self.content)
        self.setUpWidget()

        component.getGlobalSiteManager().registerAdapter(
            widgets.TextDAVWidget,
            (zope.schema.interfaces.ITextLine,
             z3c.dav.interfaces.IWebDAVRequest))
        component.getGlobalSiteManager().registerAdapter(
            widgets.IntDAVWidget,
            (zope.schema.interfaces.IInt,
             z3c.dav.interfaces.IWebDAVRequest))

    def tearDown(self):
        component.getGlobalSiteManager().unregisterAdapter(
            widgets.TextDAVWidget,
            (zope.schema.interfaces.ITextLine,
             z3c.dav.interfaces.IWebDAVRequest))
        component.getGlobalSiteManager().unregisterAdapter(
            widgets.IntDAVWidget,
            (zope.schema.interfaces.IInt,
             z3c.dav.interfaces.IWebDAVRequest))
        super(ObjectDAVWidgetTest, self).tearDown()

    def test_default_render_missing_values(self):
        widget = self._WidgetFactory(self.field, self.request)
        self.assertEqual(widget.render_missing_values, True)

    def test_renderMissingAttribute(self):
        content = SimpleObject(name = u"Michael Kerrin")

        widget = self._WidgetFactory(self.field, self.request)
        widget.namespace = self.namespace
        widget.setRenderedValue(content)

        self.assertRaises(AttributeError, widget.render)

    def test_renderMissingFieldValue(self):
        ## In this case the name attribute (which is not required) is equal
        ## to the missing_value. The ObjectDAVWidget view still renders this
        ## elements because the render_missing_values is set to True.
        content = SimpleObject(name = None, age = 26)

        widget = self._WidgetFactory(self.field, self.request)
        widget.namespace = self.namespace
        widget.setRenderedValue(content)

        self.assertEqual(widget.render_missing_values, True)

        element = widget.render()
        assertXMLEqual(element, """<ns0:foo xmlns:ns0="testns:">
          <ns0:name />
          <ns0:age>26</ns0:age>
        </ns0:foo>""")

    def test_dontRenderMissingFieldValue(self):
        ## In this case the name attribute (which is not required) is equal
        ## to the missing_value and because the render_missing_values
        ## attribute is False we don't render this XML element.
        content = SimpleObject(name = None, age = 26)

        widget = self._WidgetFactory(self.field, self.request)
        widget.render_missing_values = False
        widget.namespace = self.namespace
        widget.setRenderedValue(content)

        self.assertEqual(widget.render_missing_values, False)

        element = widget.render()
        assertXMLEqual(element, """<ns0:foo xmlns:ns0="testns:">
          <ns0:age>26</ns0:age>
        </ns0:foo>""")

    def test_renderMissingRequiredFieldValue(self):
        ## In this case the age attribute (which is required) is equal
        ## to the missing value so the ObjectDAVWidget should try and
        ## render it.
        content = SimpleObject(name = u"Michael Kerrin", age = None)

        widget = self._WidgetFactory(self.field, self.request)
        widget.namespace = self.namespace
        widget.setRenderedValue(content)

        self.assertEqual(widget.render_missing_values, True)

        element = widget.render()
        assertXMLEqual(element, """<ns0:foo xmlns:ns0="testns:">
          <ns0:name>Michael Kerrin</ns0:name>
          <ns0:age />
        </ns0:foo>""")

    def test_dontRenderMissingRequiredFieldValue(self):
        ## In this case the age attribute (which is required) is equal
        ## to the missing value so the ObjectDAVWidget should try and
        ## render it, even since the render_missing_values is False.
        content = SimpleObject(name = u"Michael Kerrin", age = None)

        widget = self._WidgetFactory(self.field, self.request)
        widget.render_missing_values = False
        widget.namespace = self.namespace
        widget.setRenderedValue(content)

        self.assertEqual(widget.render_missing_values, False)

        element = widget.render()
        assertXMLEqual(element, """<ns0:foo xmlns:ns0="testns:">
          <ns0:name>Michael Kerrin</ns0:name>
          <ns0:age />
        </ns0:foo>""")


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(WebDAVBaseWidgetTest),
        unittest.makeSuite(TextWebDAVWidgetTest),
        unittest.makeSuite(IntWebDAVWidgetTest),
        unittest.makeSuite(FloatWebDAVWidgetTest),
        unittest.makeSuite(DatetimeWebDAVWidgetTest),
        unittest.makeSuite(DatetimeWebDAVWidgetNoTZInfoTest),
        unittest.makeSuite(DateWebDAVWidgetTest),
        unittest.makeSuite(ISO8601DatetimeWebDAVWidgetTest),
        unittest.makeSuite(ISO8601DatetimeWebDAVWidgetNoTZInfoTest),
        unittest.makeSuite(ISO8601DateWebDAVWidgetTest),
        unittest.makeSuite(ListWebDAVWidgetTest),
        unittest.makeSuite(ListTextWebDAVWidgetTest),
        unittest.makeSuite(ObjectDAVWidgetTest),
        ))
