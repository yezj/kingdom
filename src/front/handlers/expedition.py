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
from twisted.python import log
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
    @api('Expedition info', '/expedition/info/', [
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], description=u"获得远征信息,包含关卡信息,敌人信息,重置信息")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        expedition = yield self.get_expedition(user)
        exped = yield self.predis.lrange("exped:%s:%s" % (ZONE_ID, uid), start=0, end=-1)
        exped_coin = yield self.get_expedcoin(user)
        #print expedition, exped
        ret = dict(out=dict(user=dict(exped_coin=exped_coin), expedition=expedition, exped=exped), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class GetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Expedition get', '/expedition/get/', [
        Param('eid', True, str, '050108', '050108', 'eid'),
        Param('hids', True, str, '01002,01001', '01002,01001', 'hids'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
    ], description=u"获取当前关卡掉落信息")
    def post(self):
        try:
            eid = self.get_argument("eid")
            hids = self.get_argument("hids").split(',')    # "12,32,56,1,10"
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        entrycount = (yield self.redis.hget("entrycount:%s" % uid, eid)) or 0
        if not entrycount:
            entrycount = 0
        entrytimes = (yield self.redis.hget("entrytimes:%s" % uid, eid)) or 0
        if not entrytimes:
            entrytimes = 0
        try:
            res = yield self.sql.runQuery("SELECT prod, maxnum, minnum, gold, rock, feat,\
              exped_coin FROM core_expedition WHERE eid=%s LIMIT 1", (eid, ))
            #print eid, res
            if res:
                prod, maxnum, minnum, gold, rock, feat, exped_coin = res[0]
                rand = random.randint(minnum, maxnum)
                prods = [str(p) for p in prod.rstrip('\r\n').split(',')]
                entrytimes = entrytimes % len(prods)
                prods = E.random_exped_prods(entrytimes, entrytimes + 1*4, prods, 4)
                #print 'prods', prods
            else:
                prods = {}
                gold = rock = feat = exped_coin = 0
        except Exception:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return
        match = {
            'label': eid,
            'hids': hids,
            'gold': gold,
            'rock': rock,
            'feat': feat,
            'exped_coin': exped_coin,
            'prods': prods,
        }
        fid = uuid.uuid4().hex
        yield self.set_expedflush(fid, match)
        ret = dict(out=dict(flush=fid, match=match), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class SetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Expedition set', '/expedition/set/', [
        Param('fid', True, str, '0cb9abd2f380497198c769344279a7cd', '0cb9abd2f380497198c769344279a7cd', 'fid'),
        #Param('gain', True, str, '', '{"blood": {"01002": 40, "01003": -1}, "result":0, "comp":{"01002": 40}', 'gain'),
        Param('our', True, str, '', '{"01002": {"blood": 0, "gas": 0}, "01003": {"blood": -1, "gas": 0}}', 'our'),
        Param('comps', True, str, '', '{"01002": {"blood": 0, "gas": 0}, "01003": {"blood": -1, "gas": 0}}', 'comps'),
        Param('result', True, int, 1, 1, 'result'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
    ], description=u"设置远征战役结果,包括双方血量")
    def post(self):
        try:
            fid = self.get_argument("fid")
            our = escape.json_decode(self.get_argument("our"))
            comps = escape.json_decode(self.get_argument("comps"))
            result = self.get_argument("result")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        #exped_coin = yield self.get_expedcoin(user)
        prop = yield self.get_expedflush(fid)
        label = prop['label']
        expedition = yield self.set_expedition(user, label, our, comps)
        if int(result):
            user['gold'] += prop['gold']
            user['rock'] += prop['rock']
            user['feat'] += prop['feat']
            for prod, n in prop['prods'].items():
                if prod in user['prods']:
                    user['prods'][prod] += n
                else:
                    user['prods'][prod] = n
                if user['prods'][prod] > 9999:
                    user['prods'][prod] = 9999
                elif user['prods'][prod] == 0:
                    del user['prods'][prod]
                else:pass
            #print prop['exped_coin']
            exped_coin = yield self.update_expedcoin(user, prop['exped_coin'])
            log.msg('user %s , exped %s,  get exped_coin %s, now exped_coin %s' % (uid, label, prop['exped_coin'], exped_coin))
            cuser = dict(gold=user['gold'],
                         rock=user['rock'],
                         feat=user['feat'],
                         heros=user['heros'],
                         prods=user['prods']
                         )
        else:
            cuser = {}

        yield self.redis.hincrby("entrycount:%s" % uid, label, 1)
        yield self.redis.hincrby("entrytimes:%s" % uid, label, 2)
        yield self.redis.hset("entrytimer:%s" % uid, label, int(time.time()))
        cwork = E.tagworks(user, {'EXPEDITION': 1})
        if cwork:
            cuser['works'] = user['works']
        ctask = E.pushtasks(user)
        if ctask:
            cuser['tasks'] = user['tasks']
        cmail = E.checkmails(user)
        if cmail:
            cuser['mails'] = user['mails']
        logmsg = u'远征:%s攻打%s关卡' % (int(result) and u'成功' or u'失败', label)
        yield self.set_user(uid, logmsg, **cuser)
        if int(result) == 1:
            yield self.predis.lpush("exped:%s:%s" % (ZONE_ID, uid), label)
        exped_coin = yield self.get_expedcoin(user)
        cuser['exped_coin'] = exped_coin
        exped = yield self.predis.lrange("exped:%s:%s" % (ZONE_ID, uid), start=0, end=-1)
        ret = dict(out=dict(user=cuser), expedition=expedition, exped=exped, timestamp=int(time.time()))
        #print 'ret', ret
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class ResetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Expedition reset', '/expedition/reset/', [
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
    ], description=u"重置远征,重置次数减1")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        expedresets = yield self.redis.get('expedresets:%s' % uid)
        if expedresets:
            if expedresets >= E.expedmaxtimes(user['vrock']):
                self.write(dict(err=E.ERR_DISSATISFY_MAXRESETS, msg=E.errmsg(E.ERR_DISSATISFY_MAXRESETS)))
                return
        else:
            expedresets = 0
            yield self.redis.set('expedresets:%s' % uid, expedresets)
        expeditions = yield self.predis.hexists("expeditions:%s" % ZONE_ID, uid)
        if expeditions:
            yield self.predis.hdel("expeditions:%s" % ZONE_ID, str(uid))
            yield self.predis.hdel("expedzuids:%s" % ZONE_ID, str(uid))
        yield self.predis.delete("exped:%s:%s" % (ZONE_ID, uid))
        yield self.redis.incr('expedresets:%s' % uid)
        expedition = yield self.get_expedition(user)
        exped_coin = yield self.get_expedcoin(user)
        expedition['exped_coin'] = exped_coin
        ret = dict(expedition=expedition, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class ShopHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Expedition shop', '/expedition/shop/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
    ], filters=[ps_filter], description="Expedition shop")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        expedprod_list = yield self.redis.lrange('expedprod:%s' % uid, 0, -1)
        expedrefresh = yield self.redis.get('expedrefreshes:%s' % uid)
        if not expedrefresh:
            expedrefresh = 0
        prods = copy.deepcopy(D.EXPEDPROD)

        for pid in prods.keys():
            if int(pid) in expedprod_list:
                prods[pid]['is_buy'] = 1
            else:
                prods[pid]['is_buy'] = 0
        ret = dict(prods=prods, timestamp=int(time.time()), refresh_times=expedrefresh)
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class BuyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Expedition buy', '/expedition/buy/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        Param('pid', True, str, '01030', '01030', 'pid'),
    ], filters=[ps_filter], description="Expedition buy")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        if self.has_arg('pid') and self.arg('pid') in D.EXPEDPROD:
            pid = self.arg('pid')
            num = D.EXPEDPROD[pid]['num']
            expedprod_list = yield self.redis.lrange('expedprod:%s' % uid, 0, -1)
            if int(pid) in expedprod_list:
                self.write(dict(err=E.ERR_DUPLICATE_BUY, msg=E.errmsg(E.ERR_DUPLICATE_BUY)))
                return
            cost = E.cost4exped(pid)
            if cost:
                exped_coin = yield self.get_expedcoin(user)
                expedrefresh = yield self.redis.get('expedrefreshes:%s' % uid)
                if not expedrefresh:
                    expedrefresh = 0
                if exped_coin < cost:
                    self.write(dict(err=E.ERR_NOTENOUGH_EXPEDCOIN, msg=E.errmsg(E.ERR_NOTENOUGH_EXPEDCOIN)))
                    return
                else:
                    exped_coin = yield self.update_expedcoin(user, -cost)

                    if pid in user['prods']:
                        user['prods'][pid] += int(num)
                    else:
                        user['prods'][pid] = int(num)
                    if user['prods'][pid] > 9999:
                        user['prods'][pid] = 9999
                    cuser = dict(prods=user['prods'])
                    yield self.redis.lpush('expedprod:%s' % uid, pid)
                    logmsg = u'远征:远征物品购买%s' % pid
                    yield self.set_user(uid, logmsg, **cuser)
                    cuser = dict(cuser=cuser, exped_coin=exped_coin)
                    ret = dict(user=cuser, timestamp=int(time.time()))
                    reb = zlib.compress(escape.json_encode(ret))
                    self.write(ret)
        else:
            raise web.HTTPError(400, "Argument error")

