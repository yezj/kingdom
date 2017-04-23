# -*- coding: utf-8 -*-

import random
import time
import zlib
import uuid
import json
import datetime

import pickle
import copy
from twisted.internet import defer
from twisted.python import log
from cyclone import escape, web
from front import storage
from front import utils
from front.utils import E
from front.wiapi import *
from front import D
from front.handlers.base import ApiHandler, ApiJSONEncoder


@handler
class IndexHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Guild', '/guild/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
    ], filters=[ps_filter], description="Get guild")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        print user
        guilds = {}
        query = "SELECT id, name, notice, creator, president, vice_presidents, members, timestamp FROM core_guild ORDER BY timestamp"
        res = yield self.sql.runQuery(query)
        if res:
            for r in res:
                id, name, notice, creator, president, vice_presidents, members, timestamp = r
                guilds[id] = dict(
                    name=name,
                    notice=notice or '',
                    creator=creator,
                    president=president,
                    vice_presidents=escape.json_decode(vice_presidents),
                    members=escape.json_decode(members),
                    timestamp=timestamp
                )
        else:
            guilds = dict()
        ret = dict(guilds=guilds, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)


@handler
class CreateHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Guild create', '/guild/create/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('name', True, str, '汉大帮', '汉大帮', 'name'),
    ], filters=[ps_filter], description="Guild create")
    def post(self):
        try:
            name = self.get_argument("name")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        query = "SELECT id, name, notice, creator, president, vice_presidents, members, timestamp FROM core_guild" \
                " WHERE creator=%s"
        params = (str(uid),)
        res = yield self.sql.runQuery(query, params)
        if res:
            self.write(dict(err=E.ERR_CREATE_GUILD_REPEAT, msg=E.errmsg(E.ERR_CREATE_GUILD_REPEAT)))
            return
        else:
            gid = yield self.create_guild(str(uid), name)
            ret = dict(timestamp=int(time.time()), gid=gid)
            reb = zlib.compress(escape.json_encode(ret))
            self.write(ret)


@handler
class JoinHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Guild join', '/guild/join/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('gid', True, str, '1', '1', 'gid'),
    ], filters=[ps_filter], description="Guild join")
    def post(self):
        try:
            gid = self.get_argument("gid")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        query = "SELECT members FROM core_guild"
        res = yield self.sql.runQuery(query)
        IS_JIONED = False
        if res:
            for r in res:
                if str(uid) in escape.json_decode(r[0]):
                    IS_JIONED
        if IS_JIONED:
            self.write(dict(err=E.ERR_JOIN_GUILD_REPEAT, msg=E.errmsg(E.ERR_JOIN_GUILD_REPEAT)))
            return

        query = "SELECT id, name, notice, creator, president, vice_presidents, members, timestamp FROM core_guild" \
                " WHERE id=%s LIMIT 1"
        params = (gid,)
        res = yield self.sql.runQuery(query, params)
        if res:
            id, name, notice, creator, president, vice_presidents, members, timestamp = res[0]
            members = escape.json_decode(members)
            if str(uid) in members:
                self.write(dict(err=E.ERR_JOIN_GUILD_REPEAT, msg=E.errmsg(E.ERR_JOIN_GUILD_REPEAT)))
                return
            else:
                members.append(str(uid))
                yield self.update_guild_members(gid, president, vice_presidents, members)
        ret = dict(timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)


@handler
class QuitHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Guild quit', '/guild/quit/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('gid', True, str, '1', '1', 'gid'),
    ], filters=[ps_filter], description="Guild quit")
    def post(self):
        try:
            gid = self.get_argument("gid")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        query = "SELECT id, name, notice, creator, president, vice_presidents, members, timestamp FROM core_guild" \
                " WHERE id=%s LIMIT 1"

        params = (gid,)
        res = yield self.sql.runQuery(query, params)
        if res:
            id, name, notice, creator, president, vice_presidents, members, timestamp = res[0]
            members = escape.json_decode(members)
            vice_presidents = escape.json_decode(vice_presidents)
            if str(uid) in members:
                del members[str(uid)]
                if str(uid) in vice_presidents:
                    del vice_presidents[str(uid)]
                yield self.update_guild_members(gid, president, vice_presidents, members)
            else:
                self.write(dict(err=E.ERR_QUIT_GUILD_REPEAT, msg=E.errmsg(E.ERR_QUIT_GUILD_REPEAT)))
                return
        ret = dict(timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)


@handler
class SetPresidentHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Set president', '/set/president/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('gid', True, str, '1', '1', 'gid'),
        Param('president_id', True, str, '1', '1', 'president_id'),
    ], filters=[ps_filter], description="Set president")
    def post(self):
        try:
            gid = self.get_argument("gid")
            president_id = self.get_argument("president_id")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        query = "SELECT id, name, notice, creator, president, vice_presidents, members, timestamp FROM core_guild" \
                " WHERE id=%s LIMIT 1"

        params = (gid,)
        res = yield self.sql.runQuery(query, params)
        if res:
            id, name, notice, creator, president, vice_presidents, members, timestamp = res[0]
            members = escape.json_decode(members)
            vice_presidents = escape.json_decode(vice_presidents)
            if str(president_id) not in members:
                self.write(dict(err=E.ERR_NOTEXIST_GUILD_USER, msg=E.errmsg(E.ERR_NOTEXIST_GUILD_USER)))
                return
            if str(president_id) in vice_presidents:
                del vice_presidents[str(president_id)]
            president = uid
            yield self.update_guild_members(gid, president, vice_presidents, members)
        ret = dict(timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)


@handler
class SetVicePresidentHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Set vpresident', '/set/vpresident/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('gid', True, str, '1', '1', 'gid'),
        Param('vice_president_id', True, str, '1', '1', 'vice_president_id'),
    ], filters=[ps_filter], description="Set vpresident")
    def post(self):
        try:
            gid = self.get_argument("gid")
            vice_president_id = self.get_argument("vice_president_id")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        query = "SELECT id, name, notice, creator, president, vice_presidents, members, timestamp FROM core_guild" \
                " WHERE id=%s AND creator=%s LIMIT 1"

        params = (gid, uid)
        res = yield self.sql.runQuery(query, params)
        if res:
            id, name, notice, creator, president, vice_presidents, members, timestamp = res[0]
            members = escape.json_decode(members)
            vice_presidents = escape.json_decode(vice_presidents)
            if str(vice_president_id) not in members:
                self.write(dict(err=E.ERR_NOTEXIST_GUILD_USER, msg=E.errmsg(E.ERR_NOTEXIST_GUILD_USER)))
                return
            vice_presidents.append(vice_president_id)
            yield self.update_guild_members(gid, president, vice_presidents, members)
        ret = dict(timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)
