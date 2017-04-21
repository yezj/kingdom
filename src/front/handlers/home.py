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

class HomeHandler(ApiHandler):

    def get(self):
        self.render('index.html')


class CrossdomainHandler(ApiHandler):

    def get(self):
        self.render('crossdomain.xml')

    def post(self):
        self.render('crossdomain.xml')

@handler
class StartupHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Startup', '/startup/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('model', True, str, 'bigfish@hi3798mv100', 'bigfish@hi3798mv100', 'model'),
        Param('serial', True, str, '0066cf0456732122121', '0066cf0456732122121', 'serial'),
        Param('idcard', False, str, None, None, 'idcard'),
        Param('access_token', False, str, '55526fcb39ad4e0323d32837021655300f957edc', '55526fcb39ad4e0323d32837021655300f957edc', 'access_token'),
        ], filters=[ps_filter], description="Startup")
    def post(self):
        try:
            model = self.get_argument("model")[:49]
            serial = self.get_argument("serial")[:99]
            idcard = self.get_argument("idcard", None)
            channel = self.get_argument("channel", "putaogame")
            access_token = self.get_argument("access_token", None)
        except Exception:
            raise web.HTTPError(400, "Argument error")
            
        channels = yield self.sql.runQuery("SELECT id FROM core_channel WHERE slug=%s LIMIT 1", (channel, ))
        if not channels:
            channels = yield self.sql.runQuery("SELECT id FROM core_channel WHERE slug=%s LIMIT 1", ("putaogame", ))
        channel, = channels[0]
        try:
            # server = {domain:..., notice: ...}
            server = self.ping_server()
        except E.SERVERERROR, e:
            self.write(dict(err=E.ERR_SERVER, msg=e.message))
            return
        except Exception:
            self.write(dict(err=E.ERR_UNKNOWN, msg=E.errmsg(E.ERR_UNKNOWN)))
            return

        idcard = yield self.refresh_idcard(idcard, model, serial, channel, access_token)
        if self.has_arg('access_token'):
            record = yield self.predis.get('zone:%s:%s' % (ZONE_ID, self.arg('access_token')))
            if not record:
                yield self.predis.set('zone:%s:%s' % (ZONE_ID, self.arg('access_token')), idcard)
                yield self.bind_token(idcard, self.arg('access_token'))

        ret = dict(idcard=idcard, zone=ZONE_ID, server=server)
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class ActiveHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Active', '/active/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('idcard', True, str, '864c04bf73a445fd84da86a206060c48h20', '864c04bf73a445fd84da86a206060c48h20', 'idcard'),
        Param('zone', True, str, '0', '0', 'zone'),
        ], filters=[ps_filter], description="Active")
    def post(self):
        try:
            channel = self.get_argument("channel", "putaogame")
            idcard = self.get_argument("idcard")
            zone = self.get_argument("zone")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        if idcard:
            ahex, aid = idcard.split('h', 1)
            res = yield self.sql.runQuery("SELECT accountid, user_id FROM core_account WHERE accountid=%s OR id=%s LIMIT 1", (aid, aid))
            if res:
                query = "UPDATE core_account SET accountid=%s, timestamp=%s WHERE id=%s RETURNING id"
                params = (aid, int(time.time()), aid)
                for i in range(5):
                    try:
                        yield self.sql.runOperation(query, params)
                        break
                    except storage.IntegrityError:
                        log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                        continue
            yield self.predis.hset('zone:%s:%s' % (zone, datetime.datetime.now().strftime('%Y%m%d')), aid, E.true)

        try:
            sign = yield self.generate_sign(idcard=idcard, zone=zone)
        except E.USERNOTFOUND:
            self.write(dict(err=E.ERR_USER_NOTFOUND, msg=E.errmsg(E.ERR_USER_NOTFOUND)))
            return
        except E.USERABNORMAL:
            self.write(dict(err=E.ERR_USER_ABNORMAL, msg=E.errmsg(E.ERR_USER_ABNORMAL)))
            return
        except E.USERBEBANKED:
            self.write(dict(err=E.ERR_USER_BEBANKED, msg=E.errmsg(E.ERR_USER_BEBANKED)))
            return
        except Exception:
            self.write(dict(err=E.ERR_UNKNOWN, msg=E.errmsg(E.ERR_UNKNOWN)))
            return
        #print 'sign', sign
        ret = dict(sign=sign, accountid=aid)
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class SyncHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Sync', '/sync/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Sync")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        notice = yield self.get_notice()
        userseals = yield self.get_seal(uid)
        if userseals:
            sealnu, sealday =userseals
        else:
            sealnu, sealday = 0, 0

        userseals=[sealnu, sealday]
        today = datetime.date.today().day 
        status = 0 
        if sealnu != 0 and sealday-1 == today:
            status = 1
        if sealnu >= 14:
            status = 1
 
        #yield self.set_mails(user)
        if not user:
            self.write(dict(err=E.ERR_USER_NOTFOUND, msg=E.errmsg(E.ERR_USER_NOTFOUND)))
            return
        # check mails
        cuser = {}
        mailcomming = E.checkmails(user)
        if mailcomming:
            cuser['mails'] = user['mails']
            yield self.set_user(uid, **cuser)
        yield self.set_mails(user)
        # get hp and tick
        hp, tick = yield self.get_hp(user)
        user['hp'] = hp
        user['tick'] = tick
        user['card'] = yield self.get_card(user)
        sp, tick = yield self.get_sp(user)
        user['sp'] = sp
        user['works'] = E.checkworks(user)
        # entry related
        entryopens = E.entryopens(user)
        entrycounts = yield self.redis.hgetall("entrycount:%s" % uid)
        entrytimers = yield self.redis.hgetall("entrytimer:%s" % uid)
        lott = yield self.update_lott(user)
        lottmark, mailmark, arenamark = yield self.check_redpot(user)
        yield self.set_arena(uid)
        bminterval = yield self.redis.get('blackmarket:%s' % uid)
        if not bminterval:
            bminterval = 0
        else:
            bminterval = bminterval - int(time.time())
        minterval = yield self.redis.get('market:%s' % uid)
        if not minterval:
            minterval = 0
        else:
            minterval = minterval - int(time.time())
        res = yield self.sql.runQuery("SELECT beautyid FROM core_beauty")
        beautys = yield self.get_beautys(user)
        user['beautys'] = beautys
        res = yield self.sql.runQuery("SELECT created_at, ended_at FROM core_bigevent WHERE bid='20160001'")
        if res:
            created_at, ended_at = res[0]
            created_at = int(time.mktime(created_at.timetuple()))
            ended_at = int(time.mktime(ended_at.timetuple()))
            now = int(time.mktime(datetime.datetime.now().timetuple()))
            if now >= created_at and now <= ended_at:  
                created_at, ended_at = res[0]  
                created_at = created_at.date()
                now = datetime.datetime.now().date()
                day = (now - created_at).days
                hebdo = yield self.predis.get('hebdo:%s:%s:%s' % (ZONE_ID, uid, day))
                if not hebdo:
                    yield self.send_hebdomail(user, day)
        user['dayrecharge'] = 0
        user['consume'] = yield self.get_consume(user)
        user['inpour'] = yield self.get_inpour(user)
        #print 'consume', user['consume'], user['inpour']
        ret = dict(out=dict(user=user, entryopens=entryopens, entrycounts=entrycounts, entrytimers=entrytimers, lottfree=lottmark,\
         bminterval=bminterval, minterval=minterval, arena=arenamark, notice=notice, fourteenseal=[sealnu,status]), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class DotHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Reddot', '/reddot/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="reddot")
    def post(self):
        #red dot arena 
        uid = self.uid
        user = yield self.get_user(uid)
        lottmark, mailmark, arenamark = yield self.check_redpot(user)
        message = yield self.redis.lrange('message', start=-50, end=-1)
        if message:
            message = [pickle.loads(m.decode("utf-8")) for m in message]
        else:
            message = []
        ret = dict(arena=arenamark, lott=lottmark, mail=mailmark, message=message, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class HpHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Synchp', '/synchp/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="synchp")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        currhp, tick = yield self.get_hp(user)
        ret = dict(hp=currhp, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class SyncdbHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Syncdb', '/syncdb/', [
    ], filters=[ps_filter], description="Syncdb")
    def post(self):
        self.write("START...\r\n")
        self.redis.flushdb()
        res = yield self.sql.runQuery("SELECT id, name, nickname, avat, xp, gold, rock, feat, book, jheros, jprods,\
         jbatts, jseals, jdoors, jextra, jtasks, jworks, jmails, vrock, jbeautys, jactivities, jrecharge, jinsts FROM core_user")
        nickname = []
        for r in res:
            try:
                user = dict(uid=r[0], name=r[1], nickname=r[2], avat=r[3], xp=r[4], gold=r[5], rock=r[6], feat=r[7],\
                 book=r[8], vrock=r[18])
                user['heros'] = r[9] and escape.json_decode(r[9]) or {}
                user['prods'] = r[10] and escape.json_decode(r[10]) or {}
                user['batts'] = r[11] and escape.json_decode(r[11]) or {}
                user['seals'] = r[12] and escape.json_decode(r[12]) or {}
                user['doors'] = r[13] and escape.json_decode(r[13]) or {}
                user['extra'] = r[14] and escape.json_decode(r[14]) or {}
                user['tasks'] = r[15] and escape.json_decode(r[15]) or {}
                user['beautys'] = r[19] and escape.json_decode(r[19]) or {}
                user['works'] = {
                                "01021": {"_": 0, "tags": {"EQUIP": [1, 0]}},\
                                "01020": {"_": 0, "tags": {"STORE": [1, 0]}},\
                                "01019": {"_": 0, "tags": {"FEAT": [1, 0]}},\
                                "01018": {"_": 0, "tags": {"HUNT": [1, 0]}},\
                                "01017": {"_": 0, "tags": {"MINE": [1, 0]}},\
                                "01016": {"_": 0, "tags": {"WORSHIP": [1, 0]}},\
                                "01015": {"_": 0, "tags": {"BEAUTY": [1, 0]}},\
                                "01014": {"_": 0, "tags": {"CALL": [3, 0]}},\

                                "01013": {"_": 0, "tags": {"GOLD": [1, 0]}},\
                                "01012": {"_": 0, "tags": {"INST3": [2, 0]}},\
                                "01011": {"_": 0, "tags": {"DINNER": [1, 0]}},\
                                "01010": {"_": 0, "tags": {"LUNCH": [1, 0]}},\
                                "01009": {"_": 0, "tags": {"BREAKFAST": [1, 0]}},\
                                "01008": {"_": 0, "tags": {"ARENA": [3, 0]}},\
                                "01007": {"_": 0, "tags": {"CARD": [1, 0]}},\
                                "01006": {"_": 0, "tags": {"SKILLUP": [3, 0]}},\
                                "01004": {"_": 0, "tags": {"INST1": [2, 0]}},\
                                "01005": {"_": 0, "tags": {"INST2": [3, 0]}},\
                                "01002": {"_": 0, "tags": {"BATT": [10, 0]}},\
                                "01003": {"_": 0, "tags": {"HARDBATT": [3, 0]}},\
                                "01001": {"_": 0, "tags": {"TAX": [1, 0]}}}
                user['activities'] = r[20] and escape.json_decode(r[20]) or {}
                user['recharge'] = r[21] and escape.json_decode(r[21]) or {}
                user['insts'] = r[22] and escape.json_decode(r[22]) or {}
                card = yield self.get_card(user)
                if int(card) > 0:
                    user['works']['01007'] = {"_": 1, "tags": {"CARD": [1, 1]}}
                user['mails'] = r[17] and escape.json_decode(r[17]) or {}

                yield self.set_user(**user)
                self.redis.lpush("nickname", r[2])
                #nickname.append(r[2])
            except Exception:
                web.HTTPError(500)
            try:
                yield self.set_arena(r[0])
                #yield self.update_payrecord(r[0])
                yield self.redis.set('arenatimes:%s' % r[0], 0)
                yield self.redis.set('arenatime:%s' % r[0], int(time.time()))
                yield self.redis.set('arenarefreshes:%s' % r[0], 0)
                yield self.redis.set('arenaresets:%s' % r[0], 0)
                yield self.predis.delete('bmseed')
                yield self.predis.delete("hardbatttimes:%s" % ZONE_ID)
                yield self.predis.delete("expeditions:%s" % ZONE_ID)
                yield self.predis.delete("expedzuids:%s" % ZONE_ID)
                yield self.predis.delete("exped:%s:%s" % (ZONE_ID, r[0]))
            except Exception:
                web.HTTPError(500)

        yield self.sql.runQuery("UPDATE core_freelott SET free=True, times=0 WHERE lotttype=%s RETURNING id" % E.lott_by_gold)
        res = yield self.sql.runQuery("SELECT user_id, lotttype, free FROM core_freelott")
        if res:
            for r in res:
                yield self.redis.set('lottfree:%s:%s' % (r[0], r[1]), r[2])

        self.write("SYNC SUCCESS")

