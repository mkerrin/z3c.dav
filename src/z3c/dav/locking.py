##############################################################################
# Copyright (c) 2006 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
##############################################################################
"""WebDAV LOCK and UNLOCK methods.

Request contains a lockinfo XML element.

  <!ELEMENT lockinfo (lockscope, locktype, owner?)  >
  <!ELEMENT lockscope (exclusive | shared) >
  <!ELEMENT locktype (write) >
  <!ELEMENT shared EMPTY >
  <!ELEMENT exclusive EMPTY >
  <!ELEMENT write EMPTY >
  <!ELEMENT owner ANY >

Response contains a lockdiscovery XML element.

  <!ELEMENT lockdiscovery (activelock)* >
  <!ELEMENT activelock (lockscope, locktype, depth, owner?, timeout?,
            locktoken?, lockroot)>
  <!ELEMENT depth (#PCDATA) >
     "0" | "1" | "infinity"
  <!ELEMENT timeout (#PCDATA) >
    TimeType (defined in Section 10.7).
  <!ELEMENT locktoken (href) >
    locktoken uri
  <!ELEMENT lockroot (href) >
    The href element contains the root of the lock.

$Id$
"""
__docformat__ = 'restructuredtext'

import copy
import time
import random
import datetime

from zope import component
from zope import interface

import z3c.etree
import z3c.dav.interfaces
import z3c.dav.properties
from z3c.dav.coreproperties import IDAVLockdiscovery, IDAVSupportedlock
import z3c.dav.utils
import ifvalidator

MAXTIMEOUT = (2L ** 32) - 1
DEFAULTTIMEOUT = 12 * 60L

_randGen = random.Random(time.time())

def generateLocktoken():
    """
    Simple utility method to generate a opaque lock token.
    """
    return "opaquelocktoken:%s-%s-00105A989226:%.03f" % \
           (_randGen.random(), _randGen.random(), time.time())


@component.adapter(interface.Interface, z3c.dav.interfaces.IWebDAVRequest)
@interface.implementer(z3c.dav.interfaces.IWebDAVMethod)
def LOCK(context, request):
    """
    If we can adapt the context to a lock manager then we should be able to
    lock the resource.
    """
    lockmanager = z3c.dav.interfaces.IDAVLockmanager(context, None)
    if lockmanager is None:
        return None
    if not lockmanager.islockable():
        return None

    return LOCKMethod(context, request, lockmanager)


