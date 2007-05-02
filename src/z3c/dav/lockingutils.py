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
"""Support for using zope.locking has a locking mechanism for WebDAV locking.

Note that we can't use zope.locking.utility.TokenUtility has a global utility.
This is because if a recursive lock request fails half through then the
utility has already been modified and since it is not persistent
transaction.abort doesn't unlock the pervious successful locks. Since the
utility gets into an inconsistent state.

$Id$
"""
__docformat__ = 'restructuredtext'

import persistent
import time
import random
from BTrees.OOBTree import OOBTree
from zope import component
from zope import interface
from zope.locking import tokens
import zope.locking.interfaces
from zope.security.proxy import removeSecurityProxy
from zope.app.keyreference.interfaces import IKeyReference
from zope.traversing.browser.absoluteurl import absoluteURL
from zope.app.container.interfaces import IReadContainer

from z3c.dav.coreproperties import ILockEntry, IDAVSupportedlock, \
     IActiveLock
import z3c.dav.interfaces


INDIRECT_INDEX_KEY = 'zope.app.dav.lockingutils'

_randGen = random.Random(time.time())

class IIndirectToken(zope.locking.interfaces.IToken,
                     zope.locking.interfaces.IEndable):
    """
    """

    roottoken = interface.Attribute("""
    Return the root lock token against which this token is locked.
    """)


