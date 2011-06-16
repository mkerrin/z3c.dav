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
"""Common WebDAV error handling code.

A lot of WebDAV requests can go badly wrong. If this is the case then return
a snippet of HTML that could be displayed to the user describing what went
left.

$Id$
"""
__docformat__ = 'restructuredtext'

from zope import interface
import zope.component
from zope.formlib import namedtemplate
from zope.publisher.interfaces.http import IHTTPException
from zope.app.pagetemplate import ViewPageTemplateFile

import z3c.dav.interfaces

class BadRequest(object):
    interface.implements(IHTTPException)
    zope.component.adapts(z3c.dav.interfaces.IBadRequest,
                          z3c.dav.interfaces.IHTTPRequest)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def message(self):
        return self.context.message

    def __call__(self):
        self.request.response.setStatus(400)
        return self.template()

    template = namedtemplate.NamedTemplate("default")


default_template = namedtemplate.NamedTemplateImplementation(
    ViewPageTemplateFile("badrequest.pt"), BadRequest)
