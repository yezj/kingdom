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
from cyclone import escape, web
from front import storage
from front import utils
from front.utils import E
from front.wiapi import *
from front import D
from front.handlers.base import ApiHandler, ApiJSONEncoder


@handler
class InfoHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Beauty info', '/beauty/info/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Beauty info")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        res = yield self.sql.runQuery("SELECT beautyid FROM core_beauty")
        beautys = {}
        for r in res:
            if r[0] in user['beautys']:
                beautys[r[0]] = user['beautys'][r[0]]
            else:
                beautys[r[0]] = -1
        ret = dict(out=dict(beautys=beautys), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class GetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Beauty get', '/beauty/get/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        Param('bid', True, str, '06001', '06001', 'bid'),
        ], filters=[ps_filter], description="Beauty set")
    def post(self):
        try:
            bid = self.get_argument("bid")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        if bid in user['beautys']:
            self.write(dict(err=E.ERR_BEAUTY_ALREADYGOT, msg=E.errmsg(E.ERR_BEAUTY_ALREADYGOT)))
            return
        res = yield self.sql.runQuery("SELECT name, level, gold, rock, prods, nums FROM core_beauty where beautyid=%s" % (repr(str(bid)), ))
        if res:
            name, level, gold, rock, prods, nums = res[0]
            if user['xp']/100000 + 1 < level:
                self.write(dict(err=E.ERR_NOTENOUGH_XP, msg=E.errmsg(E.ERR_NOTENOUGH_XP)))
                return
            if prods:
                prop = dict(zip(prods.strip().split(','), nums.strip().split(',')))
            else:
                prop = {}
            if user['rock'] < int(rock):
                self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
                return
            if user['gold'] < int(gold):
                self.write(dict(err=E.ERR_NOTENOUGH_GOLD, msg=E.errmsg(E.ERR_NOTENOUGH_GOLD)))
                return
            user['rock'] -= int(rock)
            consume = yield self.set_consume(user, int(rock))
            user['gold'] -= int(gold)
            for prod, n in prop.items():
                if prod in user['prods'] and int(n) <= user['prods'][prod]:
                    user['prods'][prod] -= int(n)
                else:
                    self.write(dict(err=E.ERR_NOTENOUGH_PROD, msg=E.errmsg(E.ERR_NOTENOUGH_PROD)))
                    return
                if user['prods'][prod] == 0:
                    del user['prods'][prod]
            user['beautys'][bid] = 0
            yield self.redis.rpush("message", pickle.dumps([D.BEAUTYMESSAGE[0] % (user['nickname'], name), D.BEAUTYMESSAGE[1] % int(time.time())]))
            cuser = dict(gold=user['gold'], rock=user['rock'], prods=user['prods'], beautys=user['beautys'])
            logmsg = u'美人:召唤%s' % bid
            yield self.set_user(uid, logmsg, **cuser)
            consume = yield self.get_consume(user)
            cuser['consume'] = consume
            ret = dict(user=cuser, timestamp=int(time.time()))
            reb = zlib.compress(escape.json_encode(ret))
            self.write(ret)
        else:
            raise web.HTTPError(400, "Argument error")

@handler
class SetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Beauty set', '/beauty/set/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('bid', True, str, '06001', '06001', 'bid'),
        Param('type', True, str, '0/1', '0', 'type'),
        ], filters=[ps_filter], description="Beauty set")
    def post(self):
        try:
            bid = self.get_argument("bid")
            btype = int(self.get_argument("type"))
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        #print repr(str(bid)), bid
        res = yield self.sql.runQuery("SELECT name FROM core_beauty where beautyid=%s" % (repr(str(bid)), ))
        if res:
            beautyname, = res[0]
        else:
            raise web.HTTPError(400, "Argument error")
        if bid not in user['beautys']:
            raise web.HTTPError(400, "Argument error")
        if user['beautys'][bid] >= 100:
            self.write(dict(err=E.ERR_MAXLEVEL_ALREADYGOT, msg=E.errmsg(E.ERR_MAXLEVEL_ALREADYGOT)))
            return
        cost = E.cost4beauty(btype, user['beautys'][bid])
        if cost:
            if user['rock'] < cost.get('rock', 0):
                self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
                return
            if user['gold'] < cost.get('gold', 0):
                self.write(dict(err=E.ERR_NOTENOUGH_GOLD, msg=E.errmsg(E.ERR_NOTENOUGH_GOLD)))
                return
            user['rock'] -= cost.get('rock', 0)
            consume = yield self.set_consume(user, cost.get('rock', 0))
            user['gold'] -= cost.get('gold', 0)
            for prod, n in cost.get('prods', {}).items():
                if prod in user['prods'] and int(n) <= user['prods'][prod]:
                    user['prods'][prod] -= int(n)
                else:
                    self.write(dict(err=E.ERR_NOTENOUGH_PROD, msg=E.errmsg(E.ERR_NOTENOUGH_PROD)))
                    return
                if user['prods'][prod] ==0:
                    del user['prods'][prod]
            rand = 1
            if btype == 1 and random.random() < D.BEAUTYPROBA:
                rand = 2
            user['beautys'][bid] += rand
            if user['beautys'][bid] > 100:
                user['beautys'][bid] = 100
            yield self.redis.rpush("message", pickle.dumps([D.LINGERMESSAGE[0] % (user['nickname'], beautyname, user['beautys'][bid]), D.LINGERMESSAGE[1] % int(time.time())]))
            cuser = dict(gold=user['gold'], rock=user['rock'], prods=user['prods'], beautys=user['beautys'])
            cwork = E.tagworks(user, {'BEAUTY': 1})
            if cwork:
                cuser['works'] = user['works']
            logmsg = u'美人:升级%s' % bid
            yield self.set_user(uid, logmsg, **cuser)
            consume = yield self.get_consume(user)
            cuser['consume'] = consume
            ret = dict(user=cuser, timestamp=int(time.time()))
            reb = zlib.compress(escape.json_encode(ret))
            self.write(ret)
        else:
            raise web.HTTPError(400, "Argument error")