class IndirectToken(persistent.Persistent):
    """

    Most of these tests have being copied from the README.txt file in
    zope.locking

    Some initial setup including creating some demo content.

      >>> from zope.locking import utility, utils
      >>> util = utility.TokenUtility()
      >>> component.getGlobalSiteManager().registerUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)

    Setup some content to test on.

      >>> demofolder = DemoFolder(None, 'demofolderroot')
      >>> demofolder['demo1'] = Demo()
      >>> demofolder['demofolder1'] = DemoFolder()
      >>> demofolder['demofolder1']['demo'] = Demo()

    Lock the root folder with an exclusive lock.

      >>> lockroot = tokens.ExclusiveLock(demofolder, 'michael')
      >>> res = util.register(lockroot)

    Now indirectly all the descended objects of the root folder against the
    exclusive lock token we used to lock this folder with.

      >>> lock1 = IndirectToken(demofolder['demo1'], lockroot)
      >>> lock2 = IndirectToken(demofolder['demofolder1'], lockroot)
      >>> lock3 = IndirectToken(demofolder['demofolder1']['demo'], lockroot)
      >>> res1 = util.register(lock1)
      >>> lock1 is util.get(demofolder['demo1'])
      True
      >>> res2 = util.register(lock2)
      >>> lock2 is util.get(demofolder['demofolder1'])
      True
      >>> res3 = util.register(lock3)
      >>> lock3 is util.get(demofolder['demofolder1']['demo'])
      True

    Make sure that the lockroot contains an index of all the toekns locked
    against in its annotations

      >>> len(lockroot.annotations[INDIRECT_INDEX_KEY])
      3

    Check that the IEndable properties are None

      >>> res1.expiration == lockroot.expiration == None
      True
      >>> res1.duration == lockroot.duration == None
      True
      >>> res1.duration == lockroot.remaining_duration == None
      True
      >>> res1.started == lockroot.started
      True
      >>> lockroot.started is not None
      True

    All the indirect locktokens and the lookroot share the same annotations

      >>> lockroot.annotations[u'webdav'] = u'test webdav indirect locking'
      >>> res1.annotations[u'webdav']
      u'test webdav indirect locking'

    All the lock tokens have the same principals

      >>> list(res1.principal_ids)
      ['michael']
      >>> list(lockroot.principal_ids)
      ['michael']

    None of the locks have ended yet, and they share the same utility.

      >>> res1.ended is None
      True
      >>> lockroot.ended is None
      True
      >>> lockroot.utility is res1.utility
      True

    Expire the lock root

      >>> now = utils.now()
      >>> res3.end()

    Now all the descendent objects of the lockroot and the lockroot itself
    are unlocked.

      >>> util.get(demofolder) is None
      True
      >>> util.get(demofolder['demo1']) is None
      True
      >>> util.get(demofolder['demofolder1']['demo']) is None
      True

    Also all the tokens has ended after now.

      >>> lock1.ended is not None
      True
      >>> lock2.ended > now
      True
      >>> lock1.ended is lock2.ended
      True
      >>> lock3.ended is lockroot.ended
      True

    Test the event subscribers.

      >>> ev = events[-1]
      >>> zope.locking.interfaces.ITokenEndedEvent.providedBy(ev)
      True
      >>> len(lockroot.annotations[INDIRECT_INDEX_KEY])
      3
      >>> removeEndedTokens(ev)
      >>> len(lockroot.annotations[INDIRECT_INDEX_KEY])
      0

    Test all the endable attributes

      >>> import datetime
      >>> one = datetime.timedelta(hours = 1)
      >>> two = datetime.timedelta(hours = 2)
      >>> three = datetime.timedelta(hours = 3)
      >>> four = datetime.timedelta(hours = 4)
      >>> lockroot = tokens.ExclusiveLock(demofolder, 'john', three)
      >>> dummy = util.register(lockroot)
      >>> indirect1 = IndirectToken(demofolder['demo1'], lockroot)
      >>> dummy = util.register(indirect1)
      >>> indirect1.duration
      datetime.timedelta(0, 10800)
      >>> lockroot.duration == indirect1.duration
      True
      >>> indirect1.ended is None
      True
      >>> indirect1.expiration == indirect1.started + indirect1.duration
      True

    Now try to 

      >>> indirect1.expiration = indirect1.started + one
      >>> indirect1.expiration == indirect1.started + one
      True
      >>> indirect1.expiration == lockroot.expiration
      True
      >>> indirect1.duration == one
      True

    Now test changing the duration attribute

      >>> indirect1.duration = four
      >>> indirect1.duration == lockroot.duration
      True
      >>> indirect1.duration
      datetime.timedelta(0, 14400)

    Now check the remain_duration code

      >>> import pytz
      >>> def hackNow():
      ...     return (datetime.datetime.now(pytz.utc) +
      ...             datetime.timedelta(hours=2))
      ...
      >>> import zope.locking.utils
      >>> oldNow = zope.locking.utils.now
      >>> zope.locking.utils.now = hackNow # make code think it's 2 hours later
      >>> indirect1.duration
      datetime.timedelta(0, 14400)
      >>> two >= indirect1.remaining_duration >= one
      True
      >>> indirect1.remaining_duration -= one
      >>> one >= indirect1.remaining_duration >= datetime.timedelta()
      True
      >>> three + datetime.timedelta(minutes = 1) >= indirect1.duration >= three
      True

    Since we modified the remaining_duration attribute a IExpirationChagedEvent
    should have being fired.
      
      >>> ev = events[-1]
      >>> from zope.interface.verify import verifyObject
      >>> from zope.locking.interfaces import IExpirationChangedEvent
      >>> verifyObject(IExpirationChangedEvent, ev)
      True
      >>> ev.object is lockroot
      True

    Now pretend that it is a day later, the indirect token and the lock root
    will have timed out sliently.

      >>> def hackNow():
      ...     return (
      ...         datetime.datetime.now(pytz.utc) + datetime.timedelta(days=1))
      ...
      >>> zope.locking.utils.now = hackNow # make code think it is a day later
      >>> indirect1.ended == indirect1.expiration
      True
      >>> lockroot.ended == indirect1.ended
      True
      >>> util.get(demofolder['demo1']) is None
      True
      >>> util.get(demofolder['demo1'], util) is util
      True
      >>> indirect1.remaining_duration == datetime.timedelta()
      True
      >>> indirect1.end()
      Traceback (most recent call last):
      ...
      EndedError

    Once a lock has ended, the timeout can no longer be changed.

      >>> indirect1.duration = datetime.timedelta(days=2)
      Traceback (most recent call last):
      ...
      EndedError

    Now undo our hack.

      >>> zope.locking.utils.now = oldNow # undo the hack
      >>> indirect1.end() # really end the token
      >>> util.get(demofolder) is None
      True

    Now test the simple SharedLock with an indirect token.

      >>> lockroot = tokens.SharedLock(demofolder, ('john', 'mary'))
      >>> dummy = util.register(lockroot)
      >>> sharedindirect = IndirectToken(demofolder['demo1'], lockroot)
      >>> dummy = util.register(sharedindirect)
      >>> sorted(sharedindirect.principal_ids)
      ['john', 'mary']
      >>> sharedindirect.add(('jane',))
      >>> sorted(lockroot.principal_ids)
      ['jane', 'john', 'mary']
      >>> sorted(sharedindirect.principal_ids)
      ['jane', 'john', 'mary']
      >>> sharedindirect.remove(('mary',))
      >>> sorted(sharedindirect.principal_ids)
      ['jane', 'john']
      >>> sorted(lockroot.principal_ids)
      ['jane', 'john']
      >>> lockroot.remove(('jane',))
      >>> sorted(sharedindirect.principal_ids)
      ['john']
      >>> sorted(lockroot.principal_ids)
      ['john']
      >>> sharedindirect.remove(('john',))
      >>> util.get(demofolder) is None
      True
      >>> util.get(demofolder['demo1']) is None
      True

    Test using the shared lock token methods on a non shared lock

      >>> lockroot = tokens.ExclusiveLock(demofolder, 'john')
      >>> dummy = util.register(lockroot)
      >>> indirect1 = IndirectToken(demofolder['demo1'], lockroot)
      >>> dummy = util.register(indirect1)
      >>> dummy is indirect1
      True
      >>> dummy.add('john')
      Traceback (most recent call last):
      ...
      TypeError: can't add a principal to a non-shared token
      >>> dummy.remove('michael')
      Traceback (most recent call last):
      ...
      TypeError: can't add a principal to a non-shared token

    Setup with wrong utility.

      >>> util2 = utility.TokenUtility()
      >>> roottoken = tokens.ExclusiveLock(demofolder, 'michael2')
      >>> roottoken = util2.register(roottoken)
      >>> roottoken.utility == util2
      True

      >>> indirecttoken = IndirectToken(demofolder['demo1'], roottoken)
      >>> indirecttoken = util2.register(indirecttoken)
      >>> indirecttoken.utility is util2
      True
      >>> indirecttoken.utility = util
      Traceback (most recent call last):
      ...
      ValueError: cannot reset utility
      >>> indirecttoken = IndirectToken(demofolder['demo1'], roottoken)
      >>> indirecttoken.utility = util
      Traceback (most recent call last):
      ...
      ValueError: Indirect tokens must be registered withsame utility has the root token

    Cleanup test.

      >>> component.getGlobalSiteManager().unregisterUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      True

    """
    interface.implements(IIndirectToken)

    def __init__(self, target, token):
        self.context = self.__parent__ = target
        self.roottoken = token

    _utility = None
    @apply
    def utility():
        # IAbstractToken - this is the only hook I can find since
        # it represents the lock utility in charge of this lock.
        def get(self):
            return self._utility
        def set(self, value):
            if self._utility is not None:
                if value is not self._utility:
                    raise ValueError("cannot reset utility")
            else:
                assert zope.locking.interfaces.ITokenUtility.providedBy(value)
                root = self.roottoken
                if root.utility != value:
                    raise ValueError("Indirect tokens must be registered with" \
                                     "same utility has the root token")
                index = root.annotations.get(INDIRECT_INDEX_KEY, None)
                if index is None:
                    index = root.annotations[INDIRECT_INDEX_KEY] = \
                            tokens.AnnotationsMapping()
                    index.__parent__ = root
                key_ref = IKeyReference(self.context)
                assert index.get(key_ref, None) is None, \
                       "context is already locked"
                index[key_ref] = self
                self._utility = value
        return property(get, set)

    @property
    def principal_ids(self):
        # IAbstractToken
        return self.roottoken.principal_ids

    @property
    def started(self):
        # IAbstractToken
        return self.roottoken.started

    @property
    def annotations(self):
        # See IToken
        return self.roottoken.annotations

    def add(self, principal_ids):
        # ISharedLock
        if not zope.locking.interfaces.ISharedLock.providedBy(self.roottoken):
            raise TypeError, "can't add a principal to a non-shared token"
        return self.roottoken.add(principal_ids)

    def remove(self, principal_ids):
        # ISharedLock
        if not zope.locking.interfaces.ISharedLock.providedBy(self.roottoken):
            raise TypeError, "can't add a principal to a non-shared token"
        return self.roottoken.remove(principal_ids)

    @property
    def ended(self):
        # IEndable
        return self.roottoken.ended

    @apply
    def expiration(): # XXX - needs testing
        # IEndable
        def get(self):
            return self.roottoken.expiration
        def set(self, value):
            self.roottoken.expiration = value
        return property(get, set)

    @apply
    def duration(): # XXX - needs testing
        # IEndable
        def get(self):
            return self.roottoken.duration
        def set(self, value):
            self.roottoken.duration = value
        return property(get, set)

    @apply
    def remaining_duration():
        # IEndable
        def get(self):
            return self.roottoken.remaining_duration
        def set(self, value):
            self.roottoken.remaining_duration = value
        return property(get, set)

    def end(self):
        # IEndable
        return self.roottoken.end()


