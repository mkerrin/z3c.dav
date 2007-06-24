======
WebDAV
======

The *z3c.dav* package is an implementation of the WebDAV protocol for Zope3.
*z3c.dav* only supports the *zope.app.folder* content type, within the core
RFC2518 protocol, but *z3c.dav* does contain a number of components that help
developers support WebDAV in their application. These components include
the ability to handle WebDAV specific errors, to generate multi-status
responses, and an implementation of all core WebDAV methods exist that use
zope component to lookup specific adapters that perform the required action.
For example `locking`_ looks up a IDAVLockmanager to perform the actual
locking and unlocking of objects. But if the required adapter does not
exist then a `405 Method Not Allowed` response is returned to the client.

In other to support the other standard Zope content types and services that
might be used within your application the following add on packages are
available:

* z3c.davapp.zopeappfile

  Defines a common WebDAV data model for zope.app.file.file.File, and
  zope.app.file.file.Image content objects.

* z3c.davapp.zopefile

  Defines a common WebDAV data model for zope.file.file.File content objects.

* z3c.davapp.zopelocking

  Implements wrappers around the zope.locking utility to integrate with
  z3c.dav.

Each of these packages uses an other Zope3 package to provide the underlying
functionality. For example *z3c.davapp.zopelocking* provides WebDAV locking
support by implementing a common IDAVLockmanager adapter defined in *z3c.dav*
which hooks into the z3c.dav locking mechanism to do the actual locking of
the objects while z3c.dav will parse the request from the client, lookup the
IDAVLockmanager and call some method on this adapter depending on the request.

More information
----------------

* `Data model`_

* `Locking`_

.. _data model: z3c.dav.datamodel/@@show.html

.. _locking: z3c.dav.locking/@@show.html
