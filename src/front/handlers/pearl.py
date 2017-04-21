# -*- coding: utf-8 -*-

import random
import time
import zlib
import uuid
import json
import datetime
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
    @api('Pearl info', '/pearl/info/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Pearl info")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        buytimes = yield self.redis.get('pearlbuytimes:%s' % uid)
        if not buytimes:
            buytimes = 0
            yield self.redis.set('pearlbuytimes:%s' % uid, buytimes)

        ret = dict(buytimes=buytimes, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class BuyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Pearl buy', '/pearl/buy/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Pearl buy")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        buytimes = yield self.redis.get('pearlbuytimes:%s' % uid)
        if not buytimes:
            buytimes = 0
        maxtimes = E.pearlmaxtimes(user['vrock'])
        if buytimes < maxtimes:
            cost = E.buy4pearl(buytimes)
            if user['rock'] < cost.get('rock', 0):
                self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
                return
            user['rock'] -= cost.get('rock', 0)
            consume = yield self.set_consume(user, cost.get('rock', 0))
            for p, n in cost.get('prods', {}).items():
                #print p, n
                if p in user['prods']:
                    user['prods'][p] += n 
                else:
                    user['prods'][p] = n 
                if user['prods'][p] > 9999:
                    user['prods'][p] = 9999
                elif user['prods'][p] == 0:
                    del user['prods'][p]
                else:pass
            cuser = dict(rock=user['rock'], prods=user['prods'])
            logmsg = u'珍珠:第%s次购买' % (buytimes+1)
            yield self.set_user(uid, logmsg, **cuser)
            consume = yield self.get_consume(user)
            cuser['consume'] = consume
            ret = dict(user=cuser, timestamp=int(time.time()))
            reb = zlib.compress(escape.json_encode(ret))
            self.write(ret)
            yield self.redis.incr('pearlbuytimes:%s' % uid)
        else:
            self.write(dict(err=E.ERR_DISSATISFY_MAXBUYTIMES, msg=E.errmsg(E.ERR_DISSATISFY_MAXBUYTIMES)))
            return