def removeEndedTokens(event):
    """subscriber handler for ITokenEndedEvent"""
    assert zope.locking.interfaces.ITokenEndedEvent.providedBy(event)
    roottoken = event.object
    assert not IIndirectToken.providedBy(roottoken)
    index = roottoken.annotations.get(INDIRECT_INDEX_KEY, {})
    # read the whole index in memory so that we correctly loop over all the
    # items in this list.
    indexItems = list(index.items())
    for key_ref, token in indexItems:
        # token has ended so it should be removed via the register method
        roottoken.utility.register(token)
        del index[key_ref]

# TODO - need subscriber incase a user tries to add a object has a
# descendent to the lock object.

################################################################################
#
# zope.locking adapters.
#
################################################################################

class ExclusiveLockEntry(object):
    interface.implements(ILockEntry)

    lockscope = [u"exclusive"]
    locktype = [u"write"]


class SharedLockEntry(object):
    interface.implements(ILockEntry)

    lockscope = [u"shared"]
    locktype = [u"write"]


@component.adapter(interface.Interface, z3c.dav.interfaces.IWebDAVRequest)
@interface.implementer(IDAVSupportedlock)
def DAVSupportedlock(context, request):
    """
    This adapter retrieves the data for rendering in the `{DAV:}supportedlock`
    property. The `{DAV:}supportedlock` property provides a listing of lock
    capabilities supported by the resource.

    When their is no ITokenUtility registered with the system then we can't
    lock any content object and so this property is undefined.

      >>> DAVSupportedlock(None, None) is None
      True

      >>> from zope.locking.utility import TokenUtility
      >>> util = TokenUtility()
      >>> component.getGlobalSiteManager().registerUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)

    zope.locking supported both the exclusive and shared lock tokens.

      >>> slock = DAVSupportedlock(None, None)
      >>> len(slock.supportedlock)
      2
      >>> exclusive, shared = slock.supportedlock

      >>> exclusive.lockscope
      [u'exclusive']
      >>> exclusive.locktype
      [u'write']

      >>> shared.lockscope
      [u'shared']
      >>> shared.locktype
      [u'write']

    Cleanup

      >>> component.getGlobalSiteManager().unregisterUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      True

    """
    utility = component.queryUtility(zope.locking.interfaces.ITokenUtility,
                                     context = context, default = None)
    if utility is None:
        return None
    return DAVSupportedlockAdapter()


