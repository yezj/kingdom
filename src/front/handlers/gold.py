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
    @api('Gold info', '/gold/info/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Gold info")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        buytimes = yield self.redis.get('goldbuytimes:%s' % uid)
        maxtimes = E.goldmaxtimes(user['vrock'])
        if not buytimes:
            buytimes = 0
            yield self.redis.set('goldbuytimes:%s' % uid, buytimes)
        lefttimes = maxtimes - buytimes
        if lefttimes < 0:
            lefttimes = 0
        ret = dict(buytimes=buytimes, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class BuyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Gold buy', '/gold/buy/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('times', True, int, 1, 1, 'times'),
        ], filters=[ps_filter], description="Gold buy")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)

        buytimes = yield self.redis.get('goldbuytimes:%s' % uid)
        if not buytimes:
            buytimes = 0
            yield self.redis.set('goldbuytimes:%s' % uid, buytimes)
        maxtimes = E.goldmaxtimes(user['vrock'])
        if self.has_arg('times'):
            if (int(self.arg('times')) + buytimes) > maxtimes:
                self.write(dict(err=E.ERR_DISSATISFY_MAXBUYTIMES, msg=E.errmsg(E.ERR_DISSATISFY_MAXBUYTIMES)))
                return
            else:
                buy = E.buy4gold(buytimes, int(self.arg('times')), user['xp'])
                rock = 0
                gold = 0
                for one in buy:
                    rock += one.get('rock', 0)
                    gold += one.get('gold', 0)
                    gold += one.get('extra', 0)
                if user['rock'] < rock:
                    self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
                    return
                user['rock'] -= rock
                consume = yield self.set_consume(user, rock)
                user['gold'] += gold
                cuser = dict(rock=user['rock'], gold=user['gold'])
                cwork = E.tagworks(user, {'GOLD': 1})
                if cwork:
                    cuser['works'] = user['works']

                logmsg = u'金币:购买%s次' % self.arg('times')
                yield self.set_user(uid, logmsg, **cuser)
                #yield self.redis.set('goldbuytimes:%s' % uid, buytimes+int(self.arg('times')))
                consume = yield self.get_consume(user)
                cuser['consume'] = consume
                ret = dict(user=cuser, buy=buy, timestamp=int(time.time()))
                reb = zlib.compress(escape.json_encode(ret))
                self.write(ret)
                yield self.redis.incr('goldbuytimes:%s' % uid, int(self.arg('times')))
        else:
            raise web.HTTPError(400, "Argument error")
