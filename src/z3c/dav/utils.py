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
"""A collection of useful classes used for generating common XML fragments
for use within z3c.dav

MultiStatus

  <!ELEMENT multistatus (response*, responsedescription?)  >
  <!ELEMENT response (href, ((href*, status)|(propstat+)),
            error?, responsedescription? , location?) >
  <!ELEMENT propstat (prop, status, error?, responsedescription?) >
  <!ELEMENT prop ANY >
  <!ELEMENT href (#PCDATA)>
  <!ELEMENT status (#PCDATA) >
  <!ELEMENT responsedescription (#PCDATA) >
  <!ELEMENT error ANY >
  <!ELEMENT location (href)>

Also contains some usefully methods like

+ getObjectURL

$Id$
"""
__docformat__ = 'restructuredtext'

import zope.component
from zope import interface
from zope.publisher.http import status_reasons
from zope.traversing.browser.interfaces import IAbsoluteURL
from zope.container.interfaces import IReadContainer
import z3c.etree

class IPropstat(interface.Interface):
    """Helper interface to render a response XML element. 
    """

    properties = interface.Attribute("""List of etree elements that make up
    the prop element.
    """)

    status = interface.Attribute("""Integer status code of all the properties
    belonging to this propstat XML element.
    """)

    error = interface.Attribute("""List of etree elements describing the
    error condition of the properties within this propstat XML element.
    """)

    responsedescription = interface.Attribute("""String containing readable
    information about the status of all the properties belonging to this
    propstat element.
    """)

    def __call__():
        """Render this propstat object to a etree XML element.
        """


class IResponse(interface.Interface):
    """Helper object to render a response XML element.
    """

    href = interface.Attribute("""String representation of the HTTP URL
    pointing to the resource that this response element represents.
    """)

    status = interface.Attribute("""Optional integer status code for this
    response element.
    """)

    error = interface.Attribute("""List of etree elements describing the
    error conditions of all the properties contained within an instance of
    this response XML element.
    """)

    responsedescription = interface.Attribute("""String containing readable
    information about this response relative to the request or result.
    """)

    location = interface.Attribute("""The "Location" HTTP header for use with
    some status codes like 201 and 300. This value should be set if any of
    status codes contained within this response XML element are required to
    have a HTTP "Location" header.
    """)

    def addPropstats(status, propstat):
        """Add a IPropstat instance to this response. This propstat will
        rendered with a status of 'status'.
        """

    def addProperty(status, element):
        """Add a etree.Element object to this response XML element. The property
        will be added within the propstat element that registered under the
        status code.
        """

    def __call__():
        """Render this response object to an etree element.
        """


class IMultiStatus(interface.Interface):

    responses = interface.Attribute("""List of IResponse objects that make
    all the responses contained within this multistatus XML element.
    """)

    responsedescription = interface.Attribute("""String containing a readable
    informatino about the status of all the responses belonging to this
    multistatus element.
    """)

    def __call__():
        """Render this multistatus object to an etree element.
        """

################################################################################
#
# Some helper methods. Which includes:
#
#  - makeelement(namespace, tagname, text_or_el = None)
#
#  - makedavelement(tagname, text_or_el = None)
#
#  - makestatuselement(status)
#
#  - parseEtreeTag(tag)
#
################################################################################

def makeelement(namespace, tagname, text_or_el = None):
    etree = z3c.etree.getEngine()
    el = etree.Element(etree.QName(namespace, tagname))
    if isinstance(text_or_el, (str, unicode)):
        el.text = text_or_el
    elif text_or_el is not None:
        el.append(text_or_el)

    return el


def makedavelement(tagname, text_or_el = None):
    """
      >>> etree.tostring(makedavelement('foo')) #doctest:+XMLDATA
      '<foo xmlns="DAV:" />'

      >>> etree.tostring(makedavelement('foo', 'foo content')) #doctest:+XMLDATA
      '<foo xmlns="DAV:">foo content</foo>'
    """
    return makeelement('DAV:', tagname, text_or_el)


def makestatuselement(status):
    """
      >>> etree.tostring(makestatuselement(200)) #doctest:+XMLDATA
      '<status xmlns="DAV:">HTTP/1.1 200 Ok</status>'

      >>> etree.tostring(makestatuselement(200L)) #doctest:+XMLDATA
      '<status xmlns="DAV:">HTTP/1.1 200 Ok</status>'

    Do we want this?

      >>> etree.tostring(makestatuselement('XXX')) #doctest:+XMLDATA
      '<status xmlns="DAV:">XXX</status>'
    """
    if isinstance(status, (int, long)):
        status = 'HTTP/1.1 %d %s' %(status, status_reasons[status])

    return makedavelement('status', status)


