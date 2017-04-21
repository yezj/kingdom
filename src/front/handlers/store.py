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
    @api('Store info', '/store/info/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Store info")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        storeprod_list = yield self.redis.lrange('storeprod:%s' % uid, 0, -1)
        storerefresh = yield self.redis.get('storerefreshes:%s' % uid)
        if not storerefresh:
            storerefresh = 0
        prods = E.store(storerefresh)
        for key, value in prods.items():
            if key in storeprod_list:
                prods[key]['is_buy'] = 1
            else:
                prods[key]['is_buy'] = 0

        ret = dict(out=dict(prods=prods, refresh_times=storerefresh, dispear=3600), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)


@handler
class BuyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Store buy', '/store/buy/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        Param('pos', True, str, '0', '0', 'pos'),
        Param('pid', True, str, '01030', '01030', 'pid'),
        ], filters=[ps_filter], description="Store buy")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        try:
            pos = int(self.get_argument("pos"))
            pid = self.get_argument("pid")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        storeprod_list = yield self.redis.lrange('storeprod:%s' % uid, 0, -1)
        if int(pos) in storeprod_list:
            self.write(dict(err=E.ERR_DUPLICATE_BUY, msg=E.errmsg(E.ERR_DUPLICATE_BUY)))
            return
        storerefresh = yield self.redis.get('storerefreshes:%s' % uid)
        if not storerefresh:
            storerefresh = 0
        # if storerefresh > E.storemaxtimes(user['vrock']):
        #     self.write(dict(err=E.ERR_DISSATISFY_MAXREFRESHES, msg=E.errmsg(E.ERR_DISSATISFY_MAXREFRESHES)))
        #     return
        prods = E.store(storerefresh)
        for key, value in prods.items():
            if key in storeprod_list:
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
        user['gold'] -= prods[pos].get('gold', 0)
        if pid in user['prods']:
            user['prods'][pid] += int(prods[pos]['num'])
        else:
            user['prods'][pid] = int(prods[pos]['num'])
        if user['prods'][pid] > 9999:
            user['prods'][pid] = 9999
        yield self.set_consume(user, prods[pos].get('rock', 0))
        cuser = dict(prods=user['prods'], gold=user['gold'], rock=user['rock'])
        yield self.redis.lpush('storeprod:%s' % uid, pos)
        cwork = E.tagworks(user, {'STORE': 1})
        if cwork:
            cuser['works'] = user['works']
        logmsg = u'小铺:购买索引%s的%s' % (pos, pid)
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
    @api('Store refresh', '/store/refresh/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Store refresh")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        storerefresh = yield self.redis.get('storerefreshes:%s' % uid)
        if not storerefresh:
            storerefresh = 0
            yield self.redis.set('storerefreshes:%s' % uid, storerefresh)
        if storerefresh > E.storemaxtimes(user['vrock']):
            self.write(dict(err=E.ERR_DISSATISFY_MAXREFRESHES, msg=E.errmsg(E.ERR_DISSATISFY_MAXREFRESHES)))
            return
        if storerefresh > 20:
            storerefresh = 20
        if user['rock'] < D.STOREREFRESH[storerefresh*2+1]:
            self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
            return
        user['rock'] -= D.STOREREFRESH[storerefresh*2+1]
        yield self.set_consume(user, D.STOREREFRESH[storerefresh*2+1])
        storerefresh = yield self.redis.incr('storerefreshes:%s' % uid)
        yield self.redis.delete('storeprod:%s' % uid)
        prods = E.store(storerefresh)
        cuser = dict(rock=user['rock'])
        logmsg = u'小铺:第%s次刷新' % storerefresh
        yield self.set_user(uid, logmsg, **cuser)
        consume = yield self.get_consume(user)
        cuser['consume'] = consume
        ret = dict(out=dict(prods=prods, refresh_times=storerefresh), user=cuser, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

