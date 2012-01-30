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

import mock
from twisted.internet import defer
from twisted.web import server

class FakeRequest(object):
    written = ''
    finished = False
    redirected_to = None
    failure = None
    method = 'GET'
    path = '/req.path'

    def __init__(self, postpath=None, args={}):
        self.headers = {}
        self.prepath = []
        self.postpath = postpath or []
        self.deferred = defer.Deferred()
        self.args = args

    def write(self, data):
        self.written = self.written + data

    def redirect(self, url):
        self.redirected_to = url

    def finish(self):
        self.finished = True
        self.deferred.callback(self.written)

    def setHeader(self, hdr, value):
        self.headers.setdefault(hdr, []).append(value)

    def processingFailed(self, f):
        self.deferred.errback(f)

class WwwTestMixin(object):

    def make_master(self, **kwargs):
        master = mock.Mock(name='master')
        cfg = dict(url='//', port=None)
        cfg.update(kwargs)
        master.config.www = cfg
        return master

    def make_request(self, postpath=None, args={}):
        self.request = FakeRequest(postpath=postpath, args=args)
        return self.request

    def render_resource(self, rsrc, postpath=None, args={}, request=None):
        # pass *either* a request or postpath (and optionally args)
        if not request:
            request = self.make_request(postpath=postpath, args=args)

        rv = rsrc.render(request)
        if rv != server.NOT_DONE_YET:
            return defer.succeed(rv)
        return request.deferred
