##############################################################################
# Copyright (c) 2007 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
##############################################################################
"""
The definition of the `If` header is [10.4.2]:

   If = "If" ":" ( 1*No-tag-list | 1*Tagged-list )

   No-tag-list = List
   Tagged-list = Resource-Tag 1*List

   List = "(" 1*Condition ")"
   Condition = ["Not"] (State-token | "[" entity-tag "]")
   ; entity-tag: see Section 3.11 of [RFC2616]
   ; No LWS allowed between "[", entity-tag and "]"

   State-token = Coded-URL

   Resource-Tag = "<" Simple-ref ">"
   ; Simple-ref: see Section 8.3
   ; No LWS allowed in Resource-Tag

In order to evaluate this header we must following these rules [10.4.3]:

  Each List production describes a series of conditions.  The whole
  list evaluates to true if and only if each condition evaluates to
  true (that is, the list represents a logical conjunction of
  Conditions).

  Each No-tag-list and Tagged-list production may contain one or more
  Lists.  They evaluate to true if and only if any of the contained
  lists evaluates to true (that is, if there's more than one List, that
  List sequence represents a logical disjunction of the Lists).

  Finally, the whole If header evaluates to true if and only if at
  least one of the No-tag-list or Tagged-list productions evaluates to
  true.  If the header evaluates to false, the server MUST reject the
  request with a 412 (Precondition Failed) status.  Otherwise,
  execution of the request can proceed as if the header wasn't present.

"""
import re
import urlparse
from cStringIO import StringIO

import zope.component
import zope.interface
import zope.schema
import zope.traversing.api
import zope.app.http.interfaces
import z3c.dav.coreproperties
import z3c.dav.interfaces
import z3c.conditionalviews.interfaces

# Resource-Tag = "<" Simple-ref ">"
resource_tag = re.compile(r"<(?P<resource>.+?)>")
# Condition = ["Not"] (State-token | "[" entity-tag "]")
condition = re.compile(
  r"(?P<notted>not)?\s*(<(?P<state_token>.*?)>|\[(?P<entity_tag>\S+?)\])+",
  re.I)

STATE_ANNOTS = "z3c.conditionalviews.stateresults"

class IStateTokens(zope.interface.Interface):

    schemes = zope.schema.List(
        title = u"State token schemes",
        description = \
                    u"List of possible state schemes producible by the system")

    tokens = zope.schema.List(
        title = u"State tokens",
        description = u"List of the current state tokens.")


class IFStateToken(object):

    def __init__(self, scheme, token):
        self.scheme = scheme
        self.token = token


class ListCondition(object):

    def __init__(self, notted = False, state_token = None, entity_tag = None):
        self.notted = notted
        self.state_token = state_token
        self.entity_tag = entity_tag


