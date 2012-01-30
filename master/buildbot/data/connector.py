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

from twisted.application import service
from buildbot.util import pathmatch
from buildbot.data import update
from buildbot.data import changes

class NoMatchError(Exception):
    pass

class DataConnector(service.Service):

    def __init__(self, master):
        self.setName('data')
        self.master = master
        self.update = update.UpdateComponent(master)

        self.matcher = pathmatch.Matcher()
        # TODO: this needs to happen automatically
        self.matcher[changes.Change.pathPattern] = changes.Change(master)
        self.matcher[changes.Changes.pathPattern] = changes.Changes(master)

    def get(self, options, path):
        endpoint, kwargs = self.matcher[path]
        return endpoint.get(options, kwargs)

    def startConsuming(self, callback, path):
        return self.master.mq.startConsuming(callback, '.'.join(path)) # TODO: wrong

    def control(self, action, args, path):
        endpoint, kwargs = self.matcher[path]
        return endpoint.control(action, args, kwargs)
