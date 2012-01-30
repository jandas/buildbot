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

from buildbot.www import json
from buildbot.test.util import www
from twisted.trial import unittest
from twisted.internet import defer

class TestRoot(www.WwwTestMixin, unittest.TestCase):

    def test_render(self):
        master = self.make_master(url='h:/a/b/')
        rsrc = json.JsonRootResource(master)

        d = self.render_resource(rsrc, [''])
        @d.addCallback
        def check(rv):
            self.assertIn('api_versions', rv)
        return d

class TestBase(www.WwwTestMixin, unittest.TestCase):

    class Subclass(json.JsonBaseResource):

        # note that this subclass declaration in itself exercises the
        # path(..) decorator

        @json.JsonBaseResource.path('foo')
        def json_foo(self, request):
            return [ 'foo', 'bar', None, {} ]

        @json.JsonBaseResource.path('def')
        def json_def(self, request):
            return defer.succeed(dict(ab='cd'))

        @json.JsonBaseResource.path('args', '$a', '$b')
        def json_args(self, request, b, a):
            return defer.succeed(dict(a=a, b=b))

    def setUp(self):
        self.master = self.make_master(url='h:/')
        self.rsrc = self.Subclass(self.master)

    def test_api_req(self):
        d = self.render_resource(self.rsrc, ['foo'])
        @d.addCallback
        def check(rv):
            self.assertEqual(rv, '["foo","bar",null,{}]')
            self.assertEqual(self.request.headers['content-type'],
                    [ 'application/json' ])
            self.assertEqual(self.request.headers['content-disposition'],
                    [ "attachment; filename=\"/req.path.json\"" ])
        return d

    def test_api_req_as_text(self):
        d = self.render_resource(self.rsrc, ['foo'], args={'as_text': ['1']})
        @d.addCallback
        def check(rv):
            self.assertEqual(rv, '[\n  "foo", \n  "bar"\n]') # note: filtered
            self.assertEqual(self.request.headers['content-type'],
                    [ 'text/plain' ])
            self.assertEqual(self.request.headers.get('content-disposition'),
                    None)
        return d

    def test_api_req_as_text_compact(self):
        d = self.render_resource(self.rsrc, ['foo'],
                args={'as_text': ['1'], 'compact': ['1']})
        @d.addCallback
        def check(rv):
            self.assertEqual(rv, '["foo","bar"]') # note: filtered
        return d

    def test_api_req_filter(self):
        d = self.render_resource(self.rsrc, ['foo'], args={'filter': ['1']})
        @d.addCallback
        def check(rv):
            self.assertEqual(rv, '["foo","bar"]')
        return d

    def test_api_req_callback(self):
        d = self.render_resource(self.rsrc, ['foo'],
                args={'callback': ['xyz']})
        @d.addCallback
        def check(rv):
            self.assertEqual(rv, 'xyz(["foo","bar",null,{}]);')
            self.assertEqual(
                    self.request.headers["Access-Control-Allow-Origin"],
                    ["*"])
        return d

    def test_api_cache_headers(self):
        self.master.config.www['json_cache_seconds'] = 10
        self.patch(datetime.datetime, 'utcnow'
        d = self.render_resource(self.rsrc, ['foo'],
                args={'callback': ['xyz']})
        @d.addCallback
        def check(rv):
            self.assertEqual(rv, 'xyz(["foo","bar",null,{}]);')
            self.assertEqual(
                    self.request.headers["Access-Control-Allow-Origin"],
                    ["*"])
        return d