class LOCKMethod(object):
    """
    LOCK handler for all objects.
    """
    interface.implements(z3c.dav.interfaces.IWebDAVMethod)
    component.adapts(interface.Interface, z3c.dav.interfaces.IWebDAVRequest)

    def __init__(self, context, request, lockmanager):
        self.context = context
        self.request = request
        self.lockmanager = lockmanager

    def getTimeout(self):
        """
        Return a datetime.timedelta object representing the duration of
        the requested lock token. This information is passed in the `Timeout'
        header and corresponds to the following syntax.

          TimeOut = "Timeout" ":" 1#TimeType
          TimeType = ("Second-" DAVTimeOutVal | "Infinite")
                     ; No LWS allowed within TimeType
          DAVTimeOutVal = 1*DIGIT

        Multiple TimeType entries are listed in order of performace so this
        method will return the first valid TimeType converted to a
        `datetime.timedelta' object or else it returns the default timeout.

          >>> from zope.publisher.browser import TestRequest

        No supplied value -> default value.

          >>> LOCKMethod(None, TestRequest(environ = {}), None).getTimeout()
          datetime.timedelta(0, 720)

        Infinity lock timeout is too long so revert to the default timeout.

          >>> LOCKMethod(None,
          ...    TestRequest(environ = {'TIMEOUT': 'infinity'}),
          ...    None).getTimeout()
          datetime.timedelta(0, 720)
          >>> LOCKMethod(None,
          ...    TestRequest(environ = {'TIMEOUT': 'infinite'}),
          ...    None).getTimeout()
          datetime.timedelta(0, 720)

        Specify a lock timeout of 500 seconds.

          >>> LOCKMethod(None,
          ...    TestRequest(environ = {'TIMEOUT': 'Second-500'}),
          ...    None).getTimeout()
          datetime.timedelta(0, 500)

        Invalid and invalid second.

          >>> LOCKMethod(None,
          ...    TestRequest(environ = {'TIMEOUT': 'XXX500'}),
          ...    None).getTimeout()
          Traceback (most recent call last):
          ...
          BadRequest: <zope.publisher.browser.TestRequest instance URL=http://127.0.0.1>, u'Invalid TIMEOUT header'

          >>> LOCKMethod(None,
          ...    TestRequest(environ = {'TIMEOUT': 'XXX-500'}),
          ...    None).getTimeout()
          Traceback (most recent call last):
          ...
          BadRequest: <zope.publisher.browser.TestRequest instance URL=http://127.0.0.1>, u'Invalid TIMEOUT header'

          >>> LOCKMethod(None,
          ...    TestRequest(environ = {'TIMEOUT': 'Second-500x'}),
          ...    None).getTimeout()
          Traceback (most recent call last):
          ...
          BadRequest: <zope.publisher.browser.TestRequest instance URL=http://127.0.0.1>, u'Invalid TIMEOUT header'

        Maximum timeout value.

          >>> timeout = 'Second-%d' %(MAXTIMEOUT + 100)
          >>> LOCKMethod(None,
          ...    TestRequest(environ = {'TIMEOUT': timeout}),
          ...    None).getTimeout()
          datetime.timedelta(0, 720)

          >>> LOCKMethod(None,
          ...    TestRequest(environ = {'TIMEOUT': 'Second-3600'}),
          ...    None).getTimeout()
          datetime.timedelta(0, 3600)

        Specify multiple timeout values. The first applicable time type value
        is choosen.

          >>> LOCKMethod(None, TestRequest(
          ...    environ = {'TIMEOUT': 'Infinity, Second-3600'}),
          ...    None).getTimeout()
          datetime.timedelta(0, 3600)

          >>> timeout = 'Infinity, Second-%d' %(MAXTIMEOUT + 10)
          >>> LOCKMethod(None,
          ...    TestRequest(environ = {'TIMEOUT': timeout}),
          ...    None).getTimeout()
          datetime.timedelta(0, 720)

          >>> timeout = 'Second-1200, Second-450, Second-500'
          >>> LOCKMethod(None,
          ...    TestRequest(environ = {'TIMEOUT': timeout}),
          ...    None).getTimeout()
          datetime.timedelta(0, 1200)

          >>> timeout = 'Second-%d, Second-450' %(MAXTIMEOUT + 10)
          >>> LOCKMethod(None,
          ...    TestRequest(environ = {'TIMEOUT': timeout}),
          ...    None).getTimeout()
          datetime.timedelta(0, 450)

        """
        timeout = None
        header = self.request.getHeader("timeout", "infinity")
        for timeoutheader in header.split(","):
            timeoutheader = timeoutheader.strip().lower()

            t = timeoutheader.split("-")
            if len(t) == 2 and t[0].lower().lower() == "second":
                th = t[1]
            elif len(t) == 1 and (t[0] == "infinite" or t[0] == "infinity"):
                th = t[0]
            else:
                raise z3c.dav.interfaces.BadRequest(
                    self.request, message = u"Invalid TIMEOUT header")

            if th == "infinite" or th == "infinite" or th == "infinity":
                timeout = None
            else:
                try:
                    timeout = long(th)
                except ValueError:
                    raise z3c.dav.interfaces.BadRequest(
                        self.request, message = u"Invalid TIMEOUT header")

            if timeout is not None and timeout < MAXTIMEOUT:
                break # we have gotten a valid timeout we want to use.

            timeout = None # try again to find a valid timeout value.

        if timeout is None:
            timeout = DEFAULTTIMEOUT

        return datetime.timedelta(seconds = timeout)

    def getDepth(self):
        """Default is infinity.

          >>> from zope.publisher.browser import TestRequest

          >>> LOCKMethod(None, TestRequest(), None).getDepth()
          'infinity'
          >>> LOCKMethod(
          ...    None, TestRequest(environ = {'DEPTH': '0'}), None).getDepth()
          '0'
          >>> LOCKMethod(None, TestRequest(
          ...    environ = {'DEPTH': 'infinity'}), None).getDepth()
          'infinity'
          >>> LOCKMethod(None, TestRequest(
          ...    environ = {'DEPTH': '1'}), None).getDepth()
          Traceback (most recent call last):
          ...
          BadRequest: <zope.publisher.browser.TestRequest instance URL=http://127.0.0.1>, u"Invalid depth header. Must be either '0' or 'infinity'"

        """
        depth = self.request.getHeader("depth", "infinity")
        if depth not in ("0", "infinity"):
            raise z3c.dav.interfaces.BadRequest(
                self.request,
                u"Invalid depth header. Must be either '0' or 'infinity'")

        return depth

    def LOCK(self):
        # The Lock-Token header is not returned in the response for a
        # successful refresh LOCK request.
        refreshlock = False

        if self.request.xmlDataSource is None:
            self.handleLockRefresh()
            refreshlock = True
        else: # Body => try to lock the resource
            locktoken = self.handleLock()

        etree = z3c.etree.getEngine()

        davprop, adapter = z3c.dav.properties.getProperty(
            self.context, self.request, "{DAV:}lockdiscovery")
        davwidget = z3c.dav.properties.getWidget(
            davprop, adapter, self.request)
        propel = etree.Element(etree.QName("DAV:", "prop"))
        propel.append(davwidget.render())

        self.request.response.setStatus(200)
        self.request.response.setHeader("Content-Type", "application/xml")
        if not refreshlock:
            self.request.response.setHeader("Lock-Token", "<%s>" % locktoken)

        return etree.tostring(propel)

    def handleLockRefresh(self):
        if not self.lockmanager.islocked():
            raise z3c.dav.interfaces.PreconditionFailed(
                self.context, message = u"Context is not locked.")

        if not ifvalidator.matchesIfHeader(self.context, self.request):
            raise z3c.dav.interfaces.PreconditionFailed(
                self.context, message = u"Lock-Token doesn't match request uri")

        timeout = self.getTimeout()
        self.lockmanager.refreshlock(timeout)

    def handleLock(self):
        locktoken = None

        xmlsource = self.request.xmlDataSource
        if xmlsource.tag != "{DAV:}lockinfo":
            raise z3c.dav.interfaces.UnprocessableError(
                self.context,
                message = u"LOCK request body must be a `lockinfo' XML element")

        timeout = self.getTimeout()

        depth = self.getDepth()

        etree = z3c.etree.getEngine()

        lockscope = xmlsource.find("{DAV:}lockscope")
        if lockscope is None:
            raise z3c.dav.interfaces.UnprocessableError(
                self.context,
                message = u"No `{DAV:}lockscope' XML element in request")
        lockscope_str = z3c.dav.utils.parseEtreeTag(lockscope[0].tag)[1]

        locktype = xmlsource.find("{DAV:}locktype")
        if locktype is None:
            raise z3c.dav.interfaces.UnprocessableError(
                self.context,
                message = u"No `{DAV:}locktype' XML element in request")
        locktype_str = z3c.dav.utils.parseEtreeTag(locktype[0].tag)[1]

        supportedlocks = component.getMultiAdapter(
            (self.context, self.request), IDAVSupportedlock)
        for entry in supportedlocks.supportedlock:
            if entry.locktype[0] == locktype_str and \
               entry.lockscope[0] == lockscope_str:
                break
        else:
            raise z3c.dav.interfaces.UnprocessableError(
                self.context,
                message = u"Unknown lock-token requested.")

        owner = xmlsource.find("{DAV:}owner")
        if owner is not None: # The owner element is optional.
            owner_str = etree.tostring(copy.copy(owner))
        else:
            owner_str = None

        try:
            locktoken = self.lockmanager.lock(scope = lockscope_str,
                                              type = locktype_str,
                                              owner = owner_str,
                                              duration = timeout,
                                              depth = depth)
        except z3c.dav.interfaces.AlreadyLocked, error:
            raise z3c.dav.interfaces.WebDAVErrors(self.context, [error])

        return locktoken

