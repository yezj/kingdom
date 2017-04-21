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
    @api('Market info', '/market/info/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Market info")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        marketprod_list = yield self.redis.lrange('marketprod:%s' % uid, 0, -1)
        marketrefresh = yield self.redis.get('marketrefreshes:%s' % uid)
        if not marketrefresh:
            marketrefresh = 0
        prods = E.market(marketrefresh)
        for key, value in prods.items():
            if key in marketprod_list:
                prods[key]['is_buy'] = 1
            else:
                prods[key]['is_buy'] = 0
        minterval = yield self.redis.get('market:%s' % uid)
        if not minterval:
            minterval = 0
        else:
            minterval = minterval - int(time.time())
        ret = dict(out=dict(prods=prods, refresh_times=marketrefresh, dispear=E.dispear, minterval=minterval), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)


@handler
class BuyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Market buy', '/market/buy/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        Param('pos', True, str, '0', '0', 'pos'),
        Param('pid', True, str, '01030', '01030', 'pid'),
        ], filters=[ps_filter], description="Market buy")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        minterval = yield self.redis.get('market:%s' % uid)
        if (E.vip(user['vrock']) < D.MARKET_PERMANENT) and (not minterval):
            self.write(dict(err=E.ERR_MARET_NOTFOUND, msg=E.errmsg(E.ERR_MARET_NOTFOUND)))
            return

        try:
            pos = int(self.get_argument("pos"))
            pid = self.get_argument("pid")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        marketprod_list = yield self.redis.lrange('marketprod:%s' % uid, 0, -1)
        if int(pos) in marketprod_list:
            self.write(dict(err=E.ERR_DUPLICATE_BUY, msg=E.errmsg(E.ERR_DUPLICATE_BUY)))
            return
        marketrefresh = yield self.redis.get('marketrefreshes:%s' % uid)
        if not marketrefresh:
            marketrefresh = 0
        prods = E.market(marketrefresh)
        for key, value in prods.items():
            if key in marketprod_list:
                prods[key]['is_buy'] = 1
            else:
                prods[key]['is_buy'] = 0
        #print prods[pos]['id'], pid, pos, prods
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
        yield self.set_consume(user, prods[pos].get('rock', 0))
        user['gold'] -= prods[pos].get('gold', 0)
        if pid in user['prods']:
            user['prods'][pid] += int(prods[pos]['num'])
        else:
            user['prods'][pid] = int(prods[pos]['num'])
        if user['prods'][pid] > 9999:
            user['prods'][pid] = 9999
        cuser = dict(prods=user['prods'], gold=user['gold'], rock=user['rock'])
        yield self.redis.lpush('marketprod:%s' % uid, pos)
        logmsg = u'集市:购买索引%s的%s' % (pos, pid)
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
    @api('Market refresh', '/market/refresh/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Market refresh")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        marketrefresh = yield self.redis.get('marketrefreshes:%s' % uid)
        if not marketrefresh:
            marketrefresh = 0
            yield self.redis.set('marketrefreshes:%s' % uid, marketrefresh)
        if marketrefresh > 20:
            marketrefresh = 20
        if marketrefresh > E.marketmaxtimes(user['vrock']):
            self.write(dict(err=E.ERR_DISSATISFY_MAXREFRESHES, msg=E.errmsg(E.ERR_DISSATISFY_MAXREFRESHES)))
            return
        if user['rock'] < D.MARKETREFRESH[marketrefresh*2+1]:
            self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
            return
        user['rock'] -= D.MARKETREFRESH[marketrefresh*2+1]
        yield self.set_consume(user, D.MARKETREFRESH[marketrefresh*2+1])
        marketrefresh = yield self.redis.incr('marketrefreshes:%s' % uid)
        yield self.redis.delete('marketprod:%s' % uid)
        prods = E.market(marketrefresh)
        cuser = dict(rock=user['rock'])
        logmsg = u'集市:第%s次刷新' % marketrefresh
        yield self.set_user(uid, logmsg, **cuser)
        consume = yield self.get_consume(user)
        cuser['consume'] = consume
        ret = dict(out=dict(prods=prods, refresh_times=marketrefresh), user=cuser, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

