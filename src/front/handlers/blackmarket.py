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
    @api('Blackmarket info', '/bm/info/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Blackmarket info")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        bmprod_list = yield self.redis.lrange('bmprod:%s' % uid, 0, -1)
        #print 'bmprod_list', bmprod_list
        bmrefresh = yield self.redis.get('bmrefreshes:%s' % uid)
        if not bmrefresh:
            bmrefresh = 0
        prods = E.blackmarket(bmrefresh)
        for key, value in prods.items():
            if key in bmprod_list:
                prods[key]['is_buy'] = 1
            else:
                prods[key]['is_buy'] = 0
        bminterval = yield self.redis.get('blackmarket:%s' % uid)
        if not bminterval:
            bminterval = 0
        else:
            bminterval = bminterval - int(time.time())
        ret = dict(out=dict(prods=prods, refresh_times=bmrefresh, dispear=E.dispear, bminterval=bminterval), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)


@handler
class BuyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Blackmarket buy', '/bm/buy/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        Param('pos', True, str, '0', '0', 'pos'),
        Param('pid', True, str, '01030', '01030', 'pid'),
        ], filters=[ps_filter], description="Blackmarket buy")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        bminterval = yield self.redis.get('blackmarket:%s' % uid)
        if (E.vip(user['vrock']) < D.BM_PERMANENT) and (not bminterval):
            self.write(dict(err=E.ERR_BLACKMARET_NOTFOUND, msg=E.errmsg(E.ERR_BLACKMARET_NOTFOUND)))
            return
        try:
            pos = int(self.get_argument("pos"))
            pid = self.get_argument("pid")
        except Exception:
            raise web.HTTPError(400, "Argument error")

        bmprod_list = yield self.redis.lrange('bmprod:%s' % uid, 0, -1)
        if int(pos) in bmprod_list:
            self.write(dict(err=E.ERR_DUPLICATE_BUY, msg=E.errmsg(E.ERR_DUPLICATE_BUY)))
            return
        bmrefresh = yield self.redis.get('bmrefreshes:%s' % uid)
        if not bmrefresh:
            bmrefresh = 0
        if bmrefresh > E.bmmaxtimes(user['vrock']):
            self.write(dict(err=E.ERR_DISSATISFY_MAXREFRESHES, msg=E.errmsg(E.ERR_DISSATISFY_MAXREFRESHES)))
            return
        prods = E.blackmarket(bmrefresh)
        for key, value in prods.items():
            if key in bmprod_list:
                prods[key]['is_buy'] = 1
            else:
                prods[key]['is_buy'] = 0
        try:
            assert prods[pos]['id'] == pid
        except Exception:
            raise web.HTTPError(400, "Argument error")

        if user['rock'] < prods[pos].get('rock', 0):
            self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
            return
        if user['gold'] < prods[pos].get('gold', 0):
            self.write(dict(err=E.ERR_NOTENOUGH_GOLD, msg=E.errmsg(E.ERR_NOTENOUGH_GOLD)))
            return
        user['rock'] -= prods[pos].get('rock', 0)
        consume = yield self.set_consume(user, prods[pos].get('rock', 0))
        user['gold'] -= prods[pos].get('gold', 0)
        if pid in user['prods']:
            user['prods'][pid] += int(prods[pos]['num'])
        else:
            user['prods'][pid] = int(prods[pos]['num'])
        if user['prods'][pid] > 999:
            user['prods'][pid] = 999
        cuser = dict(prods=user['prods'], gold=user['gold'], rock=user['rock'])
        yield self.redis.lpush('bmprod:%s' % uid, pos)
        logmsg = u'黑市:购买索引%s的%s' % (pos, pid)
        yield self.set_user(uid, logmsg, **cuser)
        consume = yield self.get_consume(user)
        cuser['consume'] = consume
        ret = dict(user=cuser, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class RefreshHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Blackmarket refresh', '/bm/refresh/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Blackmarket refresh")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        bmrefresh = yield self.redis.get('bmrefreshes:%s' % uid)
        if not bmrefresh:
            bmrefresh = 0
            yield self.redis.set('bmrefreshes:%s' % uid, bmrefresh)
        if bmrefresh > 20:
            bmrefresh = 20
        #print D.BMREFRESH[bmrefresh*2+1]
        if user['rock'] < D.BMREFRESH[bmrefresh*2+1]:
            self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
            return
        user['rock'] -= D.BMREFRESH[bmrefresh*2+1]
        consume = yield self.set_consume(user, D.BMREFRESH[bmrefresh*2+1])
        bmrefresh = yield self.redis.incr('bmrefreshes:%s' % uid)
        yield self.redis.delete('bmprod:%s' % uid)
        prods = E.blackmarket(bmrefresh)
        cuser = dict(rock=user['rock'])
        logmsg = u'黑市:第%s次刷新' % bmrefresh
        yield self.set_user(uid, logmsg, **cuser)
        consume = yield self.get_consume(user)
        cuser['consume'] = consume
        ret = dict(out=dict(prods=prods, refresh_times=bmrefresh), user=cuser, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