class IFValidator(object):
    """

      >>> import zope.interface.verify
      >>> from zope.publisher.interfaces import IPublishTraverse
      >>> from zope.publisher.browser import TestRequest
      >>> from zope.location.interfaces import ILocationInfo
      >>> from zope.app.publication.zopepublication import ZopePublication
      >>> from zope.security.proxy import removeSecurityProxy

    The validator is a utility that implements the IF header conditional
    request as specified in the WebDAV specification.

      >>> validator = IFValidator()
      >>> zope.interface.verify.verifyObject(
      ...    z3c.conditionalviews.interfaces.IHTTPValidator, validator)
      True

    We can only evaluate this request if the request contains an `IF` header.

      >>> request = TestRequest()
      >>> validator.evaluate(None, request, None)
      False
      >>> request = TestRequest(environ = {'IF': '(<DAV:no-lock>)'})
      >>> validator.evaluate(None, request, None)
      True

    We need to set up following adapters for the validator to work.

      >>> class PhysicallyLocatable(object):
      ...    zope.interface.implements(ILocationInfo)
      ...    def __init__(self, context):
      ...        self.context = context
      ...    def getRoot(self):
      ...        return root
      ...    def getPath(self):
      ...        return '/' + self.context.__name__
      >>> zope.component.getGlobalSiteManager().registerAdapter(
      ...    PhysicallyLocatable, (Demo,))

    We store the results of the parsing of the state tokens in a dictionary
    structure. Its keys are the path to the object and its value is a
    dictionary of locktokens and whether or not the `NOT` keyword was present.

      >>> def getStateResults(request):
      ...    reqannot = zope.annotation.interfaces.IAnnotations(request)
      ...    return reqannot.get(STATE_ANNOTS, {})

    Firstly nothing matches the <DAV:no-lock> state token.

      >>> resource = Demo('test')
      >>> validator.valid(resource, request, None)
      False
      >>> resource._tokens = ['test']
      >>> validator.valid(resource, request, None)
      False

    The invalid status for this protocol is 412, for all methods.

      >>> validator.invalidStatus(resource, request, None)
      412

    Non-tagged lists
    ================

    Entity tag condition
    --------------------

      >>> ETag.etag = 'xx'
      >>> request = TestRequest(environ = {'IF': '(["xx"])'})
      >>> validator.valid(resource, request, None)
      True
      >>> request._environ['IF'] = '(["xx"] ["yy"])'
      >>> validator.valid(resource, request, None)
      False
      >>> request._environ['IF'] = '(["xx"])(["yy"])'
      >>> validator.valid(resource, request, None)
      True
      >>> request._environ['IF'] = '(["yy"])(["xx"])'
      >>> validator.valid(resource, request, None)
      True

      >>> request._environ['IF'] = '([W/"xx"])'
      >>> validator.valid(resource, request, None)
      True

    The request object gets annotated with the results of the matching any
    state tokens, so that I only need to parse this data once. But since only
    entity tags have been passed so far the request object will not be
    annotated with the results of the state tokens.

      >>> getStateResults(request)
      {}

    Not - entity tag conditions
    ---------------------------

      >>> request = TestRequest(environ = {'IF': '(not ["xx"])'})
      >>> validator.valid(resource, request, None)
      False
      >>> request._environ['IF'] = '(not ["xx"] ["yy"])'
      >>> validator.valid(resource, request, None)
      False
      >>> request._environ['IF'] = '(not ["xx"])(["yy"])'
      >>> validator.valid(resource, request, None)
      False
      >>> request._environ['IF'] = '(not ["yy"])'
      >>> validator.valid(resource, request, None)
      True

      >>> request._environ['IF'] = '(NOT [W/"xx"])'
      >>> validator.valid(resource, request, None)
      False

      >>> getStateResults(request)
      {}

    State-tokens
    ------------

    We collect the parsed state tokens from the `IF` as we find them and
    store them as an annotation on the request object.

      >>> request = TestRequest(environ = {'IF': '(<ns:locktoken>)'})
      >>> validator.valid(resource, request, None)
      False
      >>> getStateResults(request)
      {'/test': {'ns:locktoken': False}}

      >>> resource._tokens = ['ns:locktoken']
      >>> validator.valid(resource, request, None)
      True
      >>> getStateResults(request)
      {'/test': {'ns:locktoken': False}}

    Namespace with digit. Some versions of Python fail to parse the following
    lock tokens. The problem is in `urlparse.urlparse' which is known to be
    broken in versions 2.7 and 2.7.1 of Python.

      >>> request = TestRequest(environ = {'IF': '(<ns:0.916441024976-0.164634675389-00105A989226:1308916796.245>)'})
      >>> validator.valid(resource, request, None)
      False
      >>> getStateResults(request)
      {'/test': {'ns:0.916441024976-0.164634675389-00105A989226:1308916796.245': False}}

      >>> request = TestRequest(environ = {'IF': '(<ns:0.916441024976-0.164634675389-00105A989226:1308916796.245>)'})
      >>> resource._tokens = ['ns:0.916441024976-0.164634675389-00105A989226:1308916796.245']

    This is the test that breaks on the broken versions.

      >>> validator.valid(resource, request, None)
      True
      >>> getStateResults(request)
      {'/test': {'ns:0.916441024976-0.164634675389-00105A989226:1308916796.245': False}}

    If there are multiple locktokens associated with a resource, we only
    are interested in the token that is represented in the IF header, so we
    only have one entry in the state results variable.

      >>> request = TestRequest(environ = {'IF': '(<ns:locktoken>)'})
      >>> resource._tokens = ['ns:locktoken', 'ns:nolocktoken']
      >>> validator.valid(resource, request, None)
      True
      >>> getStateResults(request)
      {'/test': {'ns:locktoken': False}}
      >>> request._environ['IF'] = '(NOT <ns:locktoken>)'
      >>> validator.valid(resource, request, None)
      False
      >>> getStateResults(request)
      {'/test': {'ns:locktoken': True}}

      >>> request._environ['IF'] = '(NOT <ns:invalidlocktoken>)'
      >>> validator.valid(resource, request, None)
      True
      >>> getStateResults(request)
      {'/test': {'ns:invalidlocktoken': True}}


    Combined entity / state tokens
    ------------------------------

      >>> request = TestRequest(environ = {'IF': '(<ns:locktoken> ["xx"])'})
      >>> validator.valid(resource, request, None)
      True
      >>> resource._tokens = ['ns:nolocktoken']
      >>> validator.valid(resource, request, None)
      False

      >>> request._environ['IF'] = '(<ns:nolocktoken> ["xx"]) (["yy"])'
      >>> validator.valid(resource, request, None)
      True

      >>> request._environ['IF'] = '(<ns:nolocktoken> ["yy"]) (["xx"])'
      >>> validator.valid(resource, request, None)
      True

    Now if the resource isn't locked, that is it has no state tokens
    associated with it, then the request must be valid.

      >>> resource._tokens = []
      >>> request._environ['IF'] = '(<ns:locktoken>)'
      >>> validator.valid(resource, request, None)
      True
      >>> getStateResults(request)
      {'/test': {'ns:locktoken': False}}

    But we if the condition in the state token contains a state token belong
    to the URL scheme that we don't know about then the condition false, and
    in this case the header evaluation fails.

      >>> request._environ['IF'] = '(<DAV:no-lock>)'
      >>> validator.valid(resource, request, None)
      False

    Resources
    =========

    We now need to test the situation when a resource is specified in the
    the `IF` header. We need to define a context here so that we can find
    the specified resource from the header. Make the context implement
    IPublishTraverse so that we know how to traverse to the next segment
    in the path.

    Setup up three content object. One is the context for validation, the
    second is a locked resource, and the last is the root of the site.

      >>> root = Demo('')
      >>> locked = Demo('locked')
      >>> root.add(locked)
      >>> demo = Demo('demo')
      >>> root.add(demo)

    The request needs more setup in order for the traversal to work. We
    need and a publication object and since our TestRequets object extends
    the BrowserRequest pretend that the method is `PUT` so that the
    traversal doesn't try and find a default view for the resource. This
    would require more setup.

      >>> request.setPublication(ZopePublication(None))
      >>> request._environ['REQUEST_METHOD'] = 'PUT'

    Test that we can find the locked resource from the demo resource.

      >>> resource = validator.get_resource(
      ...    demo, request, 'http://localhost/locked')
      >>> resource.__name__
      'locked'
      >>> resource = validator.get_resource(demo, request, '/locked')
      >>> resource.__name__
      'locked'

    Setup all the state tokens for all content objects to be their `__name__`
    attribute.

      >>> demo._tokens = ['ns:demo']
      >>> locked._tokens = ['ns:locked']
      >>> request._environ['IF'] = '<http://localhost/locked> (<ns:demo>)'
      >>> validator.valid(demo, request, None)
      False
      >>> request._environ['IF'] = '<http://localhost/locked> (<ns:locked>)'
      >>> validator.valid(demo, request, None)
      True

    If a specified resource does not exist then the only way for the IF header
    to match is for the state tokens to be `(Not <ns:locktoken>)`.

      >>> request._environ['IF'] = '<http://localhost/missing> (<ns:locked>)'
      >>> validator.valid(demo, request, None)
      True

    In this case when we try to match against `(Not <ns:locked>)`
    but we stored state is still matched.

      >>> request._environ['IF'] = '<http://localhost/missing> (Not <ns:locked>)'
      >>> validator.valid(demo, request, None)
      False
      >>> getStateResults(request)
      {'/missing': {'ns:locked': True}}

    If we have specify multiple resources then we need to parse the
    whole `IF` header so that the state results method knows about the
    different resources.

      >>> request._environ['IF'] = '</demo> (<ns:demo>) </locked> (<ns:notlocked>)'
      >>> validator.valid(demo, request, None)
      True
      >>> getStateResults(request)
      {'/locked': {'ns:notlocked': False}, '/demo': {'ns:demo': False}}

    Null resources
    ==============

      >>> import zope.app.http.put

    When validating certain tagged-list productions we can get back
    zope.app.http.interfaces.INullResource objects from the get_resource
    method, plus the original context can be a null resource too.

      >>> class Demo2(Demo):
      ...    def publishTraverse(self, request, name):
      ...        child = self.children.get(name, None)
      ...        if child:
      ...            return child
      ...        if request.method in ('PUT', 'LOCK', 'MKCOL'):
      ...            return zope.app.http.put.NullResource(self, name)
      ...        raise zope.publisher.interfaces.NotFound(self, name, request)

      >>> root2 = Demo2('')
      >>> locked2 = Demo2('locked')
      >>> root2.add(locked2)
      >>> demo2 = Demo2('demo')
      >>> root2.add(demo2)

      >>> class PhysicallyLocatable2(PhysicallyLocatable):
      ...    def getRoot(self):
      ...        return root2
      >>> zope.component.getGlobalSiteManager().registerAdapter(
      ...    PhysicallyLocatable2, (Demo2,))

    Now generate a request with an IF header, and LOCK method that fails to
    find a resource, we get a NullResource instead of a NotFound exception.

      >>> request = TestRequest(environ = {'IF': '</missing> (<ns:locked>)',
      ...                                  'REQUEST_METHOD': 'LOCK'})
      >>> request.setPublication(ZopePublication(None))

      >>> missingdemo2 = validator.get_resource(demo2, request, '/missing')
      >>> missingdemo2 = removeSecurityProxy(missingdemo2)
      >>> missingdemo2  #doctest:+ELLIPSIS
      <zope.app.http.put.NullResource object at ...>

    Now this request evaluates to true and we take the path from the `IF`
    header and store the state tokens in the request annotation against
    this path.

      >>> validator.valid(demo2, request, None)
      True
      >>> getStateResults(request)
      {'/missing': {'ns:locked': False}}
      >>> matchesIfHeader(demo2, request)
      True
      >>> matchesIfHeader(missingdemo2, request)
      True

    The demo object is not locked so it automatically matches the if header.

      >>> root2._tokens = ['ns:locked']
      >>> validator.valid(demo2, request, None)
      True
      >>> getStateResults(request)
      {'/missing': {'ns:locked': False}}
      >>> matchesIfHeader(demo2, request)
      True

    Even though the correct lock token is supplied in the `IF` header for the
    root2 resource, it is on for an alternative resource and the root object
    is not within the scope of that indirect lock token.

      >>> matchesIfHeader(root2, request)
      False

      >>> root2._tokens = ['ns:otherlocktoken']
      >>> validator.valid(demo2, request, None)
      True
      >>> getStateResults(request)
      {'/missing': {'ns:locked': False}}

      >>> validator.valid(missingdemo2, request, None)
      True
      >>> matchesIfHeader(missingdemo2, request)
      True

      >>> root2._tokens = ['ns:locked']
      >>> validator.valid(missingdemo2, request, None)
      True

    When a null resource is created it if sometimes replaced by an other
    persistent object. If this is a PUT method then the object created
    should be locked with an indirect lock token, associated with the same
    root token as the folder, so as the matchesIfHeader method returns
    True.

      >>> demo3 = Demo('missing')
      >>> root2.add(demo3)
      >>> matchesIfHeader(demo3, request)
      True

    Invalid data
    ============

    When the if header fails to parse then the request should default to
    True, but if we matched any resources / state tokens before the parse
    error then we should still store this.

    Need to clear the request annotation for these tests to run.

      >>> request = TestRequest(environ = {'IF': '</ddd> (hi)'})
      >>> request.setPublication(ZopePublication(None))
      >>> request._environ['REQUEST_METHOD'] = 'PUT'

      >>> validator.valid(demo, request, None)
      Traceback (most recent call last):
      ...
      BadRequest: <zope.publisher.browser.TestRequest instance URL=http://127.0.0.1>, "Invalid IF header: unclosed '(' list production"
      >>> getStateResults(request)
      {}

    The IF header parses until the list condition which is missing the angular
    brackets.

      >>> request._environ['IF'] = '</ddd> (<hi>) (there)'
      >>> validator.valid(demo, request, None)
      Traceback (most recent call last):
      ...
      BadRequest: <zope.publisher.browser.TestRequest instance URL=http://127.0.0.1>, "Invalid IF header: unclosed '(' list production"
      >>> getStateResults(request)
      {}

    Try what happens when there is no starting '(' for a list.

      >>> request._environ['IF'] = '</ddd> <hi>'
      >>> validator.valid(demo, request, None)
      Traceback (most recent call last):
      ...
      BadRequest: <zope.publisher.browser.TestRequest instance URL=http://127.0.0.1>, "Invalid IF header: unexcepted charactor found, expected a '('"
      >>> getStateResults(request)
      {}

    Expected a '(' in the IF header but the header was already parsed.

      >>> request._environ['IF'] = '</ddd> (<hi>) <hi>'
      >>> validator.valid(demo, request, None)
      Traceback (most recent call last):
      ...
      BadRequest: <zope.publisher.browser.TestRequest instance URL=http://127.0.0.1>, "Invalid IF header: unexcepted charactor found, expected a '('"
      >>> getStateResults(request)
      {}

    Expected a '(' in the IF header.

      >>> request._environ['IF'] = '</ddd> (<hi>) hi'
      >>> validator.valid(demo, request, None)
      Traceback (most recent call last):
      ...
      BadRequest: <zope.publisher.browser.TestRequest instance URL=http://127.0.0.1>, "Invalid IF header: unexcepted charactor found, expected a '('"
      >>> getStateResults(request)
      {}

    The specification for the `If' header requires at list one condition be
    present.

      >>> request._environ['IF'] = '</ddd> ()'
      >>> validator.valid(demo, request, None)
      Traceback (most recent call last):
      ...
      BadRequest: <zope.publisher.browser.TestRequest instance URL=http://127.0.0.1>, 'Invalid IF header: no conditions present'

      >>> request._environ['IF'] = '()'
      >>> validator.valid(demo, request, None)
      Traceback (most recent call last):
      ...
      BadRequest: <zope.publisher.browser.TestRequest instance URL=http://127.0.0.1>, 'Invalid IF header: no conditions present'


    matchesIfHeader method
    ======================

    Test the state of the context to see if matches the list of states
    supplied in the `IF` header.

      >>> request = TestRequest(environ = {'REQUEST_METHOD': 'PUT'})
      >>> request.setPublication(ZopePublication(None))

    When the resource is not locked and hence are no state tokens for the
    object then this method returns True

      >>> matchesIfHeader(root, request)
      True

    When the resource is locked, and there is no `IF` header then we haven't
    matched anything.

      >>> matchesIfHeader(demo, request)
      False

    Specifying a `DAV:no-lock` state token always causes the validation
    to succeed, but the locktoken is never in the header so we don't match it.

      >>> request._environ['IF'] = '</demo> (NOT <DAV:no-lock>)'
      >>> validator.valid(demo, request, None)
      True
      >>> matchesIfHeader(demo, request)
      False

    The parsed state token in the `IF` header for the demo object matches
    the current state token.

      >>> demo._tokens = ['ns:test'] # setup the state tokens
      >>> request._environ['IF'] = '</demo> (<ns:test>)'
      >>> validator.valid(demo, request, None)
      True
      >>> matchesIfHeader(demo, request)
      True

    The parsed state token for the demo object does not match that in the
    `IF` header. Note that we needed to specify the <DAV:no-lock> in order
    for the request to be valid. In this case we the request will be
    executed but there are event handlers that might call the matchesIfHeader
    which does return False since we don't have any locktoken.

      >>> request._environ['IF'] = '</demo> (<ns:falsetest>) (NOT <DAV:no-lock>)'
      >>> validator.valid(demo, request, None)
      True
      >>> matchesIfHeader(demo, request)
      False

    The state token for the root object matches that in the `IF` header. And
    this as special meaning for any children of the root folder, if there
    state token is the same then we get a match.

      >>> root._tokens = ['ns:roottest']
      >>> request._environ['IF'] = '</> (<ns:roottest>)'
      >>> validator.valid(demo, request, None)
      True
      >>> matchesIfHeader(root, request)
      True

    Demo is locked with the state token 'test' and so doesnot validate against
    the `IF` header.

      >>> matchesIfHeader(demo, request)
      False

    Two resources are specified in the `IF` header, so the root object fails
    to match the `IF` header whereas the demo object does match.

      >>> request._environ['IF'] = '</> (<ns:falseroottest>) </demo> (<ns:test>)'
      >>> validator.valid(demo, request, None)
      True
      >>> matchesIfHeader(root, request)
      False
      >>> matchesIfHeader(demo, request)
      True

    If the demo objects is for example indirectly locked against a root, and
    its state token appears in the `IF` header for a parent object then
    the demo object matches the `IF` header.

      >>> request._environ['IF'] = '</> (<ns:roottest>)'
      >>> validator.valid(root, request, None)
      True
      >>> matchesIfHeader(root, request)
      True
      >>> matchesIfHeader(demo, request)
      False

    But if the demo object is not locked then it passes.

      >>> demo._tokens = ['ns:roottest']
      >>> validator.valid(demo, request, None)
      True
      >>> matchesIfHeader(root, request)
      True
      >>> matchesIfHeader(demo, request)
      True

      >>> root._tokens = ['notroottest']
      >>> matchesIfHeader(root, request)
      False
      >>> matchesIfHeader(demo, request)
      True

    Update response
    ===============

    After validating a request the `updateResponse' method is called. This
    does nothing.

      >>> headers = dict(request.response.getHeaders())
      >>> validator.updateResponse(demo, request, None)
      >>> dict(request.response.getHeaders()) == headers
      True

    Each cases 1
    ============

    Test case when there are no state tokens known by the system. In this
    case the request is not valid as we have no knowledge of the token passed
    in the conditional request so we can't match against it.

      >>> request._environ['IF'] = '</> (<roottest>)'
      >>> validator.valid(root, request, None)
      False

    Cleanup
    =======

      >>> zope.component.getGlobalSiteManager().unregisterAdapter(
      ...    ETag, (None, TestRequest, None))
      True
      >>> zope.component.getGlobalSiteManager().unregisterAdapter(
      ...    PhysicallyLocatable, (Demo,))
      True
      >>> zope.component.getGlobalSiteManager().unregisterAdapter(
      ...    PhysicallyLocatable2, (Demo2,))
      True

    """
    zope.interface.implements(z3c.conditionalviews.interfaces.IHTTPValidator)

    def evaluate(self, context, request, view):
        return request.getHeader("If", None) is not None

    def get_next_list(self, request):
        header = request.getHeader("If").lstrip()

        resource = None

        while header:
            rmatch = resource_tag.match(header)
            if rmatch:
                resource = rmatch.group("resource")
                header = header[rmatch.end():].lstrip()

            conditions = []

            if not header or header[0] != "(":
                raise z3c.dav.interfaces.BadRequest(
                    request, "Invalid IF header: unexcepted charactor" \
                             " found, expected a '('")
            header = header[1:].lstrip()

            while header:
                listitem = condition.match(header)
                if not listitem:
                    if header[0] != ")":
                        raise z3c.dav.interfaces.BadRequest(
                            request,
                            "Invalid IF header: unclosed '(' list production")
                    header = header[1:].lstrip()
                    break

                header = header[listitem.end():].lstrip()

                notted = bool(listitem.group("notted"))
                state_token = listitem.group("state_token")
                if state_token:
                    state_token = IFStateToken(
                        urlparse.urlparse(state_token)[0], state_token)

                entity_tag = listitem.group("entity_tag")
                if entity_tag:
                    if entity_tag[:2] == "W/":
                        entity_tag = entity_tag[2:]
                    entity_tag = entity_tag[1:-1]

                conditions.append(
                    ListCondition(notted, state_token, entity_tag))

            if not conditions:
                raise z3c.dav.interfaces.BadRequest(
                    request, "Invalid IF header: no conditions present")

            yield resource, conditions

    def get_resource(self, context, request, resource):
        environ = dict(request.environment)
        environ["PATH_INFO"] = urlparse.urlparse(resource)[2]

        req = request.__class__(StringIO(""), environ)
        req.setPublication(request.publication)

        if zope.app.http.interfaces.INullResource.providedBy(context):
            context = context.container

        root = zope.traversing.api.getRoot(context)
        return req.traverse(root)

    def valid(self, context, request, view):
        stateresults = {}
        conditionalresult = False

        for resource, conditions in self.get_next_list(request):
            if resource:
                try:
                    context = self.get_resource(context, request, resource)
                except zope.publisher.interfaces.NotFound:
                    # resource is still set so can't match the conditions
                    # against the current context.
                    context = None

            if context is None or \
                   zope.app.http.interfaces.INullResource.providedBy(context):
                path = resource and urlparse.urlparse(resource)[2]
            else:
                path = zope.traversing.api.getPath(context)

            etag = zope.component.queryMultiAdapter(
                (context, request, view),
                z3c.conditionalviews.interfaces.IETag,
                default = None)
            etag = etag and etag.etag

            states = zope.component.queryMultiAdapter(
                (context, request, view), IStateTokens, default = None)
            statetokens = states and states.tokens or []

            listresult = True
            for condition in conditions:
                # Each List production describes a series of conditions.
                # The whole list evaluates to true if and only if each
                # condition evaluates to true.
                if condition.entity_tag:
                    result = etag and \
                             etag == condition.entity_tag or False

                    if condition.notted:
                        result = not result
                elif condition.state_token:
                    # Each state token is a URL. So first we test to see
                    # if we understand the scheme of the state token
                    # supplied in this condition. If we don't understand
                    # the scheme then this condition evaluates to False.
                    if states:
                        if condition.state_token.scheme in states.schemes:
                            # Now if the context as at least one state token
                            # then we compare the state token supplied in this
                            # condition by simple string comparison.
                            if statetokens and \
                                   condition.state_token.token not in \
                                       statetokens:
                                result = False
                            else:
                                result = True
                        else:
                            # Un-known state token scheme so this condition
                            # is False.
                            result = False
                    else:
                        # No known state tokens so this condition is False as
                        # we didn't match the conditional request.
                        result = False
                    if condition.notted:
                        result = not result

                    if path is not None:
                        # There is no way we can compare the state results
                        # for this request at a later date if we don't
                        # have a path.
                        stateresults.setdefault(path, {})
                        stateresults[path][
                            condition.state_token.token] = condition.notted
                else:
                    raise TypeError(
                        "Either the entity_tag or the state_token"
                        " needs to be set on a condition")

                listresult &= result

            if listresult:
                # Each No-tag-list and Tagged-list production may contain
                # one or more Lists. They evaluate to true if and only if
                # any of the contained lists evaluates to true. That is if
                # listresult is True then the tag-lists are True.
                conditionalresult = True

        # We may have states and entity tags that failed, but we don't want
        # to reparse the if header to figure this out.
        reqannot = zope.annotation.interfaces.IAnnotations(request)
        reqannot[STATE_ANNOTS] = stateresults

        return conditionalresult

    def invalidStatus(self, context, request, view):
        return 412

    def updateResponse(self, context, request, view):
        pass # do nothing