@handler
class RefreshHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Expedition refresh', '/expedition/refresh/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
    ], filters=[ps_filter], description="Expedition refresh")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        exped_coin = yield self.get_expedcoin(user)
        expedrefresh = yield self.redis.get('expedrefreshes:%s' % uid)
        if not expedrefresh:
            expedrefresh = 0
            yield self.redis.set('expedrefreshes:%s' % uid, expedrefresh)
        if expedrefresh < E.limit_by_refresh:
            if exped_coin < D.EXPEDREFRESH[expedrefresh*2+1]:
                self.write(dict(err=E.ERR_NOTENOUGH_EXPEDCOIN, msg=E.errmsg(E.ERR_NOTENOUGH_EXPEDCOIN)))
                return
            exped_coin = yield self.update_expedcoin(user, -D.EXPEDREFRESH[expedrefresh*2+1])
            yield self.redis.incr('expedrefreshes:%s' % uid)
            yield self.redis.delete('expedprod:%s' % uid)
            cuser = dict(exped_coin=exped_coin)
            ret = dict(user=cuser, prods = D.EXPEDPROD, timestamp=int(time.time()))
            reb = zlib.compress(escape.json_encode(ret))
            self.write(ret)
        else:
            self.write(dict(err=E.ERR_DISSATISFY_MAXREFRESHES, msg=E.errmsg(E.ERR_DISSATISFY_MAXREFRESHES)))
            return

