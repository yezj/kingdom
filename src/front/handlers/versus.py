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

@handler
class IndexHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('versus', '/versus/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
    ], filters=[ps_filter], description="Get versus")
    def post(self):
        uid = self.uid
        #print uid
        user = yield self.get_user(uid)
        state = yield self.get_userstate(uid)
        states = {}
        for key, value in D.VERSUSSTATE.iteritems():
            query = "SELECT b.id, b.nickname, b.avat, xp FROM %s AS a" % value + ", core_user as b WHERE a.user_id=b.id AND now_rank=%s LIMIT 1"
            res = yield self.sql.runQuery(query, (1, ))
            if res:
                id, nickname, avat, xp = res[0]
                states[key] = dict(uid=id, nickname=nickname, avat=avat, xp=xp)
            else:
                states[key] = {}

        versuschance = yield self.redis.get('versuschance:%s' % uid) or 0
        #print 'versuschance', uid, versuschance
        if not versuschance:
            versuschance = 1
        else:
            versuschance = 0
        ret = dict(state=state, states=states, chance=versuschance, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class JoinHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Versus join', '/versus/join/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        Param('sid', True, str, '1', '1', 'sid'),
    ], filters=[ps_filter], description="Versus join")
    def post(self):
        try:
            sid = self.get_argument("sid")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        query = "SELECT * FROM %s WHERE user_id=%s LIMIT 1" % (D.VERSUSSTATE[sid], uid)
        res = yield self.sql.runQuery(query)
        if res:
            self.write(dict(err=E.ERR_VERSUSSTATE_ALREADY, msg=E.errmsg(E.ERR_VERSUSSTATE_ALREADY)))
            return
        yield self.join_state(user, sid)
        versuschance = yield self.redis.get('versuschance:%s' % uid) or 0
        #print 'versuschance', uid, versuschance
        if not versuschance:
            versuschance = 1
            yield self.redis.set('versuschance:%s' % uid, versuschance)
        else:
            self.write(dict(err=E.ERR_DISSATISFY_MAXENTRY, msg=E.errmsg(E.ERR_DISSATISFY_MAXENTRY)))
            return
        ret = dict(timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class LeaveHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Versus leave', '/versus/leave/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        Param('sid', True, str, '1', '1', 'sid'),
    ], filters=[ps_filter], description="Versus leave")
    def post(self):
        try:
            sid = self.get_argument("sid")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        query = "SELECT * FROM %s WHERE user_id=%s LIMIT 1" % (D.VERSUSSTATE[sid], uid)
        res = yield self.sql.runQuery(query)
        if not res:
            self.write(dict(err=E.ERR_VERSUSSTATE_NOTFOUND, msg=E.errmsg(E.ERR_VERSUSSTATE_NOTFOUND)))
            return
        yield self.leave_state(user, sid)
        ret = dict(timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class InfoHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('versus info', '/versus/info/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        Param('sid', True, str, '1', '1', 'sid'),
        ], filters=[ps_filter], description="Get versus info")
    def post(self):
        try:
            sid = self.get_argument("sid")
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        versus = yield self.get_versus(uid, sid)
        res = yield self.sql.runQuery("SELECT versus_coin, timestamp FROM core_userstate WHERE user_id=%s LIMIT 1", (uid, ))
        if res:
            versus_coin, timestamp = res[0]
        else:
            versus_coin = timestamp = 0
        if versus:
            rand_num = 1
            competitor = yield self.random_versus_competitor(versus, uid, rand_num, sid)
            cuser = dict(versus_coin=versus_coin,
                         guards1=versus['guards1'].keys(),
                         guards2=versus['guards2'].keys(),
                         competitor=competitor,
                         formation1=versus['formation1'],
                         formation2=versus['formation2'],
                         now_rank=versus['now_rank'],
                         before_rank=versus['before_rank'],
                         positions1=versus['positions1'],
                         positions2=versus['positions2']
                         )
        else:
            raise web.HTTPError(400, "Argument error")

        versustime = yield self.redis.get('versustime:%s' % uid) or 0
        versustimes = yield self.redis.get('versustimes:%s' % uid) or 0
        if not versustime:
            versustime = 0
        if not versustimes:
            versustimes = 0
            yield self.redis.set('versustimes:%s' % uid, versustimes)
        if versustimes >= E.limit_by_versus:
            cuser['interval'] = 0
            cuser['left_times'] = 0
            cuser['total_times'] = E.limit_by_versus
        else:
            interval_times = int(time.time()) - versustime
            if interval_times >= E.timer_by_versus:
                interval = 0
            else:
                interval = E.timer_by_versus - interval_times
            if versustimes == 0:
                interval = 0
            if interval < 0:
                interval = 0
            cuser['interval'] = interval
            cuser['left_times'] = E.limit_by_versus - versustimes
            cuser['total_times'] = E.limit_by_versus
        if user['xp']/100000 < D.VERSUS_OPEN_LIMIT:
            versusmark = 0
        else:
            versusmark = yield self.redis.get('versusmark:%s' % uid) 
            if not versusmark:
                versusmark = 0
        reset_times = yield self.redis.get('versusresets:%s' % uid)
        if not reset_times:
            reset_times = 0
        cuser['reset_times'] = reset_times
        rate = E.earn4versus(versus['now_rank'])
        times = float(int(time.time()) - timestamp)/3600
        reward = int(rate.get('versus_coin', 0)*times)
        cuser['versus_coin'] = versus_coin
        ret = dict(user=cuser, versus=versusmark, reward=reward, rate=int(rate.get('versus_coin', 0)), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class GetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('versus get', '/versus/get/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('cid', True, str, '1', '1', 'cid'),
        Param('sid', True, str, '1', '1', 'state id'),
        ], filters=[ps_filter], description="versus get")
    def post(self):

        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return
        try:
            cid = self.get_argument("cid")
            sid = self.get_argument("sid")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        cversus = yield self.get_versus(cid, sid)
        if not cversus:
            raise web.HTTPError(400, "敌人已不在当前州")
        #print 'uid', uid
        if str(cid) ==  str(uid):
            versus = yield self.get_versus(uid, sid)
            if versus['now_rank'] != 1:
                raise web.HTTPError(400, "Argument error")
        versustimes = yield self.redis.get('versustimes:%s' % uid)
        if versustimes:
            if versustimes >= E.limit_by_versus:
                self.write(dict(err=E.ERR_DISSATISFY_MAXENTRY, msg=E.errmsg(E.ERR_DISSATISFY_MAXENTRY)))
                return
        versustime = yield self.redis.get('versustime:%s' % uid)
        if versustime:
            if versustime != 0:
                interval_times = int(time.time()) - versustime
                if interval_times >= E.timer_by_versus:
                    interval = 0
                else:
                    interval = E.timer_by_versus - interval_times
                if versustimes == 0:
                    interval = 0
                if interval != 0:
                    self.write(dict(err=E.ERR_DISSATISFY_COLDDOWN, msg=E.errmsg(E.ERR_DISSATISFY_COLDDOWN)))
                    return
            else:
                self.write(dict(err=E.ERR_DISSATISFY_COLDDOWN, msg=E.errmsg(E.ERR_DISSATISFY_COLDDOWN)))
                return
        else:
            versustime = 0

        # cwork = E.tagworks(user, {'VERSUS': 1})
        # if cwork:
        #     nuser = dict(works=user['works'])
        #     yield self.set_user(uid, **nuser)

        fid = 'versus' + uuid.uuid4().hex
        yield self.set_versusflush(fid, ':'.join([cid, sid]))
        ret = dict(out=dict(flush=fid), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)

        yield self.redis.incr('versustimes:%s' % uid)
        yield self.redis.set('versustime:%s' % uid, int(time.time()))

