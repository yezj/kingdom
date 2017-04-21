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
from local_settings import *
@handler
class InfoHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Rock info', '/rock/info/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Rock info")
    def get(self):
        uid = self.uid
        user = yield self.get_user(uid)
        buyrecords = yield self.predis.get('buyrecords:%s:%s' % (ZONE_ID, uid))
        if buyrecords:
            buyrecords = pickle.loads(buyrecords)
        else:
            buyrecords = {}
            for i in xrange(0, len(D.ROCKSTORE)/8):
                res = yield self.sql.runQuery("select created_at from core_buyrecord where user_id=%s and gid=%s limit 1", (uid, D.ROCKSTORE[i*8]))
                lefttime = '-1'
                if res:
                    if D.ROCKSTORE[i*8+2] == 0:
                        if D.ROCKSTORE[i*8+3] == 1:
                            res = yield self.sql.runQuery("SELECT created_at, ended_at FROM core_card WHERE user_id=%s AND gid=%s LIMIT 1", (user['uid'], D.ROCKSTORE[i*8]))
                            if res:
                                created_at, ended_at = res[0]
                                t = datetime.datetime.today().date()
                                lefttime = (ended_at - created_at)/3600/24
                                if lefttime < 0:
                                    lefttime = '-1'
                                buyrecords[D.ROCKSTORE[i*8]] = lefttime

                        elif D.ROCKSTORE[i*8+3] == 2:
                            buyrecords[D.ROCKSTORE[i*8]] = lefttime
                        else:

                            gid, = [D.ROCKSTORE[j*8] for j in xrange(0, len(D.ROCKSTORE)/8) if D.ROCKSTORE[j*8+1] == D.ROCKSTORE[i*8+1] and D.ROCKSTORE[j*8+3] == 2]
                            buyrecords[gid] = lefttime
                else:
                    if D.ROCKSTORE[i*8+2] == 0:
                        buyrecords[D.ROCKSTORE[i*8]] = lefttime
            yield self.predis.set('buyrecords:%s:%s' % (ZONE_ID, uid), pickle.dumps(buyrecords))

        ret = dict(vrock=user['vrock'], goods=buyrecords, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Rock info', '/rock/info/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Rock info")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        buyrecords = yield self.predis.get('buyrecords:%s:%s' % (ZONE_ID, uid))
        if buyrecords:
            buyrecords = pickle.loads(buyrecords)
        else:
            buyrecords = {}
            for i in xrange(0, len(D.ROCKSTORE)/8):
                res = yield self.sql.runQuery("select created_at from core_buyrecord where user_id=%s and gid=%s limit 1", (uid, D.ROCKSTORE[i*8]))
                lefttime = '-1'
                if res:
                    if D.ROCKSTORE[i*8+2] == 0:
                        if D.ROCKSTORE[i*8+3] == 1:
                            res = yield self.sql.runQuery("SELECT created_at, ended_at FROM core_card WHERE user_id=%s AND gid=%s LIMIT 1", (user['uid'], D.ROCKSTORE[i*8]))
                            if res:
                                created_at, ended_at = res[0]
                                t = datetime.datetime.today().date()
                                lefttime = (ended_at - created_at)/3600/24
                                if lefttime < 0:
                                    lefttime = '-1'
                                buyrecords[D.ROCKSTORE[i*8]] = lefttime

                        elif D.ROCKSTORE[i*8+3] == 2:
                            buyrecords[D.ROCKSTORE[i*8]] = lefttime
                        else:

                            gid, = [D.ROCKSTORE[j*8] for j in xrange(0, len(D.ROCKSTORE)/8) if D.ROCKSTORE[j*8+1] == D.ROCKSTORE[i*8+1] and D.ROCKSTORE[j*8+3] == 2]
                            buyrecords[gid] = lefttime
                else:
                    if D.ROCKSTORE[i*8+2] == 0:
                        buyrecords[D.ROCKSTORE[i*8]] = lefttime
            yield self.predis.set('buyrecords:%s:%s' % (ZONE_ID, uid), pickle.dumps(buyrecords))

        ret = dict(vrock=user['vrock'], goods=buyrecords, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class BuyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Rock buy', '/rock/buy/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('id', True, str, '08001', '08001', 'goods id'),
        ], filters=[ps_filter], description="Rock buy")
    def get(self):
        uid = self.uid
        user = yield self.get_user(uid)
        buyrecords = yield self.predis.get('buyrecords:%s:%s' % (ZONE_ID, uid))
        if buyrecords:
            buyrecords = pickle.loads(buyrecords)
            if self.has_arg('id'):
                if self.arg('id') in buyrecords:
                    is_first = 0
                    pos, = [i for i in xrange(0, len(D.ROCKSTORE)/8) if D.ROCKSTORE[i*8] == self.arg('id')]
                    if D.ROCKSTORE[pos*8+2] == 0:
                        if D.ROCKSTORE[pos*8+3] == 1:
                            #card
                            lefttime, is_first = yield self.set_card(user, D.ROCKSTORE[pos*8])
                            if lefttime:
                                buyrecords[D.ROCKSTORE[pos*8]] = lefttime
                            if is_first:
                                user['works']['01007'] = {"_": 1, "tags": {"CARD": [1, 1]}}

                        elif D.ROCKSTORE[pos*8+3] == 3:
                            gid, = [D.ROCKSTORE[i*8] for i in xrange(0, len(D.ROCKSTORE)/8) if D.ROCKSTORE[i*8+1] == D.ROCKSTORE[pos*8+1] and D.ROCKSTORE[i*8+3] == 2]
                            del buyrecords[self.arg('id')]
                            buyrecords[gid] = '-1'

                        else:
                            pass
                    else:
                        pass
                    user['vrock'] += D.ROCKSTORE[pos*8+4]
                    user['rock'] += D.ROCKSTORE[pos*8+4]
                    user['rock'] += D.ROCKSTORE[pos*8+5]
                    if is_first:
                        cuser = dict(rock=user['rock'], vrock=user['vrock'], works=user['works'])
                    else:
                        cuser = dict(rock=user['rock'], vrock=user['vrock'])
                    logmsg = u'钻石:购买%s' % self.arg('id')
                    yield self.set_user(uid, logmsg, **cuser)
                    yield self.set_buyrecord(user, self.arg('id'))
                    yield self.predis.set('buyrecords:%s:%s' % (ZONE_ID, uid), pickle.dumps(buyrecords))
                    ret = dict(user=cuser, goods=buyrecords, timestamp=int(time.time()))
                    reb = zlib.compress(escape.json_encode(ret))
                    self.write(ret)
                else:
                    raise web.HTTPError(400, "Argument error")
                    
            else:
                raise web.HTTPError(400, "Argument error")
        else:
            raise web.HTTPError(400, "Argument error")

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Rock buy', '/rock/buy/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('id', True, str, '08001', '08001', 'goods id'),
        ], filters=[ps_filter], description="Rock buy")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        buyrecords = yield self.predis.get('buyrecords:%s:%s' % (ZONE_ID, uid))
        if buyrecords:
            buyrecords = pickle.loads(buyrecords)
            if self.has_arg('id'):
                if self.arg('id') in buyrecords:
                    is_first = 0
                    pos, = [i for i in xrange(0, len(D.ROCKSTORE)/8) if D.ROCKSTORE[i*8] == self.arg('id')]
                    if D.ROCKSTORE[pos*8+2] == 0:
                        if D.ROCKSTORE[pos*8+3] == 1:
                            #card
                            lefttime, is_first = yield self.set_card(user, D.ROCKSTORE[pos*8])
                            if lefttime:
                                buyrecords[D.ROCKSTORE[pos*8]] = lefttime
                            if is_first:
                                user['works']['01007'] = {"_": 1, "tags": {"CARD": [1, 1]}}

                        elif D.ROCKSTORE[pos*8+3] == 3:
                            gid, = [D.ROCKSTORE[i*8] for i in xrange(0, len(D.ROCKSTORE)/8) if D.ROCKSTORE[i*8+1] == D.ROCKSTORE[pos*8+1] and D.ROCKSTORE[i*8+3] == 2]
                            del buyrecords[self.arg('id')]
                            buyrecords[gid] = '-1'

                        else:
                            pass
                    else:
                        pass
                    user['vrock'] += D.ROCKSTORE[pos*8+4]
                    user['rock'] += D.ROCKSTORE[pos*8+4]
                    user['rock'] += D.ROCKSTORE[pos*8+5]
                    if is_first:
                        cuser = dict(rock=user['rock'], vrock=user['vrock'], works=user['works'])
                    else:
                        cuser = dict(rock=user['rock'], vrock=user['vrock'])
                    logmsg = u'钻石:购买%s' % self.arg('id')
                    yield self.set_user(uid, logmsg, **cuser)
                    yield self.set_buyrecord(user, self.arg('id'))
                    yield self.predis.set('buyrecords:%s' % (ZONE_ID, uid), pickle.dumps(buyrecords))
                    ret = dict(user=cuser, goods=buyrecords, timestamp=int(time.time()))
                    reb = zlib.compress(escape.json_encode(ret))
                    self.write(ret)
                else:
                    raise web.HTTPError(400, "Argument error")
                    
            else:
                raise web.HTTPError(400, "Argument error")
        else:
            raise web.HTTPError(400, "Argument error")

