# -*- coding: utf-8 -*-

import random
import time
import zlib
import uuid
import json
import datetime
import pickle
import hashlib
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
    @api('Hunt info', '/hunt/info/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Hunt info")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        hunttimes = yield self.redis.get('hunttimes:%s' % uid)
        huntresets = yield self.redis.get('huntresets:%s' % uid)
        searchtimes = yield self.redis.get('searchtimes:%s' % uid)

        if not hunttimes:
            hunttimes = 0
        if not searchtimes:
            searchtimes = 0
        if not huntresets:
            huntresets = 0
        hunt = dict(hunttimes=hunttimes, maxhunttimes=E.limit_by_hunt, resettimes=huntresets)
        cost = E.cost4search(user['xp'], searchtimes+1)

        mine = []
        guards_list = []
        res = yield self.sql.runQuery("SELECT id, jguards, formation, sword, type, size, created_at,\
         ended_at, jstocks, jpositions FROM core_mine WHERE user_id=%s AND status=%s", (uid, E.busy))
        if res:
            for r in res:
                guards = r[1] and escape.json_decode(r[1]) or {}
                created_at = r[6]
                ended_at=r[7]
                stocks = r[8] and escape.json_decode(r[8]) or {}
                positions = r[9] and escape.json_decode(r[9]) or {}
                rate = E.earn4mine(guards.keys(), user['heros'], r[4])
                times = float(int(time.time()) - int(created_at))/3600
                gold = stocks.get('gold', 0) + int(rate.get('gold', 0)*times)
                rock = stocks.get('rock', 0) + int(rate.get('rock', 0)*times)
                feat = stocks.get('feat', 0) + int(rate.get('feat', 0)*times)
                stocks = dict(gold=gold, feat=feat, rock=rock)
                #guards_list.extend(guards.keys())
                mine.append(dict(id=r[0], guards=guards, formation=r[2], sword=r[3], type=r[4],\
                 size=r[5], created_at=r[6], ended_at=r[7], rate=rate, stocks=stocks, positions=positions))

        yield self.redis.set('minenum:%s' % uid, len(res))
        #yield self.redis.set('guards_list:%s' % uid, pickle.dumps(guards_list))
        ret = dict(out=dict(cost=cost, hunt=hunt, mine=mine), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class MineHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hunt mine', '/hunt/mine/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('heros', True, str, '01001', '01001', 'heros'),
        Param('positions', True, str, '0', '0', 'positions'),
        Param('formation', True, str, '1', '1', 'formation'),
        Param('type', True, int, '0/1', '0', u'0代表开荒, 1代表挖矿'),
        Param('size', True, int, '0/1/2', '0', u'0代表小型, 1代表中型, 2代表大型'),
        ], filters=[ps_filter], description="Hunt mine")
    def post(self):
        try:
            heros = self.get_argument("heros")
            positions = self.get_argument("positions")
            formation = self.get_argument("formation")
            mtype = int(self.get_argument("type"))
            size = int(self.get_argument("size"))
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        try:
            duration = E.duration4mine(mtype, size)
        except Exception:
            raise web.HTTPError(400, "Argument error")
        minemaxnum = E.minemaxnum(user['vrock'])
        minenum = yield self.redis.get('minenum:%s' % uid)
        if not minenum:
            minenum = 0
        if int(minenum)+1 > minemaxnum:
            self.write(dict(err=E.ERR_MAXMINE_ALREADYGOT, msg=E.errmsg(E.ERR_MAXMINE_ALREADYGOT)))
            return
        #guards = heros.split(',')
        heros = heros.split(',')
        positions = positions.split(',')
        pos = dict(zip(heros, positions))
        if filter(lambda j:j not in user['heros'], heros):
            raise web.HTTPError(400, "Argument error")
        all_guards, now_guards = yield self.update_mine_guards(uid)
        for h in heros:
            if h in all_guards:
                self.write(dict(err=E.ERR_HERO_BUSY, msg=E.errmsg(E.ERR_HERO_BUSY)))
                return

        minenum = yield self.redis.incr('minenum:%s' % uid)
        mid, = yield self.create_mine(uid, heros, user['heros'], formation, mtype, size, pos)
        yield self.redis.set('mineguards:%s:%s' % (uid, mid), pickle.dumps(heros))
        mine = yield self.get_mine(uid, mid)
        cwork = E.tagworks(user, {'MINE': 1})
        if cwork:
            cuser = dict(works=user['works'])
            yield self.set_user(uid, **cuser)
        ret = dict(out=dict(mine=mine), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class GuardHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hunt guard', '/hunt/guard/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('mid', True, str, '1', '1', 'mid'),
        Param('heros', True, str, '01001', '01001', 'heros'),
        Param('positions', True, str, '0', '0', 'positions'),
        Param('formation', True, str, '1', '1', 'formation'),
        ], filters=[ps_filter], description="Hunt guard")
    def post(self):
        try:
            mid = self.get_argument("mid")
            heros = self.get_argument("heros")
            positions = self.get_argument("positions")
            formation = self.get_argument("formation")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        mine = yield self.get_mine(uid, mid)
        if not mine:
            self.write(dict(err=E.ERR_MINE_ALREADYGOT, msg=E.errmsg(E.ERR_MINE_ALREADYGOT)))
            return
        sword = mine.get('sword', 0)
        created_at = mine.get('created_at', 0)
        ended_at = mine.get('ended_at', 0)
        guards = mine.get('guards', {})
        if int(time.time()) >= int(ended_at):
            self.write(dict(err=E.ERR_HARVEST_ALREADYGOT, msg=E.errmsg(E.ERR_HARVEST_ALREADYGOT)))
            return
        heros = heros.split(',')
        positions = positions.split(',')
        pos = dict(zip(heros, positions))
        heros_list = filter(lambda j:j not in user['heros'], heros)
        if heros_list:
            raise web.HTTPError(400, "Argument error")
        all_guards, now_guards = yield self.update_mine_guards(uid, mid)
        for h in heros:
            if h not in now_guards and h in all_guards:
                self.write(dict(err=E.ERR_HERO_BUSY, msg=E.errmsg(E.ERR_HERO_BUSY)))
                return
        yield self.redis.set("mineguards:%s:%s" % (uid, mid), pickle.dumps(heros))
        jguards = {}
        for j in heros:
            jguards[j] = user['heros'][j]
        yield self.update_mine(uid, mid, jguards, formation, mine['created_at'], mine['stocks'],\
         mine['type'], user['heros'], pos)
        mine = yield self.get_mine(uid, mid)
        ret = dict(out=dict(mine=mine), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class HarvestHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hunt harvest', '/hunt/harvest/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('mid', True, str, '1', '1', 'mid'),
        ], filters=[ps_filter], description="Hunt harvest")
    def post(self):
        try:
            mid = self.get_argument("mid")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        mine = yield self.get_mine(uid, mid)
        if mine:
            if int(time.time()) >= mine['ended_at'] and mine['status'] == E.busy:
                #stocks = escape.json_decode(mine['stocks'])
                stocks = mine['stocks']
                rate =  E.earn4mine(mine['guards'].keys(), user['heros'], mine['type'])
                duration = E.duration4mine(mine['type'], mine['size'])
                times = float(int(mine['ended_at']) - int(mine['created_at']))/3600
                gold = stocks.get('gold', 0) + int(rate.get('gold', 0)*times)
                rock = stocks.get('rock', 0) + int(rate.get('rock', 0)*times)
                feat = stocks.get('rock', 0) + int(rate.get('feat', 0)*times)
                awards = dict(gold=gold, rock=rock, feat=feat)
                user['gold'] += gold
                user['feat'] += feat
                user['rock'] += rock
                cuser = dict(gold=user['gold'], feat=user['feat'], rock=user['rock'])
                logmsg = u'藏宝:宝藏收获'
                yield self.set_user(uid, logmsg, **cuser)
                yield self.sql.runQuery("UPDATE core_mine set status=%s WHERE id=%s AND user_id=%s RETURNING id", (E.done, mid, uid))
                yield self.redis.delete("mineguards:%s:%s" % (uid, mid))
                yield self.redis.decr('minenum:%s' % uid)
                ret = dict(out=dict(awards=awards), user=cuser, timestamp=int(time.time()))
                reb = zlib.compress(escape.json_encode(ret))
                self.write(ret)
            else:
                self.write(dict(err=E.ERR_DISSATISFY_HARVEST, msg=E.errmsg(E.ERR_DISSATISFY_HARVEST)))
                return
        else:
            self.write(dict(err=E.ERR_MINE_ALREADYGOT, msg=E.errmsg(E.ERR_MINE_ALREADYGOT)))
            return

