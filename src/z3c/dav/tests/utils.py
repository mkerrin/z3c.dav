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
"""Miscellanous methods used for testing different parts of the WebDAV
implementation.

$Id$
"""
__docformat__ = 'restructuredtext'

from zope.publisher.http import status_reasons
from z3c.etree.testing import assertXMLEqual

class TestMultiStatusBody(object):
    #
    # If you need to use any methods in this just make sure that your test case
    # class extends this one.
    #

    def assertMSPropertyValue(self, response, proptag, status = 200,
                              tag = None, text_value = None,
                              prop_element = None):
        # For the XML response element make sure that the proptag belongs
        # to the propstat element that has the given status.
        #   - response - etree XML element
        #   - proptag - tag name of the property we are testing
        #   - status - integre status code
        #   - tag - 
        #   - text_value -
        #   - propelement - etree Element that we compare with the property
        #                   using z3c.etree.testing.assertXMLEqual
        self.assertEqual(response.tag, "{DAV:}response")

        # set to true if we found the property, under the correct status code
        found_property = False

        propstats = response.findall("{DAV:}propstat")
        for propstat in propstats:
            statusresp = propstat.findall("{DAV:}status")
            self.assertEqual(len(statusresp), 1)

            if statusresp[0].text == "HTTP/1.1 %d %s" %(
                status, status_reasons[status]):
                # make sure that proptag is in this propstat element
                props = propstat.findall("{DAV:}prop/%s" % proptag)
                self.assertEqual(len(props), 1)
                prop = props[0]

                # now test the the tag and text match this propstat element
                if tag is not None:
                    ## XXX - this is not right.
                    ## self.assertEqual(len(prop), 1)
                    self.assertEqual(prop[0].tag, tag)
                else:
                    self.assertEqual(len(prop), 0)
                self.assertEqual(prop.text, text_value)

                if prop_element is not None:
                    assertXMLEqual(prop, prop_element)

                found_property = True
            else:
                # make sure that proptag is NOT in this propstat element
                props = propstat.findall("{DAV:}prop/%s" % proptag)
                self.assertEqual(len(props), 0)

        self.assert_(
            found_property,
            "The property %s doesn't exist for the status code %d" %(proptag,
                                                                     status))