@handler
class SetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('versus set', '/versus/set/', [
        Param('fid', True, str, '0cb9abd2f380497198c769344279a7cd', '0cb9abd2f380497198c769344279a7cd', 'fid'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        Param('hids1', True, str, '01002,01001', '01002,01001', 'hids'),
        Param('formation1', True, str, '1', '1', 'formation'),
        Param('hids2', True, str, '01002,01001', '01002,01001', 'hids'),
        Param('formation2', True, str, '1', '1', 'formation'),
        Param('chids1', True, str, '01002,01001', '01002,01001', 'chids'),
        Param('cformation1', True, str, '1', '1', 'cformation'),
        Param('chids2', True, str, '01002,01001', '01002,01001', 'chids'),
        Param('cformation2', True, str, '1', '1', 'cformation'),
        Param('result', True, int, 1, 1, 'result'),
        ], filters=[ps_filter], description="versus set")
    def post(self):
        #print 'SetHandler get()'

        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return
        try:
            fid = self.get_argument("fid")
            result = self.get_argument('result', 1)
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        fid = yield self.get_versusflush(fid)
        cid, sid = fid.split(':')
        cuser = yield self.get_user(cid)
        if int(result) == 1:
            if str(uid) != str(cid):
                if cuser:
                    now_rank, before_rank, last_rank = yield self.update_versusresult(user, cid, E.true, sid)
                    if now_rank < before_rank:
                        before = before_rank
                        up = before - now_rank
                        now_rank, before_rank, last_rank, awards = yield self.update_versusrank(user, now_rank, before_rank, last_rank, sid)
                        #sender, to_id, title, content, awards
                        #mail = D.VERSUSMAIL
                        #content = mail['content'] % (now_rank, up)
                        #if awards:
                        #    yield self.send_mails(mail['sender'], uid, mail['title'], content, awards)
                        if now_rank == 1:
                            yield self.redis.rpush("message", pickle.dumps([D.VERSUSTOPMESSAGE[0] % user['nickname'], D.VERSUSTOPMESSAGE[1] % int(time.time())]))
                        cuser = dict(now_rank=now_rank, before_rank=before, last_rank=last_rank, up=up, awards=awards)
                    else:
                        cuser = dict(now_rank=now_rank, before_rank=before_rank, last_rank=last_rank)
                versuswintimes = yield self.redis.incr('versuswintimes:%s' % uid)
                if versuswintimes >= 3:
                    yield self.redis.rpush("message", pickle.dumps([D.VERSUSWINMESSAGE[0] % user['nickname'], D.VERSUSWINMESSAGE[1] % int(time.time())]))
                yield self.set_versus(uid, sid)
            ret = dict(user=cuser, timestamp=int(time.time()))

        else:
            if str(uid) != str(cid):
                yield self.update_versusresult(user, cid, E.false, sid)
                yield self.redis.delete('versuswintimes:%s' % uid)

            ret = dict(timestamp=int(time.time()))
        yield self.redis.set('versusmark:%s' % cid, E.true)
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)
        if uu:
            yield self.set_uu(uu, ret)