class DAVSupportedlockAdapter(object):
    interface.implements(IDAVSupportedlock)
    component.adapts(interface.Interface,
                     z3c.dav.interfaces.IWebDAVRequest)

    @property
    def supportedlock(self):
        return [ExclusiveLockEntry(), SharedLockEntry()]


WEBDAV_LOCK_KEY = "z3c.dav.lockingutils.info"

@component.adapter(interface.Interface, z3c.dav.interfaces.IWebDAVRequest)
@interface.implementer(IActiveLock)
def DAVActiveLock(context, request):
    """
    This adapter is responsible for the data for the `{DAV:}activelock`
    XML element. This XML element occurs within the `{DAV:}lockdiscovery`
    property.

      >>> import datetime
      >>> import pytz
      >>> from cStringIO import StringIO
      >>> from zope.interface.verify import verifyObject
      >>> import zope.locking.utils
      >>> from zope.locking.utility import TokenUtility
      >>> from zope.locking.adapters import TokenBroker
      >>> from z3c.dav.publisher import WebDAVRequest

      >>> def hackNow():
      ...     return datetime.datetime(2007, 4, 7, tzinfo = pytz.utc)
      >>> oldNow = zope.locking.utils.now
      >>> zope.locking.utils.now = hackNow

    The activelock property only exists whenever the zope.locking package
    is configured properly.

      >>> resource = DemoFolder()
      >>> request = WebDAVRequest(StringIO(''), {})
      >>> DAVActiveLock(resource, request) is None
      True

    Now register a ITokenUtility utility and lock the resource with it.

      >>> util = TokenUtility()
      >>> component.getGlobalSiteManager().registerUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)

      >>> locktoken = tokens.ExclusiveLock(
      ...    resource, 'michael', datetime.timedelta(hours = 1))
      >>> locktoken = util.register(locktoken)

    DAVActiveLock is still None since their is no adapter from the demo
    content object to zope.locking.interfaces.ITokenBroker. This is part
    of the zope.locking installation that hasn't been completed yet.

      >>> DAVActiveLock(resource, request) is None
      True

      >>> component.getGlobalSiteManager().registerAdapter(
      ...    TokenBroker, (interface.Interface,),
      ...    zope.locking.interfaces.ITokenBroker)

      >>> activelock = DAVActiveLock(resource, request)
      >>> IActiveLock.providedBy(activelock)
      True
      >>> verifyObject(IActiveLock, activelock)
      True

    Now test the data managed by the current activelock property.

      >>> activelock.lockscope
      [u'exclusive']
      >>> activelock.locktype
      [u'write']
      >>> activelock.timeout
      u'Second-3600'
      >>> activelock.lockroot
      '/dummy/'

    The depth attribute is required by the WebDAV specification. But this
    information is stored by the z3c.dav.lockingutils in the lock token's
    annotation. But if a lock token is taken out by an alternative Zope3
    application that uses the zope.locking package then this information will
    must likely not be set up. So this adapter should provide reasonable
    default values for this information. Later we will set up the lock
    token's annotation data to store this information. The data for the owner
    and locktoken XML elements are also stored on within the lock tokens
    annotation key but these XML elements are not required by the WebDAV
    specification so this data just defaults to None.

      >>> activelock.depth
      '0'
      >>> activelock.owner is None
      True
      >>> activelock.locktoken is None
      True

    Now if we try and render this information all the required fields, as
    specified by the WebDAV specification get rendered.

      >>> lockdiscovery = DAVLockdiscovery(resource, request)
      >>> davwidget = z3c.dav.properties.getWidget(
      ...    z3c.dav.coreproperties.lockdiscovery,
      ...    lockdiscovery, request)
      >>> print etree.tostring(davwidget.render()) #doctest:+XMLDATA
      <lockdiscovery xmlns="DAV:" />

      >>> component.getGlobalSiteManager().registerAdapter(DAVActiveLock)

      >>> lockdiscovery = DAVLockdiscovery(resource, request)
      >>> davwidget = z3c.dav.properties.getWidget(
      ...    z3c.dav.coreproperties.lockdiscovery,
      ...    lockdiscovery, request)
      >>> print etree.tostring(davwidget.render()) #doctest:+XMLDATA
      <lockdiscovery xmlns="DAV:">
        <activelock>
          <lockscope><exclusive /></lockscope>
          <locktype><write /></locktype>
          <depth>0</depth>
          <timeout>Second-3600</timeout>
          <lockroot>/dummy/</lockroot>
        </activelock>
      </lockdiscovery>

    We use the lock tokens annotation to store the data for the owner, depth
    and locktoken attributes.

      >>> locktoken.annotations[WEBDAV_LOCK_KEY] = OOBTree()
      >>> locktoken.annotations[WEBDAV_LOCK_KEY]['depth'] = 'testdepth'
      >>> locktoken.annotations[WEBDAV_LOCK_KEY]['owner'] = '<owner xmlns="DAV:">Me</owner>'
      >>> locktoken.annotations[WEBDAV_LOCK_KEY]['token'] = 'simpletoken'

    After updating the lock token's annotations we need to regenerate the
    activelock adapter so that the tokendata internal attribute is setup
    correctly.

      >>> activelock = DAVActiveLock(resource, request)

    The owner attribute is not required by the WebDAV specification, but
    we can see it anyways, and similarly for the locktoken attribute.

      >>> activelock.owner
      '<owner xmlns="DAV:">Me</owner>'

    Each lock token on a resource as at most one `token` associated with it,
    but in order to display this information correctly we must return a
    a list with one item.

      >>> activelock.locktoken
      ['simpletoken']

      >>> lockdiscovery = DAVLockdiscovery(resource, request)
      >>> davwidget = z3c.dav.properties.getWidget(
      ...    z3c.dav.coreproperties.lockdiscovery,
      ...    lockdiscovery, request)
      >>> print etree.tostring(davwidget.render()) #doctest:+XMLDATA
      <lockdiscovery xmlns="DAV:">
        <activelock>
          <lockscope><exclusive /></lockscope>
          <locktype><write /></locktype>
          <depth>testdepth</depth>
          <owner>Me</owner>
          <timeout>Second-3600</timeout>
          <locktoken><href>simpletoken</href></locktoken>
          <lockroot>/dummy/</lockroot>
        </activelock>
      </lockdiscovery>

    Test the indirect locktoken. These are used when we try and lock a
    collection with the depth header set to `infinity`. These lock tokens
    share the same annotation information, expiry information and lock token,
    as the top level lock token.

      >>> resource['demo'] = Demo()
      >>> sublocktoken = IndirectToken(resource['demo'], locktoken)
      >>> sublocktoken = util.register(sublocktoken)

      >>> activelock = DAVActiveLock(resource['demo'], request)
      >>> verifyObject(IActiveLock, activelock)
      True

      >>> activelock.lockscope
      [u'exclusive']
      >>> activelock.locktype
      [u'write']
      >>> activelock.depth
      'testdepth'
      >>> activelock.owner
      '<owner xmlns="DAV:">Me</owner>'
      >>> activelock.timeout
      u'Second-3600'
      >>> activelock.locktoken
      ['simpletoken']
      >>> activelock.lockroot
      '/dummy/'

    Now rendering the lockdiscovery DAV widget for this new resource we get
    the following.

      >>> lockdiscovery = DAVLockdiscovery(resource['demo'], request)
      >>> davwidget = z3c.dav.properties.getWidget(
      ...    z3c.dav.coreproperties.lockdiscovery,
      ...    lockdiscovery, request)
      >>> print etree.tostring(davwidget.render()) #doctest:+XMLDATA
      <lockdiscovery xmlns="DAV:">
        <activelock>
          <lockscope><exclusive /></lockscope>
          <locktype><write /></locktype>
          <depth>testdepth</depth>
          <owner>Me</owner>
          <timeout>Second-3600</timeout>
          <locktoken><href>simpletoken</href></locktoken>
          <lockroot>/dummy/</lockroot>
        </activelock>
      </lockdiscovery>

      >>> locktoken.end()

    Now a locktoken from an other application could be taken out on our
    demofolder that we know very little about. For example, a
    zope.locking.tokens.EndableFreeze` lock token. It should be displayed as
    an activelock on the resource but since we don't know if the scope of this
    token is an `{DAV:}exclusive` or `{DAV:}shared` (the only lock scopes
    currently supported by WebDAV), we will render this information as an
    empty XML element.

      >>> locktoken = tokens.EndableFreeze(
      ...    resource, datetime.timedelta(hours = 1))
      >>> locktoken = util.register(locktoken)

      >>> activelock = DAVActiveLock(resource, request)
      >>> IActiveLock.providedBy(activelock)
      True

      >>> activelock.timeout
      u'Second-3600'
      >>> activelock.locktype
      [u'write']

    Now the locktoken is None so no WebDAV client should be able to a resource
    or more likely they shouldn't be able to take out a new lock on this
    resource, since the `IF` conditional header shored fail.

      >>> activelock.locktoken is None
      True

    So far so good. But the EndableFreeze token doesn't correspond to any
    lock scope known by this WebDAV implementation so when we try and access
    we just return a empty list. This ensures the `{DAV:}lockscope` element
    gets rendered by its IDAVWidget but it doesn't contain any information.

      >>> activelock.lockscope
      []
      >>> activelock.lockscope != z3c.dav.coreproperties.IActiveLock['lockscope'].missing_value
      True

    Rending this lock token we get the following.

      >>> lockdiscovery = DAVLockdiscovery(resource, request)
      >>> davwidget = z3c.dav.properties.getWidget(
      ...    z3c.dav.coreproperties.lockdiscovery,
      ...    lockdiscovery, request)
      >>> print etree.tostring(davwidget.render()) #doctest:+XMLDATA
      <lockdiscovery xmlns="DAV:">
        <activelock>
          <lockscope></lockscope>
          <locktype><write /></locktype>
          <depth>0</depth>
          <timeout>Second-3600</timeout>
          <lockroot>/dummy/</lockroot>
        </activelock>
      </lockdiscovery>

    Unlock the resource.

      >>> locktoken.end()

    Now not all lock tokens have a duration associated with them. In this
    case the timeout is None, as it is not fully required by the WebDAV
    specification and all the other attributes will have the default values
    as tested previously.

      >>> locktoken = tokens.ExclusiveLock(resource, 'michael')
      >>> locktoken = util.register(locktoken)

      >>> activelock = DAVActiveLock(resource, request)
      >>> verifyObject(IActiveLock, activelock)
      True
      >>> activelock.timeout is None
      True

      >>> lockdiscovery = DAVLockdiscovery(resource, request)
      >>> davwidget = z3c.dav.properties.getWidget(
      ...    z3c.dav.coreproperties.lockdiscovery,
      ...    lockdiscovery, request)
      >>> print etree.tostring(davwidget.render()) #doctest:+XMLDATA
      <lockdiscovery xmlns="DAV:">
        <activelock>
          <lockscope><exclusive /></lockscope>
          <locktype><write /></locktype>
          <depth>0</depth>
          <lockroot>/dummy/</lockroot>
        </activelock>
      </lockdiscovery>

    Cleanup

      >>> zope.locking.utils.now = oldNow # undo time hack

      >>> component.getGlobalSiteManager().unregisterUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      True
      >>> component.getGlobalSiteManager().unregisterAdapter(
      ...    TokenBroker, (interface.Interface,),
      ...    zope.locking.interfaces.ITokenBroker)
      True
      >>> component.getGlobalSiteManager().unregisterAdapter(DAVActiveLock)
      True

    """
    try:
        token = zope.locking.interfaces.ITokenBroker(context).get()
    except TypeError:
        token = None
    if token is None:
        return None
    return DAVActiveLockAdapter(token, context, request)


