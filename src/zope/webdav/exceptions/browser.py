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
"""Common WebDAV error handling code.

A lot of WebDAV requests can go badly wrong. If this is the case then return
a snippet of HTML that could be displayed to the user describing what went
left.

$Id$
"""
__docformat__ = 'restructuredtext'

from zope import interface
from zope import component
from zope.formlib import namedtemplate
from zope.app.http.interfaces import IHTTPException
from zope.app.pagetemplate import ViewPageTemplateFile

import zope.webdav.interfaces

class BadRequest(object):
    interface.implements(IHTTPException)
    component.adapts(zope.webdav.interfaces.IBadRequest,
                     zope.webdav.interfaces.IHTTPRequest)

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
