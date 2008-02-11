from setuptools import setup, find_packages

setup(name = "z3c.dav",
      version = "1.0b2",
      author = "Michael Kerrin",
      author_email = "michael.kerrin@openapp.ie",
      url = "http://launchpad.net/z3c.dav",
      description = "Implementation of the WebDAV protocol for Zope3",
      long_description = (
          open("src/z3c/dav/README.txt").read() +
          "\n\n" +
          open("CHANGES.txt").read()),
      license = "ZPL",
      classifiers = ["Environment :: Web Environment",
                     "Intended Audience :: Developers",
                     "License :: OSI Approved :: Zope Public License",
                     "Programming Language :: Python",
                     "Framework :: Zope3",
                     ],

      packages = find_packages("src"),
      package_dir = {"": "src"},
      namespace_packages = ["z3c"],
      install_requires = ["setuptools",
                          "z3c.etree",
                          "z3c.conditionalviews",
                          "zope.app.zcmlfiles",
                          "zope.securitypolicy",
                          ],

      include_package_data = True,
      zip_safe = False)