class DAVActiveLockAdapter(object):
    component.adapts(interface.Interface,
                     z3c.dav.interfaces.IWebDAVRequest)
    interface.implements(IActiveLock)

    def __init__(self, token, context, request):
        self.context = self.__parent__ = context
        self.token = token
        self.tokendata = token.annotations.get(WEBDAV_LOCK_KEY, {})
        self.request = request

    @property
    def lockscope(self):
        if IIndirectToken.providedBy(self.token):
            roottoken = self.token.roottoken
        else:
            roottoken = self.token

        if zope.locking.interfaces.IExclusiveLock.providedBy(roottoken):
            return [u"exclusive"]
        elif zope.locking.interfaces.ISharedLock.providedBy(roottoken):
            return [u"shared"]

        return []

    @property
    def locktype(self):
        return [u"write"]

    @property
    def depth(self):
        return self.tokendata.get("depth", "0")

    @property
    def owner(self):
        return self.tokendata.get("owner", None)

    @property
    def timeout(self):
        remaining = self.token.remaining_duration
        if remaining is None:
            return None
        return u"Second-%d" % remaining.seconds

    @property
    def locktoken(self):
        token = self.tokendata.get("token", None)
        if token is None:
            return None
        return [token]

    @property
    def lockroot(self):
        if IIndirectToken.providedBy(self.token):
            root = self.token.roottoken.context
        else:
            root = self.token.context

        return absoluteURL(root, self.request)