@handler
class SyncactHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Syncact', '/syncact/', [
    ], filters=[ps_filter], description="Syncact")
    def post(self):
        seckill = 0
        res = yield self.sql.runQuery("SELECT created_at, ended_at, switch from core_seckilltime")
        if res:
            created_at, ended_at, switch = res[0]
            created_at = int(time.mktime(created_at.timetuple()))
            ended_at = int(time.mktime(ended_at.timetuple()))
            now = time.time()
            midnight = int(now - (now % 86400) + time.timezone)
            endnight = int(midnight + 24*3600)
            if (created_at >= midnight and created_at <= endnight) or switch:
                seckill = 1
        ret = dict(seckill=seckill, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class FlushdbHandler(ApiHandler):

    @storage.databaseSafe
    # @defer.inlineCallbacks
    @api('Flushdb', '/flushdb/', [
    ], filters=[ps_filter], description="Flushdb")
    def post(self):
        self.write("START...\r\n")
        self.redis.flushdb()
        self.write("FLUSHDB SUCCESS")

@handler
class DelcacheHandler(ApiHandler):

    @storage.databaseSafe
    # @defer.inlineCallbacks
    @api('Delcache', '/delcache/', [
    ], filters=[ps_filter], description="delcache")
    def post(self):
        arguments = self.request.arguments.copy()
        try:
            uid = arguments.get("id")[0]
            self.redis.delete("cache:user:%s" % uid)
        except Exception:
            pass

