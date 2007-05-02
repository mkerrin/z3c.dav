from setuptools import setup, find_packages

setup(name = "z3c.dav",
      version = "0.6",
      author = "Michael Kerrin",
      author_email = "michael.kerrin@openapp.ie",
      url = "http://svn.zope.org/z3c.dav",
      description = "Implementation of the WebDAV protocol for Zope3",
      license = "ZPL",

      packages = find_packages("src"),
      package_dir = {"": "src"},
      namespace_packages = ["z3c"],
      install_requires = ["setuptools",
                          "z3c.etree",
                          "zope.app.keyreference",
                          "zope.app.file",
                          "zope.locking",
                          "zc.i18n",
                          ],
      extras_require = dict(test = ["zope.app.zcmlfiles",
                                    "zope.app.securitypolicy",
                                    ]),

      include_package_data = True,
      zip_safe = False)