@component.adapter(interface.Interface, z3c.dav.interfaces.IWebDAVRequest)
@interface.implementer(z3c.dav.coreproperties.IDAVLockdiscovery)
def DAVLockdiscovery(context, request):
    """
    This adapter is responsible for getting the data for the
    `{DAV:}lockdiscovery` property.

      >>> import datetime
      >>> from zope.interface.verify import verifyObject
      >>> from zope.locking.utility import TokenUtility
      >>> from zope.locking.adapters import TokenBroker
      >>> from z3c.dav.publisher import WebDAVRequest
      >>> from cStringIO import StringIO
      >>> resource = Demo()
      >>> request = WebDAVRequest(StringIO(''), {})

      >>> DAVLockdiscovery(resource, request) is None
      True

      >>> util = TokenUtility()
      >>> component.getGlobalSiteManager().registerUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      >>> component.getGlobalSiteManager().registerAdapter(DAVActiveLock,
      ...    (interface.Interface, z3c.dav.interfaces.IWebDAVRequest),
      ...     IActiveLock)
      >>> component.getGlobalSiteManager().registerAdapter(
      ...    TokenBroker, (interface.Interface,),
      ...    zope.locking.interfaces.ITokenBroker)

    The `{DAV:}lockdiscovery` is now defined for the resource but its value
    is None because the resource isn't locked yet.

      >>> lockdiscovery = DAVLockdiscovery(resource, request)
      >>> lockdiscovery is not None
      True
      >>> lockdiscovery.lockdiscovery is None
      True

      >>> token = tokens.ExclusiveLock(
      ...    resource, 'michael', datetime.timedelta(hours = 1))
      >>> token = util.register(token)
      >>> tokenannot = token.annotations[WEBDAV_LOCK_KEY] = OOBTree()
      >>> tokenannot['depth'] = 'testdepth'

      >>> lockdiscoveryview = DAVLockdiscovery(resource, request)
      >>> lockdiscovery = lockdiscoveryview.lockdiscovery
      >>> len(lockdiscovery)
      1
      >>> IActiveLock.providedBy(lockdiscovery[0])
      True
      >>> isinstance(lockdiscovery[0], DAVActiveLockAdapter)
      True

    Cleanup

      >>> component.getGlobalSiteManager().unregisterUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      True
      >>> component.getGlobalSiteManager().unregisterAdapter(DAVActiveLock,
      ...    (interface.Interface, z3c.dav.interfaces.IWebDAVRequest),
      ...     IActiveLock)
      True
      >>> component.getGlobalSiteManager().unregisterAdapter(
      ...    TokenBroker, (interface.Interface,),
      ...    zope.locking.interfaces.ITokenBroker)
      True

    """
    utility = component.queryUtility(zope.locking.interfaces.ITokenUtility)
    if utility is None:
        return None
    return DAVLockdiscoveryAdapter(context, request)


