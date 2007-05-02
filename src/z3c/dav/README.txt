============
Introduction
============

The *z3c.dav* package is an implementation of the WebDAV protocol.
It includes support for all the different methods, properties and error codes
has defined in RFC2518 and draft-ietf-webdav-rfc2518bis-15.txt.

Installation
============

This module should be installed like any other Zope3 module, that is it should
be copied verbatim into your Python path and all zcml slugs should be installed
into the *package-includes* directory. The zcml slugs for this package include
*z3c.dav-configure.zcml* and *ietree-configure.zcml*. If you want to run
the functional tests successfully then you must also install the
*z3c.dav-ftesting.zcml* file.

Now the *ietree-configure.zcml* file tells Zope what ElementTree engine you
want to use to process the XML. You will probably want to edit this file to
use the elementtree implementation that is installed on your system. There are
two supported implementations, ElementTree and lxml. To use ElementTree
just make sure that the utility declaration for *z3c.dav.zetree.EtreeEtree*
is the only uncommented utility declaration. For lxml just make sure that
*z3c.dav.zetree.LxmlEtree* is the only uncommented utility declaration.

Data Model
==========

Read how to extend the `WebDAV Data Model`_ by defining your own properties.

XML Processing
==============

WebDAV uses XML for conveying property names and values to and from the client.
This package uses ElementTree API for processing this XML. Because of this all
property names must be strings that conform to the syntax of ElementTree's
element name (or tag). For example, for the property *getcontenttype* which
belongs to the *DAV:* XML namespace will be referenced by the name
*{DAV:}getcontenttype* within *z3c.dav*.

Error Handling
==============

WebDAV defines new HTTP status codes in order convey more meaningful
information about what just happened back to the client. The WebDAV
specification also defines a multi-status response (with HTTP status code
207) for situations where multiple status codes are more appropriate. For
example the PROPPATCH method can modify multiple properties with multiple
degrees of success. For each property we can say if the property update
succeeded, failed, the property did not exists, or the user did not have the
appropriate permissions to modify that property. To deal with this we have
defined new exceptions that should be raised if a request can not be processed
for a specific reason.

When a multi-status response is desirable then *z3c.dav* will encapsulate
all the errors that occurred during the request into either a
*webdav.interfaces.WebDAVErrors* or a *webdav.interfaces.WebDAVPropstatErrors*
exception and throw this error to the publisher. The publisher will then abort
the current transaction and look up and render a *IHTTPException* view of this
error.

This view will generally be either *webdav.exceptions.MultiStatusErrorView* or
*webdav.exceptions.WebDAVPropstatErrorView*. Both these views work by looping
over all exceptions contained within the error and for each error it looks up
a *webdav.interfaces.IDAVErrorWidget* which will contain all the information
necessary to build up the final multi-status XML element which is sent back
to the client.

Each of these new exception implemented a derived interface of the
*webdav.interfaces.IDAVException* interface (although this isn't necessary).
As of writing the following exceptions can occur:

+ *webdav.interfaces.ConflictError*

+ *webdav.interfaces.ForbiddenError*

+ *webdav.interfaces.UnprocessableError*

+ *webdav.interfaces.PropertyNotFound*

+ *webdav.interfaces.PreconditionFailed*

+ *webdav.interfaces.FailedDependency*

+ *webdav.interfaces.AlreadyLocked*

.. _WebDAV Data Model: z3c.dav.datamodel/@@show.html
