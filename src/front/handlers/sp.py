# -*- coding: utf-8 -*-

import time
import zlib
from twisted.internet import defer
from cyclone import escape, web
from front import storage
from front import utils
from front.utils import E
# from front.handlers.base import BaseHandler
from front.wiapi import *
from front.handlers.base import ApiHandler, ApiJSONEncoder

@handler
class InfoHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Sp info', '/sp/info/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Sp info")
    def post(self):

        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return

        uid = self.uid
        user = yield self.get_user(uid)
        buytimes = yield self.redis.get('spbuytimes:%s' % uid)
        if not buytimes:
            buytimes = 0
            yield self.redis.set('spbuytimes:%s' % uid, buytimes)
        sp, tick = yield self.get_sp(user)
        ret = dict(out=dict(buytimes=buytimes, sp=sp, interval=tick), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)
        if uu:
            yield self.set_uu(uu, ret)

@handler
class BuyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Sp buy', '/sp/buy/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Sp buy")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        buytimes = yield self.redis.get('spbuytimes:%s' % uid)
        if not buytimes:
            buytimes = 0
        maxtimes = E.spmaxtimes(user['vrock'])
        if buytimes < maxtimes:
            cost = E.buy4sp(buytimes)
            if user['rock'] < cost.get('rock', 0):
                self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
                return
            user['rock'] -= cost.get('rock', 0)
            yield self.set_consume(user, cost.get('rock', 0))
            cuser = dict(rock=user['rock'])
            logmsg = u'技能点:第%s次购买' % (buytimes+1)
            yield self.set_user(uid, logmsg, **cuser)
            sp, tick = yield self.add_sp(user, cost.get('sp', 0))
            consume = yield self.get_consume(user)
            cuser['consume'] = consume
            ret = dict(out=dict(sp=sp), user=cuser, timestamp=int(time.time()))
            reb = zlib.compress(escape.json_encode(ret))
            self.write(ret)
            yield self.redis.incr('spbuytimes:%s' % uid)
        else:
            self.write(dict(err=E.ERR_DISSATISFY_MAXBUYTIMES, msg=E.errmsg(E.ERR_DISSATISFY_MAXBUYTIMES)))
            return