@handler
class SearchHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hunt search', '/hunt/search/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Hunt search")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        searchtimes = yield self.redis.get('searchtimes:%s' % uid)
        if not searchtimes:
            searchtimes = 0
        # if searchtimes > E.limit_by_search:
        #     self.write(dict(err=E.ERR_DISSATISFY_MAXENTRY, msg=E.errmsg(E.ERR_DISSATISFY_MAXENTRY)))
        #     return
        cost = E.cost4search(user['xp'], searchtimes+1)
        if user['gold'] < cost.get('gold', 0):
            self.write(dict(err=E.ERR_NOTENOUGH_GOLD, msg=E.errmsg(E.ERR_NOTENOUGH_GOLD)))
            return
        competitor = {}
        res = yield self.sql.runQuery("SELECT a.user_id, a.jguards, a.formation, b.nickname, b.xp, b.avat, a.id, "
                                      "a.type, a.jpositions FROM core_mine AS a, core_user AS b "
                                      "WHERE a.user_id=b.id AND a.user_id<>%s OFFSET FLOOR(RANDOM() * "
                                      "(SELECT COUNT(*) FROM core_mine WHERE user_id<>%s)) LIMIT 1", (uid, uid))
        if res:
            for r in res:
                lock = yield self.redis.get('lock:%s' % r[0])
                if not lock:
                    competitor = dict(uid=r[0],
                        guards=r[1] and escape.json_decode(r[1]) or {},
                        formation=r[2],
                        nickname=r[3],
                        xp=r[4],
                        avat=r[5],
                        id=r[6],
                        type=r[7],
                        positions=r[8] and escape.json_decode(r[8]) or {},
                        )
                    #yield self.redis.setex("lock:%s" % r[0], D.MINELOCKTIME, r[0])

        if competitor:
            cuser = yield self.get_user(competitor['uid'])
            beautys = yield self.get_beautys(cuser)
            competitor['beautys'] = beautys
            earn = E.earn4rape(cuser, competitor['guards'].keys(), cuser['heros'], competitor['type'])
            times = E.double4hunt(user['vrock'])
            earn['gold'] = earn['gold']*times
            earn['feat'] = earn['feat']*times
            earn['rock'] = earn['rock']*times
        else:
            earn = dict(rock=0, gold=0)
        user['gold'] -= cost.get('gold', 0)
        cuser = dict(gold=user['gold'])
        nuser = dict(gold=user['gold'])
        logmsg = u'藏宝:第%s次搜索宝藏' % (searchtimes+1)
        yield self.set_user(uid, logmsg, **cuser)
        yield self.redis.incr('searchtimes:%s' % uid)
        ret = dict(out=dict(competitor=competitor, cost=cost, earn=earn), user=nuser, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class GetHandler(ApiHandler):


    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hunt get', '/hunt/get/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('cid', True, str, '1', '1', 'cid'),
        Param('mid', True, str, '1', '1', 'mid'),
        ], filters=[ps_filter], description="Hunt get")
    def post(self):
        try:
            cid = self.get_argument("cid")
            mid = self.get_argument("mid")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        hunttimes = yield self.redis.get('hunttimes:%s' % uid)
        if not hunttimes:
            hunttimes = 0
        if hunttimes >= E.limit_by_hunt:
            self.write(dict(err=E.ERR_DISSATISFY_MAXENTRY, msg=E.errmsg(E.ERR_DISSATISFY_MAXENTRY)))
            return
        res = yield self.sql.runQuery("SELECT user_id, jguards, formation, type FROM core_mine WHERE user_id<>%s AND user_id=%s AND\
                                       id=%s LIMIT 1", (uid, cid, mid))
        if res:
            guards = res[0][1] and escape.json_decode(res[0][1]) or {}
            cuser = yield self.get_user(res[0][0])
            earn = E.earn4rape(cuser, guards.keys(), cuser['heros'], res[0][3])
            times = E.double4hunt(user['vrock'])
            earn['gold'] = earn['gold']*times
            earn['feat'] = earn['feat']*times
            earn['rock'] = earn['rock']*times
        else:
            raise web.HTTPError(400, "Argument error")
        yield self.redis.incr('hunttimes:%s' % uid)
        match = {
            'cid': self.arg('cid'),
            'gold': earn.get('gold', 0),
            'rock': earn.get('rock', 0),
            'feat': earn.get('feat', 0),
        }
        fid = uuid.uuid4().hex
        yield self.set_flush(fid, match)
        cwork = E.tagworks(user, {'HUNT': 1})
        if cwork:
            cuser = dict(works=user['works'])
            yield self.set_user(uid, **cuser)
        ret = dict(out=dict(flush=fid, match=match), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class SetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hunt set', '/hunt/set/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('fid', True, str, '1', '1', 'fid'),
        Param('hids', True, str, '01002,01001', '01002,01001', 'hids'),
        Param('formation', True, str, '1', '1', 'formation'),
        Param('result', True, int, 1, 1, 'result'),
        ], filters=[ps_filter], description="Hunt set")
    def post(self):
        try:
            fid = self.get_argument("fid")
            hids = self.get_argument("hids")
            formation = self.get_argument("formation")
            result = self.get_argument("result")
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)

        if self.has_arg('fid') and self.has_arg('result'):
            try:
                match = yield self.get_flush(self.arg('fid'))
                cid = match.get('cid')
                mid = match.get('mid')
                match['result'] = self.arg('result')
                #loser = yield self.get_user(cid)
            except Exception:
                raise web.HTTPError(400, "Argument error")
            if int(self.arg('result')):
                yield self.redis.lpush('huntrecord:%s' % cid, (D.DEFENCE_FAILED % (E.win, uid, int(time.time()), hids,\
                 formation, user['nickname']), ))
            else:
                yield self.redis.lpush('huntrecord:%s' % cid, (D.DEFENCE_SUCCESS % (E.lose, uid, int(time.time()), hids,\
                 formation, user['nickname']), ))

            fid = uuid.uuid4().hex
            yield self.set_bootyflush(fid, match)
            ret = dict(out=dict(flush=fid, match=match), timestamp=int(time.time()))
            reb = zlib.compress(escape.json_encode(ret))
            self.write(ret)
        else:
            raise web.HTTPError(400, "Argument error")