################################################################################
#
# UNLOCK method.
#
################################################################################

@component.adapter(interface.Interface, z3c.dav.interfaces.IWebDAVRequest)
@interface.implementer(z3c.dav.interfaces.IWebDAVMethod)
def UNLOCK(context, request):
    """
    If we can adapt the context to a lock manager then we should be able to
    unlock the resource.
    """
    lockmanager = z3c.dav.interfaces.IDAVLockmanager(context, None)
    if lockmanager is None:
        return None
    if not lockmanager.islockable():
        return None

    return UNLOCKMethod(context, request, lockmanager)


class UNLOCKMethod(object):
    """
    UNLOCK handler for all objects.
    """
    interface.implements(z3c.dav.interfaces.IWebDAVMethod)
    component.adapts(interface.Interface, z3c.dav.interfaces.IWebDAVRequest)

    def __init__(self, context, request, lockmanager):
        self.context = context
        self.request = request
        self.lockmanager = lockmanager

    def UNLOCK(self):
        locktoken = self.request.getHeader("lock-token", "")
        if len(locktoken) > 1 and locktoken[0] == "<" and locktoken[-1] == ">":
            locktoken = locktoken[1:-1]

        if not locktoken:
            raise z3c.dav.interfaces.BadRequest(
                self.request, message = u"No lock-token header supplied")

        activelock = component.getMultiAdapter(
            (self.context, self.request), IDAVLockdiscovery).lockdiscovery
        if not self.lockmanager.islocked() or \
               locktoken not in [ltoken.locktoken[0] for ltoken in activelock]:
            raise z3c.dav.interfaces.ConflictError(
                self.context, message = "object is locked or the lock isn't" \
                                        " in the scope the passed.")

        self.lockmanager.unlock(locktoken)

        self.request.response.setStatus(204)
        return ""