def matchesIfHeader(context, request):
    # Test the state of the context to see if matches the list of state
    # tokens supplied in the `IF` header.
    reqannot = zope.annotation.interfaces.IAnnotations(request)
    stateresults = reqannot.get(STATE_ANNOTS, {})

    # We need to specify a None view here. This means that IStateTokens
    # adapters need to be reqistered for all views. But in some situations
    # it might be nice to restrict a state token adapter to specific views,
    # for example is the view's context is a null resource.
    states = zope.component.queryMultiAdapter(
        (context, request, None), IStateTokens, default = [])
    states = states and states.tokens
    if states:
        parsedstates = stateresults.get(
            zope.traversing.api.getPath(context), {})
        while not parsedstates and \
               getattr(context, "__parent__", None) is not None:
            # An object might be indirectly locked so we can test its parents
            # to see if any of there state tokens are listed in the `IF`
            # header.
            context = context.__parent__
            parsedstates = stateresults.get(
                zope.traversing.api.getPath(context), {})
        for locktoken in states:
            # From the spec:
            # Note that for the purpose of submitting the lock token the
            # actual form doesn't matter; what's relevant is that the
            # lock token appears in the If header, and that the If header
            # itself evaluates to true.
            if locktoken in parsedstates:
                return True
        return False

    # No state tokens so this automatically matches.
    return True


