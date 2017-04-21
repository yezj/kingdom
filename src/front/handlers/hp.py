# -*- coding: utf-8 -*-

import random
import time
import zlib
import uuid
import json
import datetime
import pickle
from twisted.internet import defer
from cyclone import escape, web
from front import storage
from front import utils
from front.utils import E
from front.wiapi import *
from front import D
from front.handlers.base import ApiHandler, ApiJSONEncoder
from local_settings import ZONE_ID
@handler
class InfoHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hp info', '/hp/info/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Hp info")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        buytimes = yield self.redis.get('hpbuytimes:%s' % uid)
        if not buytimes:
            buytimes = 0
            yield self.redis.set('hpbuytimes:%s' % uid, buytimes)

        ret = dict(buytimes=buytimes, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class BuyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hp buy', '/hp/buy/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Hp buy")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        buytimes = yield self.redis.get('hpbuytimes:%s' % uid)
        maxtimes = E.hpmaxtimes(user['vrock'])
        if buytimes < maxtimes:
            cost = E.buy4hp(buytimes)
            if user['rock'] < cost.get('rock', 0):
                self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
                return
            user['rock'] -= cost.get('rock', 0)
            yield self.set_consume(user, cost.get('rock', 0))
            hp, tick = yield self.add_hp(user, cost.get('hp', 0), u'购买体力(第%s次)' % (buytimes+1))
            hp, tick = yield self.get_hp(user)

            cuser = dict(rock=user['rock'])
            logmsg = u'体力:第%s次购买' % (buytimes+1)
            yield self.set_user(uid, logmsg, **cuser)
            consume = yield self.get_consume(user)
            cuser['hp'] = hp
            cuser['tick'] = tick
            cuser['consume'] = consume
            yield self.redis.incr('hpbuytimes:%s' % uid)
            ret = dict(user=cuser, timestamp=int(time.time()))
            reb = zlib.compress(escape.json_encode(ret))
            self.write(ret)
        else:
            self.write(dict(err=E.ERR_DISSATISFY_MAXBUYTIMES, msg=E.errmsg(E.ERR_DISSATISFY_MAXBUYTIMES)))
            return


