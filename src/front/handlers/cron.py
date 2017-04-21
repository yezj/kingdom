# -*- coding: utf-8 -*-

import time
import zlib
import random
import pickle
import datetime
from twisted.internet import defer
from cyclone import escape, web
from front import storage
from front import utils
from front.utils import E
from front import D
from twisted.python import log
# from front.handlers.base import BaseHandler
from front.wiapi import *
from front.handlers.base import ApiHandler, ApiJSONEncoder
from local_settings import ZONE_ID

@handler
class ArenaHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Arena', '/cron/arena/', [
    ], filters=[ps_filter], description="arena cron job")
    def post(self):
        res = yield self.sql.runQuery("SELECT b.user_id, b.now_rank FROM core_user AS a, core_arena AS b WHERE a.id=b.user_id AND b.now_rank<%s AND a.xp/100000>=%s" % D.ARENA_MAIL_LIMIT)
        for r in res:
            awards = {}
            for i in xrange(0, len(D.ARENADAY)/6):
                if r[1] >= D.ARENADAY[i*6] and r[1] <= D.ARENADAY[i*6+1]:
                    awards = dict(rock=D.ARENADAY[i*6+2], gold=D.ARENADAY[i*6+3], arena_coin=D.ARENADAY[i*6+4], feat=D.ARENADAY[i*6+5])
                    break
            if awards:
                mail = D.TOPMAIL
                content = mail['content'] % r[1]
                yield self.send_mails(mail['sender'], r[0], mail['title'], content, awards)

@handler
class BlackmarketHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Blackmarket', '/cron/bm/', [
    ], filters=[ps_filter], description="Blackmarket cron job")
    def post(self):
        res = yield self.sql.runQuery("SELECT id FROM core_user")
        #yield self.predis.delete('bmseed')
        #yield self.predis.delete("hardbatttimes:%s" % ZONE_ID)
        for r in res:
            yield self.redis.delete('bmprod:%s' % r[0])
            #yield self.redis.incr('bmrefreshes:%s' % r[0])

@handler
class MarketHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Market', '/cron/market/', [
    ], filters=[ps_filter], description="Market cron job")
    def post(self):
        res = yield self.sql.runQuery("SELECT id FROM core_user")
        yield self.predis.delete('marketseed')
        yield self.predis.delete("batttimes:%s" % ZONE_ID)
        for r in res:
            yield self.redis.delete('marketprod:%s' % r[0])
            #yield self.redis.incr('marketrefreshes:%s' % r[0])

@handler
class StoreHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Store', '/cron/store/', [
    ], filters=[ps_filter], description="Store cron job")
    def post(self):
        res = yield self.sql.runQuery("SELECT id FROM core_user")
        for r in res:
            yield self.redis.delete('storeprod:%s' % r[0])
            #yield self.redis.incr('storerefreshes:%s' % r[0])

@handler
class WorshipHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Worship', '/cron/worship/', [
    ], filters=[ps_filter], description="Worship cron job")
    def post(self):
        worshipedgolds = yield self.redis.keys('worshipedgolds:*')
        for w in worshipedgolds:
            s, uid = w.split(':')
            gold = yield self.redis.get('%s' % w)
            awards = dict(gold=gold)
            worshipedtimes = yield self.redis.get('worshipedtimes:%s' % uid)
            mail = D.WORSHIPMAIL
            content = mail['content'] % (worshipedtimes, gold)
            yield self.send_mails(mail['sender'], uid, mail['title'], content, awards)

@handler
class SyncWorshipHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Worship', '/cron/syncworship/', [
    ], filters=[ps_filter], description="Worship cron job")
    def post(self):
        worshipers = []
        res = yield self.sql.runQuery("SELECT a.id, a.nickname, a.avat, a.xp, b.now_rank FROM core_user AS a,\
         core_arena AS b WHERE a.id=b.user_id AND b.now_rank<%s" % D.WORSHIPRANK)
        if res:
            for r in res:
                worshipers.append(dict(uid=r[0], nickname=r[1], avat=r[2], xp=r[3], now_rank=r[4]))

        yield self.predis.set('worshipers:%s' % ZONE_ID, pickle.dumps(worshipers))

@handler
class HaoLiHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Haoli', '/cron/haoli/', [
    ], filters=[ps_filter], description="haoli cron job")
    def post(self):
        res = yield self.sql.runQuery("SELECT id FROM core_user WHERE xp/100000>=29")
        for r in res:
            mail = D.HAOLIMAIL
            yield self.send_mails(mail['sender'], r[0], mail['title'], mail['content'], mail['jawards'])

@handler
class SealHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Seal', '/cron/seal/', [
    ], filters=[ps_filter], description="seal cron job")
    def post(self):
        res = yield self.sql.runQuery("SELECT jheros, id FROM core_user")
        
        for r in res:
            heros = r[0] and escape.json_decode(r[0]) or {}
            if '01026' not in heros:
                userseals = [2, 1]
            else:
                userseals = [1, 1]
            query = "UPDATE core_user SET jseals=%s WHERE id=%s RETURNING id"
            params = (escape.json_encode(userseals), r[1])
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue

            cuser = dict(seals=userseals)
            yield self.set_user(r[1], **cuser)

@handler
class PackHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Seal', '/cron/pack/', [
    ], filters=[ps_filter], description="pack cron job")
    def post(self):
        with open('/home/ubuntu/srv/PtKingdom/src/script/package.txt', 'r') as f:
            for r in f.readlines():
                zone, uid = r.rstrip('\r\n').split(":")
                if int(zone) == ZONE_ID:
                    user = yield self.get_user(uid)
                    if user:
                        res = yield self.sql.runQuery("SELECT id, prods, nums, gold, rock, feat, hp FROM core_vippackage WHERE level<=%s", (E.vip(user['vrock']), ))
                        for r in res:
                            vid, prods, nums, gold, rock, feat, hp = r
                            res = yield self.sql.runQuery("SELECT user_id, package_id FROM core_userpackage WHERE user_id=%s AND package_id=%s LIMIT 1", (int(uid), int(vid)))
                            if not res:
                                query = "INSERT INTO core_userpackage(user_id, package_id) VALUES (%s, %s) RETURNING id"
                                params = (int(uid), int(vid))
                                for i in range(5):
                                    try:
                                        res = yield self.sql.runQuery(query, params)
                                        break
                                    except storage.IntegrityError:
                                        log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                                        continue