class StateTokens(object):
    """
    Default state tokens implementation.

      >>> from zope.interface.verify import verifyObject

    Simple resource content type.

      >>> class IResource(zope.interface.Interface):
      ...    'Simple resource.'
      >>> class Resource(object):
      ...    zope.interface.implements(IResource)
      ...    def __init__(self, name):
      ...        self.__name__ = name
      >>> resource = Resource('testresource')

    No activelock so we have no state tokens.

      >>> states = StateTokens(resource, None, None)
      >>> verifyObject(IStateTokens, states)
      True
      >>> states.tokens
      []

    We will register a simple active lock adapter indicating that the resource
    is locked.

      >>> class Activelock(object):
      ...    def __init__(self, context, request):
      ...        self.context = context
      ...    locktoken = ['testlocktoken']
      >>> class Lockdiscovery(object):
      ...    zope.interface.implements(z3c.dav.coreproperties.IDAVLockdiscovery)
      ...    zope.component.adapts(IResource, zope.interface.Interface)
      ...    def __init__(self, context, request):
      ...        self.context = context
      ...        self.request = request
      ...    @property
      ...    def lockdiscovery(self):
      ...        return [Activelock(self.context, self.request)]

      >>> zope.component.getGlobalSiteManager().registerAdapter(Lockdiscovery)

      >>> states.tokens
      ['testlocktoken']

    Cleanup.

      >>> zope.component.getGlobalSiteManager().unregisterAdapter(Lockdiscovery)
      True

    """
    zope.interface.implements(IStateTokens)
    zope.component.adapts(zope.interface.Interface,
                          zope.publisher.interfaces.http.IHTTPRequest,
                          zope.interface.Interface)

    def __init__(self, context, request, view):
        self.context = context
        self.request = request

    schemes = ("opaquelocktoken",)

    @property
    def tokens(self):
        lockdiscovery = zope.component.queryMultiAdapter(
            (self.context, self.request),
            z3c.dav.coreproperties.IDAVLockdiscovery)
        lockdiscovery = lockdiscovery and lockdiscovery.lockdiscovery
        locktokens = []
        if lockdiscovery is not None:
            for activelock in lockdiscovery:
                locktokens.extend(activelock.locktoken)
        return locktokens