def parseEtreeTag(tag):
    """Return namespace, tagname pair.

      >>> parseEtreeTag('{DAV:}prop')
      ['DAV:', 'prop']

      >>> parseEtreeTag('{}prop')
      ['', 'prop']

      >>> parseEtreeTag('prop')
      (None, 'prop')

    """
    if tag[0] == "{":
        return tag[1:].split("}")
    return None, tag

################################################################################
#
# Helper utilities for generating some common XML responses.
#
################################################################################

class Propstat(object):
    """Simple propstat xml handler.

      >>> from zope.interface.verify import verifyObject
      >>> pstat = Propstat()
      >>> verifyObject(IPropstat, pstat)
      True
      >>> pstat.status = 200

      >>> pstat.properties.append(makedavelement(u'testprop', u'Test Property'))
      >>> print etree.tostring(pstat()) #doctest:+XMLDATA
      <propstat xmlns="DAV:">
        <prop>
          <testprop>Test Property</testprop>
        </prop>
        <status>HTTP/1.1 200 Ok</status>
      </propstat>

      >>> pstat.properties.append(makedavelement(u'test2', u'Second Test'))
      >>> print etree.tostring(pstat()) #doctest:+XMLDATA
      <propstat xmlns="DAV:">
        <prop>
          <testprop>Test Property</testprop>
          <test2>Second Test</test2>
        </prop>
        <status>HTTP/1.1 200 Ok</status>
      </propstat>

      >>> pstat.responsedescription = u'This is ok'
      >>> print etree.tostring(pstat()) #doctest:+XMLDATA
      <propstat xmlns="DAV:">
        <prop>
          <testprop>Test Property</testprop>
          <test2>Second Test</test2>
        </prop>
        <status>HTTP/1.1 200 Ok</status>
        <responsedescription>This is ok</responsedescription>
      </propstat>

      >>> pstat.error = [makedavelement(u'precondition-error')]
      >>> print etree.tostring(pstat()) #doctest:+XMLDATA
      <propstat xmlns="DAV:">
        <prop>
          <testprop>Test Property</testprop>
          <test2>Second Test</test2>
        </prop>
        <status>HTTP/1.1 200 Ok</status>
        <error>
          <precondition-error />
        </error>
        <responsedescription>This is ok</responsedescription>
      </propstat>

    The status must be set.

      >>> pstat = Propstat()
      >>> pstat()
      Traceback (most recent call last):
      ...
      ValueError: Must set status before rendering a propstat.

    """
    interface.implements(IPropstat)

    def __init__(self):
        # etree.Element
        self.properties = []
        # int or string
        self.status = None

        # etree.Element
        self.error = []
        # text
        self.responsedescription = ""

    def __call__(self):
        if self.status is None:
            raise ValueError("Must set status before rendering a propstat.")

        propstatel = makedavelement('propstat')
        propel = makedavelement('prop')
        propstatel.append(propel)

        for prop in self.properties:
            propel.append(prop)

        propstatel.append(makestatuselement(self.status))

        for error in self.error:
            propstatel.append(makedavelement('error', error))

        if self.responsedescription:
            propstatel.append(makedavelement('responsedescription',
                                             self.responsedescription))

        return propstatel