@handler
class GuardHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('versus guard', '/versus/guard/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('sid', True, str, '1', '1', 'state id'),
        Param('heros1', True, str, '01001', '01001', 'heros1'),
        Param('positions1', True, str, '01001', '01001', 'positions1'),
        Param('formation1', True, str, '1', '1', 'formation1'),
        Param('heros2', True, str, '01001', '01001', 'heros2'),
        Param('positions2', True, str, '01001', '01001', 'positions2'),
        Param('formation2', True, str, '1', '1', 'formation2'),
        ], filters=[ps_filter], description="versus guard")
    def post(self):
        try:
            sid = self.get_argument("sid")
            heros1 = self.get_argument("heros1")
            positions1 = self.get_argument("positions1")
            formation1 = self.get_argument("formation1")
            heros2 = self.get_argument("heros2")
            positions2 = self.get_argument("positions2")
            formation2 = self.get_argument("formation2")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        if len(self.arg('heros1').split(',')) > 5:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        if (heros1 and positions1 and formation1) and (heros2 and positions2 and formation2):
            yield self.update_versusguard(uid, sid, self.arg('heros1').split(','), self.arg('positions1').split(','), formation1,\
                                          self.arg('heros2').split(','), self.arg('positions2').split(','), formation2)
            ret = dict(timestamp=int(time.time()))
            reb = zlib.compress(escape.json_encode(ret))
            self.write(ret)
        else:
            raise web.HTTPError(400, "Argument error")

