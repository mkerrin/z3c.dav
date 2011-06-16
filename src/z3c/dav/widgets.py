##############################################################################
# Copyright (c) 2006 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
##############################################################################
"""A collection of usefull classes and methods related to WebDAV.

$Id$
"""
__docformat__ = 'restructuredtext'

import datetime
import calendar

import zope.component
from zope import interface
from zope.schema import getFieldsInOrder

import z3c.etree
import interfaces

import zope.datetime
from zope.formlib.interfaces import ConversionError, MissingInputError

DEFAULT_NS = 'DAV:'


class DAVWidget(object):
    """Base class for rendering WebDAV properties through implementations like
    PROPFIND and PROPPATCH.
    """
    interface.implements(interfaces.IDAVWidget)
    interface.classProvides(interfaces.IIDAVWidget)

    def __init__(self, context, request):
        self.context = context
        self.request = request

        self.name = self.context.__name__
        self.namespace = None

        # value to render.
        self._value = None

    def setRenderedValue(self, value):
        self._value = value

    def toDAVValue(self, value):
        """Override this method in the base class. This method should either
        a string, a list or tuple
        """
        raise NotImplementedError, \
              "please implemented this method in a subclass of DAVWidget."

    def render(self):
        etree = z3c.etree.getEngine()
        el = etree.Element(etree.QName(self.namespace, self.name))

        rendered_value = self.toDAVValue(self._value)
        el.text = rendered_value

        return el


class TextDAVWidget(DAVWidget):
    interface.classProvides(interfaces.IIDAVWidget)

    def toDAVValue(self, value):
        if value is None:
            return None
        return value


class IntDAVWidget(DAVWidget):
    interface.classProvides(interfaces.IIDAVWidget)

    def toDAVValue(self, value):
        if value is not None:
            return str(value)
        return None


class DatetimeDAVWidget(DAVWidget):
    """Same widget can be used for a date field also."""
    interface.classProvides(interfaces.IIDAVWidget)

    def toDAVValue(self, value):
        # datetime object
        if value is None:
            return None

        return zope.datetime.rfc1123_date(calendar.timegm(value.utctimetuple()))


class DateDAVWidget(DAVWidget):
    """Same widget can be used for a date field also."""
    interface.classProvides(interfaces.IIDAVWidget)

    def toDAVValue(self, value):
        # datetime object
        if value is None:
            return None

        return zope.datetime.rfc1123_date(calendar.timegm(value.timetuple()))


class ISO8601DatetimeDAVWidget(DAVWidget):
    """Same widget can be used for a date field also."""
    interface.classProvides(interfaces.IIDAVWidget)

    def toDAVValue(self, value):
        if value is None:
            return None

        if isinstance(value, datetime.datetime) and value.utcoffset() is None:
            return value.isoformat() + "Z"
        return value.isoformat()


class ObjectDAVWidget(DAVWidget):
    """
    ObjectDAVWidget that will display all properties whether or not the
    value of specific property in question is the missing value or not.

    `render_missing_values` attribute is a marker to tell webdav to render
    all fields which instance value is equal to the fields missing_value.
    """
    interface.classProvides(interfaces.IIDAVWidget)

    render_missing_values = True

    def render(self):
        etree = z3c.etree.getEngine()
        el = etree.Element(etree.QName(self.namespace, self.name))

        if self._value is None:
            return el

        interface = self.context.schema
        for name, field in getFieldsInOrder(interface):
            field = field.bind(self._value)
            field_value = field.get(self._value)

            # Careful this could result in elements not been displayed that
            # should be. This is tested in test_widgets but it mightened be
            # what some people think.
            if field_value == field.missing_value and \
                   not self.render_missing_values and not field.required:
                continue

            widget = zope.component.getMultiAdapter((field, self.request),
                                                    interfaces.IDAVWidget)
            widget.namespace = self.namespace
            widget.setRenderedValue(field.get(self._value))
            el.append(widget.render())

        return el


class ListDAVWidget(DAVWidget):
    interface.classProvides(interfaces.IIDAVWidget)

    def render(self):
        etree = z3c.etree.getEngine()
        el = etree.Element(etree.QName(self.namespace, self.name))

        if self._value is None:
            return el

        value_type = self.context.value_type
        if value_type is None:
            for value in self._value:
                el.append(etree.Element(etree.QName(self.namespace, value)))
        else:
            # value_type is not None so render each item in the sequence
            # according to the widget register for this field.
            for value in self._value:
                widget = zope.component.getMultiAdapter(
                    (value_type, self.request), interfaces.IDAVWidget)
                widget.setRenderedValue(value)
                widget.namespace = self.namespace
                el.append(widget.render())
        return el


################################################################################
#
# Now for a collection of input widgets.
#
################################################################################


class DAVInputWidget(object):
    interface.implements(interfaces.IDAVInputWidget)
    interface.classProvides(interfaces.IIDAVInputWidget)

    def __init__(self, context, request):
        self.context = context
        self.request = request

        self.name = self.context.__name__
        self.namespace = None

    def getProppatchElement(self):
        """NOTE that the latest specification does NOT specify that a client
        can't update a property only once during a PROPPATCH request -> this
        method and implementation is meaningless.
        """
        return self.request.xmlDataSource.findall(
            '{DAV:}set/{DAV:}prop/{%s}%s' % (self.namespace, self.name))[-1:]

    def hasInput(self):
        if self.getProppatchElement():
            return True
        return False

    def toFieldValue(self, element):
        raise NotImplementedError(
            "Please implement the toFieldValue as a subclass of DAVInputWidget")

    def getInputValue(self):
        el = self.getProppatchElement()

        # form input is required, otherwise raise an error
        if not el:
            raise MissingInputError(self.name, None, None)

        # convert input to suitable value - may raise conversion error
        value = self.toFieldValue(el[0])
        return value


class TextDAVInputWidget(DAVInputWidget):
    interface.classProvides(interfaces.IIDAVInputWidget)

    def toFieldValue(self, element):
        value = element.text
        if value is None:
            return u"" # toFieldValue must validate against the
        if not isinstance(value, unicode):
            return value.decode("utf-8")
        return value


class IntDAVInputWidget(DAVInputWidget):
    interface.classProvides(interfaces.IIDAVInputWidget)

    def toFieldValue(self, element):
        value = element.text
        # XXX - should this be happening - has then the field doesn't validate
        # in the default case against the corresponding field.
        if not value:
            return self.context.missing_value

        try:
            return int(value)
        except ValueError, e:
            raise ConversionError("Invalid int", e)


class FloatDAVInputWidget(DAVInputWidget):
    interface.classProvides(interfaces.IIDAVInputWidget)

    def toFieldValue(self, element):
        value = element.text
        if not value:
            # XXX - should this be the case?
            return self.context.missing_value

        try:
            return float(value)
        except ValueError, e:
            raise ConversionError("Invalid float", e)


class DatetimeDAVInputWidget(DAVInputWidget):
    interface.classProvides(interfaces.IIDAVInputWidget)

    def toFieldValue(self, element):
        value = element.text
        try:
            return zope.datetime.parseDatetimetz(value)
        except (zope.datetime.DateTimeError, ValueError, IndexError), e:
            raise ConversionError("Invalid datetime date", e)


class DateDAVInputWidget(DatetimeDAVInputWidget):
    interface.classProvides(interfaces.IIDAVInputWidget)

    def toFieldValue(self, element):
        value = super(DateDAVInputWidget, self).toFieldValue(element)
        return value.date()