class Response(object):
    """WebDAV response XML element

    We need a URL to initialize the Response object, /container is a good
    choice.

      >>> from zope.interface.verify import verifyObject
      >>> response = Response('/container')
      >>> verifyObject(IResponse, response)
      True

      >>> print etree.tostring(response()) #doctest:+XMLDATA
      <response xmlns="DAV:">
        <href>/container</href>
      </response>

      >>> response.status = 200
      >>> response.href.append('/container2')

      >>> print etree.tostring(response()) #doctest:+XMLDATA
      <response xmlns="DAV:">
        <href>/container</href>
        <href>/container2</href>
        <status>HTTP/1.1 200 Ok</status>
      </response>

    The response XML element can contain a number of Propstat elements
    organized by status code.

      >>> response = Response('/container')
      >>> pstat1 = Propstat()
      >>> pstat1.status = 200
      >>> pstat1.properties.append(makedavelement(u'test1', u'test one'))
      >>> response.addPropstats(200, pstat1)
      >>> pstat2 = Propstat()
      >>> pstat2.status = 404
      >>> pstat2.properties.append(makedavelement(u'test2'))
      >>> response.addPropstats(404, pstat2)

      >>> print etree.tostring(response()) #doctest:+XMLDATA
      <response xmlns="DAV:">
        <href>/container</href>
        <propstat>
          <prop>
            <test1>test one</test1>
          </prop>
          <status>HTTP/1.1 200 Ok</status>
        </propstat>
        <propstat>
          <prop>
            <test2 />
          </prop>
          <status>HTTP/1.1 404 Not Found</status>
        </propstat>
      </response>

      >>> response.error = [makedavelement(u'precondition-failed')]
      >>> print etree.tostring(response()) #doctest:+XMLDATA
      <response xmlns="DAV:">
        <href>/container</href>
        <propstat>
          <prop>
            <test1>test one</test1>
          </prop>
          <status>HTTP/1.1 200 Ok</status>
        </propstat>
        <propstat>
          <prop>
            <test2 />
          </prop>
          <status>HTTP/1.1 404 Not Found</status>
        </propstat>
        <error>
          <precondition-failed />
        </error>
      </response>

      >>> response.responsedescription = u'webdav description'
      >>> print etree.tostring(response()) #doctest:+XMLDATA
      <response xmlns="DAV:">
        <href>/container</href>
        <propstat>
          <prop>
            <test1>test one</test1>
          </prop>
          <status>HTTP/1.1 200 Ok</status>
        </propstat>
        <propstat>
          <prop>
            <test2 />
          </prop>
          <status>HTTP/1.1 404 Not Found</status>
        </propstat>
        <error>
          <precondition-failed />
        </error>
        <responsedescription>webdav description</responsedescription>
      </response>

      >>> response.location = '/container2'
      >>> print etree.tostring(response()) #doctest:+XMLDATA
      <response xmlns="DAV:">
        <href>/container</href>
        <propstat>
          <prop>
            <test1>test one</test1>
          </prop>
          <status>HTTP/1.1 200 Ok</status>
        </propstat>
        <propstat>
          <prop>
            <test2 />
          </prop>
          <status>HTTP/1.1 404 Not Found</status>
        </propstat>
        <error>
          <precondition-failed />
        </error>
        <responsedescription>webdav description</responsedescription>
        <location>
          <href>/container2</href>
        </location>
      </response>

      >>> response = Response('/container1')
      >>> response.href.append('/container2')
      >>> response.addPropstats(200, Propstat())
      >>> etree.tostring(response())
      Traceback (most recent call last):
      ...
      ValueError: Response object is in an invalid state.

      >>> response = Response('/container1')
      >>> response.status = 200
      >>> response.addPropstats(200, Propstat())
      >>> etree.tostring(response())
      Traceback (most recent call last):
      ...
      ValueError: Response object is in an invalid state.

    Now the must handly method of all the addProperty mehtod:

      >>> resp = Response('/container')
      >>> resp.addProperty(200, makedavelement(u'testprop', u'Test Property'))
      >>> print etree.tostring(resp()) #doctest:+XMLDATA
      <response xmlns="DAV:">
        <href>/container</href>
        <propstat>
          <prop>
            <testprop>Test Property</testprop>
          </prop>
          <status>HTTP/1.1 200 Ok</status>
        </propstat>
      </response>

      >>> resp.addProperty(200, makedavelement(u'testprop2',
      ...                                      u'Test Property Two'))
      >>> print etree.tostring(resp()) #doctest:+XMLDATA
      <response xmlns="DAV:">
        <href>/container</href>
        <propstat>
          <prop>
            <testprop>Test Property</testprop>
            <testprop2>Test Property Two</testprop2>
          </prop>
          <status>HTTP/1.1 200 Ok</status>
        </propstat>
      </response>

      >>> resp.addProperty(404, makedavelement(u'missing'))
      >>> print etree.tostring(resp()) #doctest:+XMLDATA
      <response xmlns="DAV:">
        <href>/container</href>
        <propstat>
          <prop>
            <testprop>Test Property</testprop>
            <testprop2>Test Property Two</testprop2>
          </prop>
          <status>HTTP/1.1 200 Ok</status>
          </propstat>
          <propstat>
            <prop>
              <missing />
            </prop>
            <status>HTTP/1.1 404 Not Found</status>
         </propstat>
       </response>

    """
    interface.implements(IResponse)

    def __init__(self, href):
        self.href = [href]
        self.status = None
        self._propstats = {} # status -> list of propstat Propstat object

        self.error = []
        self.responsedescription = ""
        self.location = None

    def getPropstat(self, status):
        if status not in self._propstats:
            self._propstats[status] = Propstat()
        return self._propstats[status]

    def addPropstats(self, status, propstat): # use getPropstats instead.
        self._propstats[status] = propstat

    def addProperty(self, status, element):
        try:
            propstat = self._propstats[status]
        except KeyError:
            propstat = self._propstats[status] = Propstat()

        propstat.properties.append(element)

    def __call__(self):
        if (len(self.href) > 1 or self.status is not None) and self._propstats:
            raise ValueError, "Response object is in an invalid state."

        respel = makedavelement('response')
        respel.append(makedavelement('href', self.href[0]))

        if self.status is not None:
            for href in self.href[1:]:
                respel.append(makedavelement('href', href))

            respel.append(makestatuselement(self.status))
        else:
            for status, propstat in self._propstats.items():
                propstat.status = status
                respel.append(propstat())

        for error in self.error:
            respel.append(makedavelement('error', error))

        if self.responsedescription:
            respel.append(makedavelement('responsedescription',
                                         self.responsedescription))

        if self.location is not None:
            respel.append(makedavelement('location',
                                         makedavelement('href', self.location)))

        return respel