@handler
class ResetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('versus reset', '/versus/reset/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="versus reset")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        versusresets = yield self.redis.get('versusresets:%s' % uid)
        if versusresets:
            if versusresets >= E.versusmaxtimes(user['vrock']):
                self.write(dict(err=E.ERR_DISSATISFY_MAXRESETS, msg=E.errmsg(E.ERR_DISSATISFY_MAXRESETS)))
                return
        else:
            versusresets = 0
            yield self.redis.set('versusresets:%s' % uid, versusresets)
        if user['rock'] < D.VERSUSRESET[versusresets*2+1]:
            self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
            return
        user['rock'] -= D.VERSUSRESET[versusresets*2+1]
        consume = yield self.set_consume(user, D.VERSUSRESET[versusresets*2+1])
        cuser = dict(rock=user['rock'])
        yield self.redis.incr('versusresets:%s' % uid)
        yield self.redis.set('versustimes:%s' % uid, 0)
        logmsg = u'竞技场:第%s次重置次数' % (versusresets+1)
        yield self.set_user(uid, logmsg, **cuser)
        cuser['left_times'] = E.limit_by_versus
        consume = yield self.get_consume(user)
        cuser['consume'] = consume
        ret = dict(user=cuser, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class ResetCDHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('versus resetcd', '/versus/resetcd/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="versus resetcd")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        if user['rock'] < E.cost_for_resetcd:
            self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
            return
        versustimes = yield self.redis.get('versustimes:%s' % uid)
        versustime = yield self.redis.get('versustime:%s' % uid)
        if not versustimes:
            versustimes = 0

        if versustimes > E.limit_by_versus:
            self.write(dict(err=E.ERR_DISSATISFY_MAXENTRY, msg=E.errmsg(E.ERR_DISSATISFY_MAXENTRY)))
            return
        yield self.redis.set('versustime:%s' % uid, 0)
        user['rock'] -= E.cost_for_resetcd
        consume = yield self.set_consume(user, E.cost_for_resetcd)
        cuser = dict(rock=user['rock'])
        logmsg = u'竞技场:重置冷却时间'
        yield self.set_user(uid, logmsg, **cuser)

        cuser['interval'] = 0
        cuser['left_times'] = E.limit_by_versus - versustimes
        cuser['total_times'] = E.limit_by_versus
        consume = yield self.get_consume(user)
        cuser['consume'] = consume
        ret = dict(user=cuser, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class RankHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('versus rank', '/versus/rank/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('sid', True, str, '1', '1', 'state id'),
        ], filters=[ps_filter], description="versus rank")
    def post(self):
        try:
            sid = self.get_argument("sid")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        query = "SELECT user_id, now_rank FROM %s" % D.VERSUSSTATE[sid] + " ORDER BY now_rank LIMIT 50"
        res = yield self.sql.runQuery(query, (uid, ))
        rank = {}
        if res:
            for r in res:
                versus = yield self.get_versus(r[0], sid)
                cuser = yield self.get_user(r[0])
                beautys = yield self.get_beautys(cuser)
                if versus:
                    guards1 = {}
                    for key in versus['guards1'].keys():
                        guards1[key] = cuser['heros'].get(key, {})
                    guards2 = {}
                    for key in versus['guards2'].keys():
                        guards2[key] = cuser['heros'].get(key, {})
                    rank[r[1]] = dict(uid=versus['uid'],
                                      guards1=guards1,
                                      guards2=guards2,
                                      #now_rank=versus['now_rank'],
                                      now_rank=r[1],
                                      nickname=versus['nickname'],
                                      xp=versus['xp'],
                                      avat=versus['avat'],
                                      win_times=versus['win_times'],
                                      formation1=versus['formation1'],
                                      formation2=versus['formation2'],
                                      beautys=beautys)
        ret = dict(rank=rank, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class ChangeHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('versus change', '/versus/change/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('sid', True, str, '1', '1', 'state id'),
        ], filters=[ps_filter], description="versus change")
    def post(self):
        try:
            sid = self.get_argument("sid")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        versus = yield self.get_versus(uid, sid)
        if versus:
            rand_num = 10
            competitor = yield self.random_versus_competitor(versus, uid, rand_num, sid)
            ret = dict(competitor=competitor, timestamp=int(time.time()))
            reb = zlib.compress(escape.json_encode(ret))
            self.write(ret)
        else:
            raise web.HTTPError(400, "Argument error")

@handler
class RecordHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('versus record', '/versus/record/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('sid', True, str, '1', '1', 'state id'),
        ], filters=[ps_filter], description="versus record")
    def post(self):
        try:
            sid = self.get_argument("sid")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        versus = yield self.get_versus(uid, sid)
        yield self.redis.set('versusmark:%s' % uid, E.false)
        query = "SELECT competitor_id, result, ascend, timestamp FROM %s" % "".join([D.VERSUSSTATE[sid], "result"]) + " WHERE user_id=%s ORDER BY timestamp"
        res = yield self.sql.runQuery(query, (uid, ))
        records = []
        for r in res:
            versus = yield self.get_versus(r[0], sid)
            cuser = yield self.get_user(r[0])
            beautys = yield self.get_beautys(cuser)
            result = r[1]
            if versus:
                guards1 = {}
                for key in versus['guards1'].keys():
                    guards1[key] = versus['heros'].get(key, {})
                guards2 = {}
                for key in versus['guards2'].keys():
                    guards2[key] = versus['heros'].get(key, {})

                records.append(dict(uid=r[0],
                                    result=result,
                                    ascend=r[2],
                                    timestamp=r[3],
                                    xp=versus['xp'],
                                    avat=versus['avat'],
                                    nickname=versus['nickname'],
                                    heros1=guards1,
                                    heros2=guards2,
                                    formation1=versus['formation1'],
                                    formation2=versus['formation2'],
                                    beautys=beautys)
                               )
        query = "SELECT user_id, result, ascend, timestamp FROM %s" % "".join([D.VERSUSSTATE[sid], "result"]) + " WHERE competitor_id=%s ORDER BY timestamp"
        res = yield self.sql.runQuery(query, (uid, ))
        for r in res:
            versus = yield self.get_versus(r[0], sid)
            cuser = yield self.get_user(r[0])
            beautys = yield self.get_beautys(cuser)
            result = r[1]
            if versus:
                guards1 = {}
                for key in versus['guards1'].keys():
                    guards1[key] = versus['heros'].get(key, {})
                guards2 = {}
                for key in versus['guards2'].keys():
                    guards2[key] = versus['heros'].get(key, {})

                if result == E.true:
                    result = E.false
                    ascend = -r[2]
                else:
                    result = E.true
                    ascend = r[2]
                records.append(dict(uid=r[0],
                                    result=result,
                                    ascend=ascend,
                                    timestamp=r[3],
                                    xp=versus['xp'],
                                    avat=versus['avat'],
                                    nickname=versus['nickname'],
                                    heros1=guards1,
                                    heros2=guards2,
                                    formation1=versus['formation1'],
                                    formation2=versus['formation2'],
                                    beautys=beautys)
                               )
        ret = dict(records=records, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)


@handler
class ShopHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('versus shop', '/versus/shop/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="versus shop")
    def post(self):
        uid = self.uid
        res = yield self.sql.runQuery("SELECT versus_coin FROM core_userstate WHERE user_id=%s LIMIT 1", (uid, ))
        if res:
            versus_coin, = res[0]
        else:
            versus_coin = 0
        versusprod_list = yield self.redis.lrange('versusprod:%s' % uid, 0, -1)
        versusrefresh = yield self.redis.get('versusrefreshes:%s' % uid)
        if not versusrefresh:
            versusrefresh = 0
        prods = copy.deepcopy(D.VERSUSPROD)

        for pid in prods.keys():
            if int(pid) in versusprod_list:
                prods[pid]['is_buy'] = 1
            else:
                prods[pid]['is_buy'] = 0
        ret = dict(prods=prods, timestamp=int(time.time()), refresh_times=versusrefresh, versus_coin=versus_coin)
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class BuyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('versus buy', '/versus/buy/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        Param('pid', True, str, '01030', '01030', 'pid'),
        ], filters=[ps_filter], description="versus buy")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        if self.has_arg('pid') and self.arg('pid') in D.VERSUSPROD:
            pid = self.arg('pid')
            num = D.VERSUSPROD[pid]['num']
            versusprod_list = yield self.redis.lrange('versusprod:%s' % uid, 0, -1)
            if int(pid) in versusprod_list:
                self.write(dict(err=E.ERR_DUPLICATE_BUY, msg=E.errmsg(E.ERR_DUPLICATE_BUY)))
                return
            cost = E.cost4versus(pid)
            #print 'cost', cost
            if cost:
                res = yield self.sql.runQuery("SELECT versus_coin FROM core_userstate WHERE user_id=%s LIMIT 1", (uid, ))
                if res:
                    versus_coin, = res[0]
                else:
                    versus_coin = 0
                versusrefresh = yield self.redis.get('versusrefreshes:%s' % uid)
                if not versusrefresh:
                    versusrefresh = 0
                if versus_coin < cost:
                    self.write(dict(err=E.ERR_NOTENOUGH_VERSUSCOIN, msg=E.errmsg(E.ERR_NOTENOUGH_VERSUSCOIN)))
                    return
                else:
                    versus_coin = versus_coin - cost
                    query = "UPDATE core_userstate SET versus_coin=%s WHERE user_id=%s RETURNING id"
                    params = (versus_coin, uid)
                    for i in range(5):
                        try:
                            yield self.sql.runQuery(query, params)
                            break
                        except storage.IntegrityError:
                            log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                            continue

                    if pid in user['prods']:
                        user['prods'][pid] += int(num)
                    else:
                        user['prods'][pid] = int(num)
                    if user['prods'][pid] > 9999:
                        user['prods'][pid] = 9999
                    cuser = dict(prods=user['prods'])
                    yield self.redis.lpush('versusprod:%s' % uid, pid)
                    logmsg = u'竞技场:竞技币购买%s' % pid
                    yield self.set_user(uid, logmsg, **cuser)
                    cuser = dict(cuser=cuser, versus_coin=versus_coin)
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
    @api('versus refresh', '/versus/refresh/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="versus refresh")
    def post(self):
        uid = self.uid
        versusrefresh = yield self.redis.get('versusrefreshes:%s' % uid)
        if not versusrefresh:
            versusrefresh = 0
            yield self.redis.set('versusrefreshes:%s' % uid, versusrefresh)
        res = yield self.sql.runQuery("SELECT versus_coin FROM core_userstate WHERE user_id=%s LIMIT 1", (uid, ))
        if res:
            versus_coin, = res[0]
        else:
            versus_coin = 0
        if versusrefresh >= 0:
            if versusrefresh < E.limit_by_refresh:
                if versus_coin < D.VERSUSREFRESH[versusrefresh*2+1]:
                    self.write(dict(err=E.ERR_NOTENOUGH_VERSUSCOIN, msg=E.errmsg(E.ERR_NOTENOUGH_VERSUSCOIN)))
                    return
                versus_coin = versus_coin - D.VERSUSREFRESH[versusrefresh*2+1]
                query = "UPDATE core_userstate SET versus_coin=%s WHERE user_id=%s RETURNING id"
                params = (versus_coin, uid)
                for i in range(5):
                    try:
                        yield self.sql.runQuery(query, params)
                        break
                    except storage.IntegrityError:
                        log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                        continue
                yield self.redis.incr('versusrefreshes:%s' % uid)
                yield self.redis.delete('versusprod:%s' % uid)
                cuser = dict(versus_coin=versus_coin)
                ret = dict(user=cuser, prods = D.VERSUSPROD, timestamp=int(time.time()))
                reb = zlib.compress(escape.json_encode(ret))
                self.write(ret)
            else:
                self.write(dict(err=E.ERR_DISSATISFY_MAXREFRESHES, msg=E.errmsg(E.ERR_DISSATISFY_MAXREFRESHES)))
                return


@handler
class RewardHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('versus reward', '/versus/reward/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        Param('sid', True, str, '1', '1', 'state id'),
    ], filters=[ps_filter], description="Get versus reward")
    def post(self):
        try:
            sid = self.get_argument("sid")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        versus = yield self.get_versus(uid, sid)
        rate = E.earn4versus(versus['now_rank'])
        res = yield self.sql.runQuery("SELECT timestamp FROM core_userstate WHERE user_id=%s LIMIT 1", (uid, ))
        if res:
            timestamp, = res[0]
        else:
            timestamp = int(time.time())

        times = float(int(time.time()) - timestamp)/3600
        versus_coin = int(rate.get('versus_coin', 0)*times)
        query = "UPDATE core_userstate SET versus_coin=versus_coin+%s, timestamp=%s WHERE user_id=%s RETURNING versus_coin"
        params = (versus_coin, int(time.time()), uid)
        for i in range(5):
            try:
                versus_coin = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        yield self.set_versus(uid, sid)
        cuser = dict(versus_coin=versus_coin)
        ret = dict(user=cuser, rate=rate.get('versus_coin', 0), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)