@handler
class BootyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hunt booty', '/hunt/booty/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('fid', True, str, '1', '1', 'fid'),
        ], filters=[ps_filter], description="Hunt booty")
    def post(self):
        try:
            fid = self.get_argument("fid")
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        try:
            match = yield self.get_bootyflush(self.arg('fid'))
            result = match.get('result')
            gold = match.get('gold')
            feat = match.get('feat')
            rock = match.get('rock')
        except Exception:
            raise web.HTTPError(400, "Argument error")
        if int(result) == E.win:
            user['gold'] += gold
            user['feat'] += feat
            user['rock'] += rock
            cuser = dict(gold=user['gold'], feat=user['feat'], rock=user['rock'])
            awards = dict(gold=gold, feat=feat, rock=rock)
            logmsg = u'藏宝:宝藏掠夺'
            yield self.set_user(uid, logmsg, **cuser)
            ret = dict(out=dict(awards=awards), user=cuser, timestamp=int(time.time()))
        else:
            ret = dict(timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class RecordHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hunt record', '/hunt/record/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Hunt record")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        record = []
        res = yield self.redis.lrange('huntrecord:%s' % uid, 0, -1)
        for r in res:
            result, cid, timestamp, hids, formation, content = r.split(':')
            cuser = yield self.get_user(cid)
            beautys = yield self.get_beautys(cuser)
            heros = {}
            for h in hids.split(','):
                if h in cuser['heros']:
                    heros[h] = cuser['heros'][h]
            record.append(dict(timestamp=int(timestamp),
                               content=content,
                               nickname=cuser['nickname'],
                               avat=cuser['avat'],
                               xp=cuser['xp'],
                               result=result,
                               heros=heros,
                               formation=formation,
                               beautys=beautys))

        ret = dict(out=dict(record=record), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class ResetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hunt reset', '/hunt/reset/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Hunt reset")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        huntresets = yield self.redis.get('huntresets:%s' % uid)
        if not huntresets:
            huntresets = 0
        if huntresets > E.huntmaxtimes(user['vrock']):
            self.write(dict(err=E.ERR_DISSATISFY_MAXRESETS, msg=E.errmsg(E.ERR_DISSATISFY_MAXRESETS)))
            return
        else:
            hunttimes = 0
            yield self.redis.set('hunttimes:%s' % uid, 0)
            huntresets = yield self.redis.incr('huntresets:%s' % uid)
        ret = dict(out=dict(hunttimes=hunttimes, resettimes=huntresets), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class CreateUserHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hunt create', '/hunt/create/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Hunt create")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        nuser = E.initdata4user()
        res = yield self.sql.runQuery("SELECT id FROM core_user")
        for r in res:
            uid = r[0]
            query = "INSERT INTO core_mine(user_id, jguards, formation, sword, type, size, status, created_at, ended_at) VALUES (%s,\
                     %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
            params = (uid, nuser['jheros'], E.default_formation, 0, 0, 0, E.busy, int(time.time()), int(time.time())+10)
            #print query % params
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
