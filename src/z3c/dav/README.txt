======
WebDAV
======

The *z3c.dav* package is an implementation of the WebDAV protocol for Zope3.
*z3c.dav* supports the *zope.app.folder* content type, within the scope of the
core RFC2518 protocol. *z3c.dav* also contains a number of components that
help developers support WebDAV in their application. These components include
the ability to handle WebDAV specific errors, to generate multi-status
responses, and an implementation of all core WebDAV methods exist that use
zope component to lookup specific adapters that perform the required action.
For example `locking`_ parses the request and then looks up a IDAVLockmanager
adapter to perform the locking and unlocking of objects. But if the required
adapter does not exist then a `405 Method Not Allowed` response is returned
to the client.

Add-on packages exist to support other standard Zope3 content types and
services. These include:

* z3c.davapp.zopeappfile

  Defines a common WebDAV data model for zope.app.file.file.File, and
  zope.app.file.file.Image content objects.

* z3c.davapp.zopefile

  Defines a common WebDAV data model for zope.file.file.File content objects.

* z3c.davapp.zopelocking

  Implements wrappers around the zope.locking utility to integrate with
  z3c.dav.

Each of these packages uses an other Zope3 package to provide the underlying
functionality.
