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

from buildbot.data import base
from buildbot.util import datetime2epoch

def _fixChange(change):
    # TODO: make these mods in the DB API
    if change:
        change = change.copy()
        del change['is_dir']
        change['when_timestamp'] = datetime2epoch(change['when_timestamp'])
    return change


class Change(base.Endpoint):

    pathPattern = ( 'change', ':changeid' )

    def get(self, options, kwargs):
        d = self.master.db.changes.getChange(
                        int(kwargs.get('changeid')))
        d.addCallback(_fixChange)
        return d


class Changes(base.Endpoint):

    pathPattern = ( 'change', )

    def get(self, options, kwargs):
        try:
            count = min(int(options.get('count', '50')), 50)
        except:
            # TODO: raise a more handle-able error
            raise
        d = self.master.db.changes.getRecentChanges(count)
        @d.addCallback
        def sort(changes):
            changes.sort(key=lambda chdict : chdict['changeid'])
            return map(_fixChange, changes)
        return d
