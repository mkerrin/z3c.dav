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

from zope import component
from zope import schema
from zope import interface
from zope.schema.interfaces import RequiredMissing
from zope.interface.verify import verifyObject
from zope.formlib.interfaces import ConversionError, MissingInputError
from zope.datetime import tzinfo

from z3c.dav import widgets
from z3c.dav.interfaces import IDAVInputWidget
import z3c.etree
from z3c.etree.testing import etreeSetup, etreeTearDown

from test_widgets import TestWebDAVRequest

class _WebDAVWidgetTest(unittest.TestCase):

    namespace = u'testns:'
    name = u'foo'
    missing_name = u'someotherproperty'

    field_content    = u'' # field value assigned to the demo content.
    rendered_content = None # string value of the some value in ...
    bad_rendered_content = None # if not None try to parse this data.

    _FieldFactory  = None
    _WidgetFactory = None

    def tearDown(self):
        etreeTearDown()
        del self.etree

    def setUp(self):
        etreeSetup()
        self.etree = z3c.etree.getEngine()

    def setUpContent(self, desc = u'', title = u'Foo Title', element = None):
        ## setup the field first to stop some really weird errors
        foofield = self._FieldFactory(
            title = title,
            description = desc)
        class IDemoContent(interface.Interface):
            foo = foofield

        class DemoContent(object):
            interface.implements(IDemoContent)

        self.content = DemoContent()
        field = IDemoContent['foo']
        self.field = field.bind(self.content)
        self.setUpWidget(element)

    def setUpWidget(self, element = None):
        request = TestWebDAVRequest(element)
        self.widget = self._WidgetFactory(self.field, request)
        self.widget.namespace = self.namespace


class WebDAVBaseInputWidgetTest(_WebDAVWidgetTest):

    _FieldFactory = schema.Text
    _WidgetFactory = widgets.DAVInputWidget

    def setUp(self):
        super(WebDAVBaseInputWidgetTest, self).setUp()
        self.setUpContent()

    def test_dontuseDAVWidgetToFieldValue(self):
        self.assertRaises(NotImplementedError, self.widget.toFieldValue,
                          self.etree.Element(self.etree.QName(self.namespace,
                                                              self.name)))


class WebDAVInputWidgetTest(_WebDAVWidgetTest):

    _FieldFactory = schema.Text
    _WidgetFactory = widgets.TextDAVInputWidget

    def setUp(self):
        super(WebDAVInputWidgetTest, self).setUp()

        self.element = self.etree.Element(
            self.etree.QName(self.namespace, self.name))
        if self.rendered_content is not None:
            self.element.text = self.rendered_content
        self.setUpContent(element = self.element)

    def test_interface(self):
        self.assertEqual(verifyObject(IDAVInputWidget, self.widget), True)

    def test_hasInput(self):
        self.assertEqual(self.widget.hasInput(), True)

    def test_convert(self):
        self.assertEqual(self.widget.toFieldValue(self.element),
                         self.field_content)

    def test_getInputValue(self):
        value = self.widget.getInputValue()
        self.assertEqual(value, self.field_content)
        self.field.validate(value) # this will raise an exception if false

    def test_noInput(self):
        element = self.etree.Element(
            self.etree.QName(self.namespace, self.missing_name))
        element.text = self.rendered_content
        request = TestWebDAVRequest(element)
        widget  = self._WidgetFactory(self.field, request)
        widget.namespace = self.namespace
        self.assertEqual(widget.hasInput(), False)

    def test_getInputValue_NoInput(self):
        element = self.etree.Element(
            self.etree.QName(self.namespace, self.missing_name))
        element.text = self.rendered_content
        request = TestWebDAVRequest(element)
        widget  = self._WidgetFactory(self.field, request)
        widget.namespace = self.namespace
        self.assertRaises(MissingInputError, widget.getInputValue)

    def _test_badinput(self, bad_rendered_content = None):
        # Only run this test if the self.bad_rendered_content is not None.
        # The test case must expility call this method.
        if bad_rendered_content is None:
            bad_rendered_content = self.bad_rendered_content
        element = self.etree.Element(self.etree.QName(self.namespace, self.name))
        element.text = bad_rendered_content
        request = TestWebDAVRequest(element)
        widget = self._WidgetFactory(self.field, request)
        widget.namespace = self.namespace
        self.assertRaises(ConversionError, widget.getInputValue)