class DAVLockdiscoveryAdapter(object):
    interface.implements(z3c.dav.coreproperties.IDAVLockdiscovery)
    component.adapts(interface.Interface,
                     z3c.dav.interfaces.IWebDAVRequest)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    @property
    def lockdiscovery(self):
        adapter = component.queryMultiAdapter((self.context, self.request),
                                              IActiveLock, default = None)
        if adapter is None:
            return None
        return [adapter]


class DAVLockmanager(object):
    """

      >>> from zope.interface.verify import verifyObject
      >>> from zope.locking import utility, utils
      >>> from zope.locking.adapters import TokenBroker

      >>> file = Demo()

    Before we register a ITokenUtility utility make sure that the DAVLockmanager
    is not lockable.

      >>> adapter = DAVLockmanager(file)
      >>> adapter.islockable()
      False

    Now create and register a ITokenUtility utility.

      >>> util = utility.TokenUtility()
      >>> component.getGlobalSiteManager().registerUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      >>> component.getGlobalSiteManager().registerAdapter(
      ...    TokenBroker, (interface.Interface,),
      ...    zope.locking.interfaces.ITokenBroker)

      >>> import datetime
      >>> import pytz
      >>> def hackNow():
      ...     return datetime.datetime(2006, 7, 25, 23, 49, 51)
      >>> oldNow = utils.now
      >>> utils.now = hackNow

    Test the DAVLockmanager implements the descired interface.

      >>> adapter = DAVLockmanager(file)
      >>> verifyObject(z3c.dav.interfaces.IDAVLockmanager, adapter)
      True

    The adapter should also be lockable.

      >>> adapter.islockable()
      True

    Lock with an exclusive lock token.

      >>> roottoken = adapter.lock(u'exclusive', u'write',
      ...    u'Michael', datetime.timedelta(seconds = 3600), '0')
      >>> util.get(file) == roottoken
      True
      >>> zope.locking.interfaces.IExclusiveLock.providedBy(roottoken)
      True

      >>> adapter.islocked()
      True

      >>> activelock = adapter.getActivelock()
      >>> activelock.lockscope
      [u'exclusive']
      >>> activelock.locktype
      [u'write']
      >>> activelock.depth
      '0'
      >>> activelock.timeout
      u'Second-3600'
      >>> activelock.lockroot
      '/dummy'
      >>> activelock.owner
      u'Michael'

      >>> adapter.refreshlock(datetime.timedelta(seconds = 7200))
      >>> adapter.getActivelock().timeout
      u'Second-7200'

      >>> adapter.unlock()
      >>> util.get(file) is None
      True
      >>> adapter.islocked()
      False
      >>> adapter.getActivelock() is None
      True

    Shared locking support.

      >>> roottoken = adapter.lock(u'shared', u'write', u'Michael',
      ...    datetime.timedelta(seconds = 3600), '0')
      >>> util.get(file) == roottoken
      True
      >>> zope.locking.interfaces.ISharedLock.providedBy(roottoken)
      True

      >>> activelock = adapter.getActivelock()
      >>> activelock.lockscope
      [u'shared']
      >>> activelock.locktoken #doctest:+ELLIPSIS
      ['opaquelocktoken:...

      >>> adapter.unlock()

    Recursive lock suport.

      >>> demofolder = DemoFolder()
      >>> demofolder['demo'] = file

      >>> adapter = DAVLockmanager(demofolder)
      >>> roottoken = adapter.lock(u'exclusive', u'write', u'MichaelK',
      ...    datetime.timedelta(seconds = 3600), 'infinity')

      >>> demotoken = util.get(file)
      >>> IIndirectToken.providedBy(demotoken)
      True

      >>> activelock = adapter.getActivelock()
      >>> activelock.lockroot
      '/dummy/'
      >>> DAVLockmanager(file).getActivelock().lockroot
      '/dummy/'
      >>> absoluteURL(file, None)
      '/dummy/dummy'
      >>> activelock.lockscope
      [u'exclusive']

    Already locked support.

      >>> adapter.lock(u'exclusive', u'write', u'Michael',
      ...    datetime.timedelta(seconds = 100), 'infinity') #doctest:+ELLIPSIS
      Traceback (most recent call last):
      ...
      AlreadyLocked...
      >>> adapter.islocked()
      True

      >>> adapter.unlock()

    Some error conditions.

      >>> adapter.lock(u'notexclusive', u'write', u'Michael',
      ...    datetime.timedelta(seconds = 100), 'infinity') # doctest:+ELLIPSIS
      Traceback (most recent call last):
      ...
      UnprocessableError: ...

    Cleanup

      >>> component.getGlobalSiteManager().unregisterUtility(
      ...    util, zope.locking.interfaces.ITokenUtility)
      True
      >>> component.getGlobalSiteManager().unregisterAdapter(
      ...    TokenBroker, (interface.Interface,),
      ...    zope.locking.interfaces.ITokenBroker)
      True
      >>> utils.now = oldNow

    """
    interface.implements(z3c.dav.interfaces.IDAVLockmanager)
    component.adapts(interface.Interface)

    def __init__(self, context):
        self.context = self.__parent__ = context

    def generateLocktoken(self):
        return "opaquelocktoken:%s-%s-00105A989226:%.03f" % \
               (_randGen.random(), _randGen.random(), time.time())

    def islockable(self):
        utility = component.queryUtility(zope.locking.interfaces.ITokenUtility,
                                         context = self.context, default = None)
        return utility is not None

    def lock(self, scope, type, owner, duration, depth,
             roottoken = None, context = None):
        if context is None:
            context = self.context

        tokenBroker = zope.locking.interfaces.ITokenBroker(context)
        if tokenBroker.get():
            raise z3c.dav.interfaces.AlreadyLocked(
                context, message = u"Context or subitem is already locked.")

        if roottoken is None:
            if scope == u"exclusive":
                roottoken = tokenBroker.lock(duration = duration)
            elif scope == u"shared":
                roottoken = tokenBroker.lockShared(duration = duration)
            else:
                raise z3c.dav.interfaces.UnprocessableError(
                    self.context,
                    message = u"Invalid lockscope supplied to the lock manager")

            annots = roottoken.annotations.get(WEBDAV_LOCK_KEY, None)
            if annots is None:
                annots = roottoken.annotations[WEBDAV_LOCK_KEY] = OOBTree()
            annots["owner"] = owner
            annots["token"] = self.generateLocktoken()
            annots["depth"] = depth
        else:
            indirecttoken = IndirectToken(context, roottoken)
            ## XXX - using removeSecurityProxy - is this right, has
            ## it seems wrong
            removeSecurityProxy(roottoken).utility.register(indirecttoken)

        if depth == "infinity" and IReadContainer.providedBy(context):
            for subob in context.values():
                self.lock(scope, type, owner, duration, depth,
                          roottoken, subob)

        return roottoken

    def getActivelock(self, request = None):
        if self.islocked():
            token = zope.locking.interfaces.ITokenBroker(self.context).get()
            return DAVActiveLockAdapter(token, self.context, request)
        return None

    def refreshlock(self, timeout):
        token = zope.locking.interfaces.ITokenBroker(self.context).get()
        token.duration = timeout

    def unlock(self):
        tokenBroker = zope.locking.interfaces.ITokenBroker(self.context)
        token = tokenBroker.get()
        token.end()

    def islocked(self):
        tokenBroker = zope.locking.interfaces.ITokenBroker(self.context)
        return tokenBroker.get() is not None
