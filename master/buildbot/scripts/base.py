# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from __future__ import with_statement

import os
import copy
import stat
from twisted.python import usage, runtime

def isBuildmasterDir(dir):
    buildbot_tac = os.path.join(dir, "buildbot.tac")
    if not os.path.isfile(buildbot_tac):
        print "no buildbot.tac"
        return False

    with open(buildbot_tac, "r") as f:
        contents = f.read()
    return "Application('buildmaster')" in contents

class SubcommandOptions(usage.Options):
    # subclasses should set this to a list-of-lists in order to source the
    # .buildbot/options file.  Note that this *only* works with optParameters,
    # not optFlags.  Example:
    # buildbotOptions = [ [ 'optfile-name', 'parameter-name' ], .. ]
    buildbotOptions = None

    def __init__(self, *args):
        # for options in self.buildbotOptions, optParameters, and the options
        # file, change the default in optParameters to the value in the options
        # file, call through to the constructor, and then change it back.
        # Options uses reflect.accumulateClassList, so this *must* be a class
        # attribute; however, we do not want to permanently change the class.
        # So we patch it temporarily and restore it after.
        cls = self.__class__
        if hasattr(cls, 'optParameters'):
            old_optParameters = cls.optParameters
            cls.optParameters = op = copy.deepcopy(cls.optParameters)
            if self.buildbotOptions:
                optfile = self.optionsFile = self.loadOptionsFile()
                for optfile_name, option_name in self.buildbotOptions:
                    for i in range(len(op)):
                        if (op[i][0] == option_name
                                and optfile_name in optfile):
                            op[i] = list(op[i])
                            op[i][2] = optfile[optfile_name]
        usage.Options.__init__(self, *args)
        if hasattr(cls, 'optParameters'):
            cls.optParameters = old_optParameters

    def loadOptionsFile(self, _here=None):
        """Find the .buildbot/options file. Crawl from the current directory
        up towards the root, and also look in ~/.buildbot . The first directory
        that's owned by the user and has the file we're looking for wins.
        Windows skips the owned-by-user test.

        @rtype:  dict
        @return: a dictionary of names defined in the options file. If no
            options file was found, return an empty dict.
        """

        here = _here or os.path.abspath(os.getcwd())

        if runtime.platformType == 'win32':
            # never trust env-vars, use the proper API
            from win32com.shell import shellcon, shell
            appdata = shell.SHGetFolderPath(0, shellcon.CSIDL_APPDATA, 0, 0)
            home = os.path.join(appdata, "buildbot")
        else:
            home = os.path.expanduser("~/.buildbot")

        searchpath = []
        toomany = 20
        while True:
            searchpath.append(os.path.join(here, ".buildbot"))
            next = os.path.dirname(here)
            if next == here:
                break # we've hit the root
            here = next
            toomany -= 1 # just in case
            if toomany == 0:
                raise ValueError("Hey, I seem to have wandered up into the "
                                "infinite glories of the heavens. Oops.")
        searchpath.append(home)

        localDict = {}

        for d in searchpath:
            if os.path.isdir(d):
                if runtime.platformType != 'win32':
                    if os.stat(d)[stat.ST_UID] != os.getuid():
                        print "skipping %s because you don't own it" % d
                        continue # security, skip other people's directories
                optfile = os.path.join(d, "options")
                if os.path.exists(optfile):
                    try:
                        with open(optfile, "r") as f:
                            options = f.read()
                        exec options in localDict
                    except:
                        print "error while reading %s" % optfile
                        raise
                    break

        for k in localDict.keys():
            if k.startswith("__"):
                del localDict[k]
        return localDict