class TextWebDAVInputWidgetTest(WebDAVInputWidgetTest):

    _FieldFactory  = schema.Text
    _WidgetFactory = widgets.TextDAVInputWidget

    field_content = u"Foo Value"
    rendered_content = u"Foo Value"

    def test_noinput(self):
        element = self.etree.Element(self.etree.QName(self.namespace, self.name))
        request = TestWebDAVRequest(element)
        widget = self._WidgetFactory(self.field, request)
        widget.namespace = self.namespace
        value = widget.getInputValue()
        self.field.validate(value)


class IntWebDAVInputWidgetTest(WebDAVInputWidgetTest):

    _FieldFactory  = schema.Int
    _WidgetFactory = widgets.IntDAVInputWidget

    field_content = 10
    rendered_content = u"10"
    bad_rendered_content = u"X10"

    def test_badinput(self):
        super(IntWebDAVInputWidgetTest, self)._test_badinput()

    def test_noinput(self):
        element = self.etree.Element(self.etree.QName(self.namespace, self.name))
        request = TestWebDAVRequest(element)
        widget = self._WidgetFactory(self.field, request)
        widget.namespace = self.namespace
        self.assertEquals(widget.hasInput(), True)
        value = widget.getInputValue()
        self.assertEquals(value, None)
        self.assertRaises(RequiredMissing, self.field.validate, value)


class FloatWebDAVInputWidgetTest(WebDAVInputWidgetTest):

    _FieldFactory  = schema.Float
    _WidgetFactory = widgets.FloatDAVInputWidget

    field_content = 10.4
    rendered_content = u"10.4"
    bad_rendered_content = u"X10.4"

    def test_badinput(self):
        super(FloatWebDAVInputWidgetTest, self)._test_badinput()

    def test_noinput(self):
        element = self.etree.Element(
            self.etree.QName(self.namespace, self.name))
        request = TestWebDAVRequest(element)
        widget = self._WidgetFactory(self.field, request)
        widget.namespace = self.namespace
        self.assertEquals(widget.hasInput(), True)
        value = widget.getInputValue()
        self.assertEquals(value, None)
        self.assertRaises(RequiredMissing, self.field.validate, value)


class DatetimeWebDAVInputWidgetTest(WebDAVInputWidgetTest):

    _FieldFactory  = schema.Datetime
    _WidgetFactory = widgets.DatetimeDAVInputWidget

    rendered_content = u'Wed, 24 May 2006 00:00:58 +0100'
    field_content = datetime.datetime(2006, 5, 24, 0, 0, 58,
                                      tzinfo = tzinfo(60))

    def test_badinput(self):
        super(DatetimeWebDAVInputWidgetTest, self)._test_badinput(
            u'NODAY, 24 May 2006 00:00:58 +0100')


class DateWebDAVInputWidgetTest(DatetimeWebDAVInputWidgetTest):

    _FieldFactory  = schema.Date
    _WidgetFactory = widgets.DateDAVInputWidget

    field_content = datetime.date(2006, 5, 24)


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(WebDAVBaseInputWidgetTest),
        unittest.makeSuite(TextWebDAVInputWidgetTest),
        unittest.makeSuite(IntWebDAVInputWidgetTest),
        unittest.makeSuite(FloatWebDAVInputWidgetTest),
        unittest.makeSuite(DatetimeWebDAVInputWidgetTest),
        unittest.makeSuite(DateWebDAVInputWidgetTest),
        ))
