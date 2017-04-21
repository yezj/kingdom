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
from local_settings import ZONE_ID

@handler
class InfoHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Worship info', '/worship/info/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Worship info")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        worshiptimes = yield self.redis.get('worshiptimes:%s' % uid)
        if not worshiptimes:
            worshiptimes = 0
        worshipers = yield self.predis.get('worshipers:%s' % ZONE_ID)
        if worshipers:
            worshipers = pickle.loads(worshipers)
        else:
            worshipers = []
            res = yield self.sql.runQuery("SELECT a.id, a.nickname, a.avat, a.xp, b.now_rank FROM core_user AS a,\
             core_arena AS b WHERE a.id=b.user_id AND b.now_rank<%s" % D.WORSHIPRANK)
            if res:
                for r in res:
                    worshipers.append(dict(uid=r[0], nickname=r[1], avat=r[2], xp=r[3], now_rank=r[4]))

            yield self.predis.set('worshipers:%s' % ZONE_ID, pickle.dumps(worshipers))

        ret = dict(out=dict(worshipers=worshipers, worshiptimes=worshiptimes), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)


@handler
class SetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Worship set', '/worship/set/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        Param('cid', True, str, '1', '1', 'cid'),
        Param('type', True, int, '1/2/3', 1, 'type'),
        ], filters=[ps_filter], description="Worship set")
    def post(self):
        try:
            wtype = int(self.get_argument("type"))
            cid = self.get_argument("cid")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        res = yield self.sql.runQuery("SELECT a.id, a.nickname, a.avat, a.xp, b.now_rank FROM core_user AS a,\
         core_arena AS b WHERE a.id=b.user_id AND a.id=%s" % cid)
        if not res:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        worshiptimes = yield self.redis.get('worshiptimes:%s' % uid)
        if not worshiptimes:
            worshiptimes = 0
        if worshiptimes >= E.warshiptimes(user['vrock']):
            self.write(dict(err=E.ERR_DISSATISFY_MAXWORSHIPS, msg=E.errmsg(E.ERR_DISSATISFY_MAXWORSHIPS)))
            return
        cost, awards = E.type4worship(wtype)
        if user['rock'] < cost.get('rock', 0):
            self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
            return  
        if user['gold'] < cost.get('gold', 0):
            self.write(dict(err=E.ERR_NOTENOUGH_GOLD, msg=E.errmsg(E.ERR_NOTENOUGH_GOLD)))
            return
        user['rock'] -= cost.get('rock', 0)
        yield self.set_consume(user, cost.get('rock', 0))
        user['gold'] -= cost.get('gold', 0)
        cuser = dict(gold=user['gold'], rock=user['rock'])
        cwork = E.tagworks(user, {'WORSHIP': 1})
        if cwork:
            cuser['works'] = user['works']
        if wtype == 1:
            wtypemsg = u'免费'
        elif wtype == 2:
            wtypemsg = u'金币'
        elif wtype == 3:
            wtypemsg = u'钻石'
        else:
            wtypemsg = u'未知'
        logmsg = u'膜拜:%s膜拜%s' % (wtypemsg, cid)
        yield self.set_user(uid, logmsg, **cuser)
        hp, tick = yield self.add_hp(user, awards.get('hp', 0), u'%s膜拜%s奖励' % (wtypemsg, cid))
        hp, tick = yield self.get_hp(user)
        cuser['hp'] = hp
        cuser['tick'] = tick
        yield self.redis.incr('worshiptimes:%s' % uid)
        worshipedtimes = yield self.redis.incr('worshipedtimes:%s' % cid)
        gold = E.award4worship(wtype, worshipedtimes)
        worshipedgolds = yield self.redis.get('worshipedgolds:%s' % cid)
        if not worshipedgolds:
            worshipedgolds = 0
        gold += worshipedgolds
        yield self.redis.set('worshipedgolds:%s' % cid, gold)
        consume = yield self.get_consume(user)
        cuser['consume'] = consume
        ret = dict(out=dict(awards=awards), user=cuser, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class RecordHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Worship record', '/worship/record/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Worship record")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        worshiped = yield self.redis.lrange('worshiped:%s' % uid, start=0, end=-1)
        #worshiped = ["9:1:\xe5\x88\x98\xe5\x81\xa5:0:1000:1437991857"]
        worshipers = []
        if worshiped:
            for w in worshiped:
                cid, avat, nickname, xp, gold, timestamp = w.split(':')
                worshipers.append(dict(uid=cid, avat=avat, nickname=nickname, xp=xp, timestamp=timestamp, gold=gold))
        ret = dict(out=dict(worshipers=worshipers), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

