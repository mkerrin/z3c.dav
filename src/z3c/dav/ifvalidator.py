##############################################################################
# Copyright (c) 2007 Zope Corporation and Contributors.
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

    tokens = zope.schema.List(
        title = u"State tokens",
        description = u"List of the current state tokens.")


class ListCondition(object):

    def __init__(self, notted = False, state_token = None, entity_tag = None):
        self.notted = notted
        self.state_token = state_token
        self.entity_tag = entity_tag


class IFValidator(object):
    """

      >>> import UserDict
      >>> import zope.interface.verify
      >>> import zope.publisher.interfaces
      >>> import zope.publisher.interfaces.http
      >>> from zope.publisher.interfaces import IPublishTraverse
      >>> from zope.publisher.browser import TestRequest
      >>> from zope.traversing.interfaces import IPhysicallyLocatable
      >>> from zope.app.publication.zopepublication import ZopePublication

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

      >>> class ReqAnnotation(UserDict.IterableUserDict):
      ...    zope.interface.implements(zope.annotation.interfaces.IAnnotations)
      ...    def __init__(self, request):
      ...        self.data = request._environ.setdefault('annotation', {})
      >>> zope.component.getGlobalSiteManager().registerAdapter(
      ...    ReqAnnotation, (zope.publisher.interfaces.http.IHTTPRequest,))

      >>> class ETag(object):
      ...    zope.interface.implements(z3c.conditionalviews.interfaces.IETag)
      ...    def __init__(self, context, request, view):
      ...        pass
      ...    etag = None
      ...    weak = False
      >>> zope.component.getGlobalSiteManager().registerAdapter(
      ...    ETag, (None, TestRequest, None))

      >>> class Statetokens(object):
      ...    zope.interface.implements(IStateTokens)
      ...    def __init__(self, context, request, view):
      ...        self.context = context
      ...    @property
      ...    def tokens(self):
      ...        if getattr(self.context, '_tokens', None) is not None:
      ...            return self.context._tokens
      ...        if self.context:
      ...            return [self.context.__name__]
      ...        return []
      >>> zope.component.getGlobalSiteManager().registerAdapter(
      ...    Statetokens, (None, TestRequest, None))

      >>> class Demo(object):
      ...    zope.interface.implements(IPublishTraverse)
      ...    def __init__(self, name):
      ...        self.__name__ = name
      ...        self.__parent__ = None
      ...        self.children = {}
      ...    def add(self, value):
      ...        self.children[value.__name__] = value
      ...        value.__parent__ = self
      ...    def publishTraverse(self, request, name):
      ...        child = self.children.get(name, None)
      ...        if child:
      ...            return child
      ...        raise zope.publisher.interfaces.NotFound(self, name, request)

      >>> class PhysicallyLocatable(object):
      ...    zope.interface.implements(IPhysicallyLocatable)
      ...    def __init__(self, context):
      ...        self.context = context
      ...    def getRoot(self):
      ...        return root
      ...    def getPath(self):
      ...        return '/' + self.context.__name__
      >>> zope.component.getGlobalSiteManager().registerAdapter(
      ...    PhysicallyLocatable, (zope.interface.Interface,))

    Firstly nothing matches the <DAV:no-lock> state token.

      >>> resource = Demo('test')
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

      >>> getStateResults(request)
      {}

    State-tokens
    ------------

    If the request is False then we have no need for the state tokens but
    they just default then to an empty dictionary.

      >>> request = TestRequest(environ = {'IF': '(<locktoken>)'})
      >>> validator.valid(resource, request, None)
      False
      >>> getStateResults(request)
      {}

      >>> resource._tokens = ['locktoken']
      >>> validator.valid(resource, request, None)
      True
      >>> getStateResults(request)
      {'/test': {'locktoken': True}}

    If there are multiple locktokens associated with a resource, we only
    are interested in the token that is represented in the IF header, so we
    only have one entry in the state results variable.

      >>> resource._tokens = ['locktoken', 'nolocktoken']
      >>> validator.valid(resource, request, None)
      True
      >>> getStateResults(request)
      {'/test': {'locktoken': True}}
      >>> request._environ['IF'] = '(NOT <locktoken>)'
      >>> validator.valid(resource, request, None)
      False

      >>> request._environ['IF'] = '(NOT <invalidlocktoken>)'
      >>> validator.valid(resource, request, None)
      True
      >>> getStateResults(request)
      {'/test': {'invalidlocktoken': False}}

    Combined entity / state tokens
    ------------------------------

      >>> request = TestRequest(environ = {'IF': '(<locktoken> ["xx"])'})
      >>> validator.valid(resource, request, None)
      True
      >>> resource._tokens = ['nolocktoken']
      >>> validator.valid(resource, request, None)
      False

      >>> request._environ['IF'] = '(<nolocktoken> ["xx"]) (["yy"])'
      >>> validator.valid(resource, request, None)
      True

      >>> request._environ['IF'] = '(<nolocktoken> ["yy"]) (["xx"])'
      >>> validator.valid(resource, request, None)
      True

    Resources
    =========

    We now need to test the situation when a resource is specified in the
    the `IF` header. We need to define a context here so that we can find
    the specified resource from the header. Make the context implement
    IPublishTraverse so that we know how to traverse to the next segment
    in the path.

    Setup up three content object. One is the context for validation, the
    second is a locked resource, and the last is the root of the site.

      >>> root = Demo('root')
      >>> locked = Demo('locked')
      >>> root.add(locked)
      >>> demo = Demo('demo')
      >>> root.add(demo)

    The request needs more setup in order for the traversal to work. We
    need and a publication object and since our TestRequets object extends
    the BrowserRequest pretend that the method is `FROG` so that the
    traversal doesn't try and find a default view for the resource. This
    would require more setup.

      >>> request.setPublication(ZopePublication(None))
      >>> request._environ['REQUEST_METHOD'] = 'FROG'

    Test that we can find the locked resource from the demo resource.

      >>> resource = validator.get_resource(
      ...    demo, request, 'http://localhost/locked')
      >>> resource.__name__
      'locked'
      >>> resource = validator.get_resource(demo, request, '/locked')
      >>> resource.__name__
      'locked'

    The state tokens for all content objects is there `__name__` attribute.

      >>> request._environ['IF'] = '<http://localhost/locked> (<demo>)'
      >>> validator.valid(demo, request, None)
      False
      >>> request._environ['IF'] = '<http://localhost/locked> (<locked>)'
      >>> validator.valid(demo, request, None)
      True
      >>> request._environ['IF'] = '<http://localhost/demo> (<demo>)'
      >>> validator.valid(demo, request, None)
      True

    If a specified resource does not exist then the only way for the IF header
    to match is for the state tokens to be `(Not <locktoken>)`.

      >>> request._environ['IF'] = '<http://localhost/missing> (<locked>)'
      >>> validator.valid(demo, request, None)
      False

    In this case when we try to match against `(Not <locked>)` but we stored
    state is still matched.

      >>> request._environ['IF'] = '<http://localhost/missing> (Not <locked>)'
      >>> validator.valid(demo, request, None)
      True
      >>> getStateResults(request)
      {'/missing': {'locked': False}}

    Invalid data
    ============

    When the if header fails to parse then the request should default to
    True, but if we matched any resources / state tokens before the parse
    error then we should still store this.

      >>> request._environ['IF'] = '</ddd> (hi)'
      >>> validator.valid(demo, request, None)
      True
      >>> getStateResults(request)
      {}

    The IF header parses until the list condition which is missing the angular
    brackets.

      >>> request._environ['IF'] = '</ddd> (<hi>) (there)'
      >>> validator.valid(demo, request, None)
      True
      >>> getStateResults(request)
      {'/ddd': {'hi': False}}

    Try what happens when there is no starting '(' for a list.

      >>> request._environ['IF'] = '</ddd> <hi>'
      >>> validator.valid(demo, request, None)
      True
      >>> getStateResults(request)
      {}

    Expected a '(' in the IF header but the header was already parsed.

      >>> request._environ['IF'] = '</ddd> (<hi>) <hi>'
      >>> validator.valid(demo, request, None)
      True
      >>> getStateResults(request)
      {'/ddd': {'hi': False}}

    Expected a '(' in the IF header.

      >>> request._environ['IF'] = '</ddd> (<hi>) hi'
      >>> validator.valid(demo, request, None)
      True
      >>> getStateResults(request)
      {'/ddd': {'hi': False}}

    Cleanup
    =======

      >>> zope.component.getGlobalSiteManager().unregisterAdapter(
      ...    ReqAnnotation, (zope.publisher.interfaces.http.IHTTPRequest,))
      True
      >>> zope.component.getGlobalSiteManager().unregisterAdapter(
      ...    ETag, (None, TestRequest, None))
      True
      >>> zope.component.getGlobalSiteManager().unregisterAdapter(
      ...    Statetokens, (None, TestRequest, None))
      True
      >>> zope.component.getGlobalSiteManager().unregisterAdapter(
      ...    PhysicallyLocatable, (zope.interface.Interface,))
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
                raise ValueError(
                    "IF Header contains invalid data - expected '('")
            header = header[1:].lstrip()

            while header:
                listitem = condition.match(header)
                if not listitem:
                    if header[0] != ")":
                        raise ValueError(
                            "IF Header contains invalid data - expected ')'")
                    header = header[1:].lstrip()
                    break

                header = header[listitem.end():].lstrip()

                notted = bool(listitem.group("notted"))
                state_token = listitem.group("state_token")
                entity_tag = listitem.group("entity_tag")
                if entity_tag:
                    if entity_tag[2:] == "W/":
                        entity_tag = entity[2:]
                    entity_tag = entity_tag[1:-1]

                conditions.append(
                    ListCondition(notted, state_token, entity_tag))

            if not conditions:
                break

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
        try:
            for resource, conditions in self.get_next_list(request):
                if resource:
                    try:
                        context = self.get_resource(context, request, resource)
                    except zope.publisher.interfaces.NotFound, error:
                        # resource is still set so can't match the conditions
                        # against the current context.
                        context = None

                if context is not None:
                    path = zope.traversing.api.getPath(context)
                else:
                    path = urlparse.urlparse(resource)[2]

                etag = zope.component.queryMultiAdapter(
                    (context, request, view),
                    z3c.conditionalviews.interfaces.IETag,
                    default = None)
                etag = etag and etag.etag

                states = zope.component.queryMultiAdapter(
                    (context, request, view), IStateTokens, default = [])
                states = states and states.tokens

                listresult = True
                for condition in conditions:
                    # Each List production describes a series of conditions.
                    # The whole list evaluates to true if and only if each
                    # condition evaluates to true.
                    if condition.entity_tag:
                        # XXX - should we store these entity tags for
                        # validation later on, like we do with the state
                        # tokens.
                        result = etag and etag == condition.entity_tag or False
                    elif condition.state_token:
                        result = condition.state_token in states or False
                        stateresults.setdefault(path, {})
                        stateresults[path][condition.state_token] = result
                    else:
                        # This should not happen :-)
                        raise TypeError(
                            "Either the entity_tag or the state_token needs "
                            "to be set on a condition")
                    if condition.notted:
                        result = not result

                    listresult &= result

                if listresult:
                    # Each No-tag-list and Tagged-list production may contain
                    # one or more Lists. They evaluate to true if and only if
                    # any of the contained lists evaluates to true. That is if
                    # listresult is True then the tag-lists are True.
                    break
            else:
                return False
        except ValueError:
            # Error in parsing the IF header, so as with all conditional
            # requests we default to True - that is a valid request.
            pass

        # We may have states and entity tags that failed, but we don't want
        # to reparse the if header to figure this out.
        reqannot = zope.annotation.interfaces.IAnnotations(request)
        reqannot[STATE_ANNOTS] = stateresults

        return True

    def invalidStatus(self, context, request, view):
        return 412

    def updateResponse(self, context, request, view):
        pass # do nothing


def getStateResults(request):
    reqannot = zope.annotation.interfaces.IAnnotations(request)
    return reqannot.get(STATE_ANNOTS, {})


def matchesIfHeader(context, request):
    activelock = zope.component.queryMultiAdapter(
        (context, request), z3c.dav.coreproperties.IActiveLock, default = None)
    if activelock is not None:
        reqannot = zope.annotation.interfaces.IAnnotations(request)
        return reqannot.get(STATE_ANNOTS, {}).get(
            zope.traversing.api.getPath(context), {}).get(
                activelock.locktoken[0], False)
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
      ...    zope.interface.implements(z3c.dav.coreproperties.IActiveLock)
      ...    zope.component.adapts(IResource,
      ...        zope.interface.Interface)
      ...    def __init__(self, context, request):
      ...        self.context = context
      ...    locktoken = ['testlocktoken']

      >>> zope.component.getGlobalSiteManager().registerAdapter(Activelock)

      >>> states.tokens
      ['testlocktoken']

    Cleanup.

      >>> zope.component.getGlobalSiteManager().unregisterAdapter(Activelock)
      True

    """
    zope.interface.implements(IStateTokens)

    def __init__(self, context, request, view):
        self.context = context
        self.request = request

    @property
    def tokens(self):
        activelock = zope.component.queryMultiAdapter(
            (self.context, self.request), z3c.dav.coreproperties.IActiveLock)
        if activelock is not None:
            locktokens = activelock.locktoken
            if locktokens:
                return locktokens
        return []