class MultiStatus(object):
    """Multistatus element generation

      >>> from zope.interface.verify import verifyObject
      >>> ms = MultiStatus()
      >>> verifyObject(IMultiStatus, ms)
      True

      >>> print etree.tostring(ms()) #doctest:+XMLDATA
      <ns0:multistatus xmlns:ns0="DAV:" />

      >>> ms.responsedescription = u'simple description'
      >>> print etree.tostring(ms()) #doctest:+XMLDATA
      <multistatus xmlns="DAV:">
        <responsedescription>simple description</responsedescription>
      </multistatus>

      >>> response = Response('/container')
      >>> ms.responses.append(response)
      >>> print etree.tostring(ms()) #doctest:+XMLDATA
      <multistatus xmlns="DAV:">
        <response>
          <href>/container</href>
        </response>
        <responsedescription>simple description</responsedescription>
      </multistatus>

      >>> pstat1 = Propstat()
      >>> pstat1.status = 200
      >>> pstat1.properties.append(makedavelement(u'test1', u'test one'))
      >>> response.addPropstats(200, pstat1)
      >>> print etree.tostring(ms()) #doctest:+XMLDATA
      <multistatus xmlns="DAV:">
        <response>
          <href>/container</href>
          <propstat>
            <prop>
              <test1>test one</test1>
            </prop>
            <status>HTTP/1.1 200 Ok</status>
          </propstat>
        </response>
        <responsedescription>simple description</responsedescription>
      </multistatus>

      >>> response2 = Response('/container2')
      >>> pstat2 = Propstat()
      >>> pstat2.status = 404
      >>> pstat2.properties.append(makedavelement(u'test2'))
      >>> response2.addPropstats(404, pstat2)
      >>> ms.responses.append(response2)
      >>> print etree.tostring(ms()) #doctest:+XMLDATA
      <multistatus xmlns="DAV:">
        <response>
          <href>/container</href>
          <propstat>
            <prop>
              <test1>test one</test1>
            </prop>
            <status>HTTP/1.1 200 Ok</status>
          </propstat>
        </response>
        <response>
          <href>/container2</href>
          <propstat>
            <prop>
              <test2 />
            </prop>
            <status>HTTP/1.1 404 Not Found</status>
          </propstat>
        </response>
        <responsedescription>simple description</responsedescription>
      </multistatus>

    """
    interface.implements(IMultiStatus)

    def __init__(self):
        # list of Response objects
        self.responses = []
        # text
        self.responsedescription = ""

    def __call__(self):
        etree = z3c.etree.getEngine()
        el = etree.Element(etree.QName('DAV:', 'multistatus'))
        for response in self.responses:
            el.append(response())

        if self.responsedescription:
            el.append(makedavelement('responsedescription',
                                     self.responsedescription))

        return el

################################################################################
#
# Some other miscellanous helpful methods
#
################################################################################

def getObjectURL(ob, req):
    """Return the URL for the object `ob`.

    If the object is a container and the url doesn't end in slash '/' then
    append a slash to the url.
    """
    url = zope.component.getMultiAdapter((ob, req), IAbsoluteURL)()
    if IReadContainer.providedBy(ob) and url[-1] != "/":
        url += "/"

    return url