class StateTokensForNullResource(object):
    zope.interface.implements(IStateTokens)
    zope.component.adapts(zope.app.http.interfaces.INullResource,
                          zope.publisher.interfaces.http.IHTTPRequest,
                          zope.interface.Interface)

    def __init__(self, context, request, view):
        pass

    schemes = ("opaquelocktoken",)

    tokens = []


BROWSER_METHODS = ("GET", "HEAD", "POST")

@zope.component.adapter(zope.lifecycleevent.interfaces.IObjectModifiedEvent)
def checkLockedOnModify(event):
    """
    When a content object is modified we need to check that the client
    submitted an `IF` header that corresponds with the lock.

      >>> from zope.lifecycleevent import ObjectModifiedEvent

    Some adapters needed to represent the data stored in the `IF` header,
    and the current state tokens for the content.

      >>> demofolder = DemoFolder()
      >>> demofile = Demo('demofile')
      >>> demofolder['demofile'] = demofile

    The test passes when the object is not locked.

      >>> checkLockedOnModify(ObjectModifiedEvent(demofile))

    Lock the file and setup the request annotation.

      >>> demofile._tokens = ['test']

      >>> request = zope.security.management.getInteraction().participations[0]
      >>> ReqAnnotation(request)[z3c.dav.ifvalidator.STATE_ANNOTS] = {
      ...    '/demofile': {'statetoken': True}}

      >>> demofile._tokens = ['wrongstatetoken'] # wrong token.
      >>> checkLockedOnModify(ObjectModifiedEvent(demofile)) #doctest:+ELLIPSIS
      Traceback (most recent call last):
      ...
      AlreadyLocked: <z3c.dav.tests.test_locking.Demo object at ...>: None

    With the correct lock token submitted the test passes.

      >>> demofile._tokens = ['statetoken'] # wrong token.
      >>> checkLockedOnModify(ObjectModifiedEvent(demofile))

    Child of locked token.

      >>> ReqAnnotation(request)[z3c.dav.ifvalidator.STATE_ANNOTS] = {
      ...    '/': {'statetoken': True}}
      >>> demofile._tokens = ['statetoken']
      >>> checkLockedOnModify(ObjectModifiedEvent(demofile))

    """
    # This is an hack to get at the current request object
    interaction = zope.security.management.queryInteraction()
    if interaction:
        request = interaction.participations[0]
        if zope.publisher.interfaces.http.IHTTPRequest.providedBy(request) \
               and request.method not in BROWSER_METHODS:
            if not z3c.dav.ifvalidator.matchesIfHeader(event.object, request):
                raise z3c.dav.interfaces.AlreadyLocked(
                    event.object, "Modifing locked object is not permitted.")
