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

@handler
class PutHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Prison put', '/prison/put/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('fid', True, str, '1', '1', 'fid'),
        Param('status', True, str, '0/1', '1', '0 release, 1 prison'),    
        ], filters=[ps_filter], description="prison put")
    def get(self):
        try:
            fid = self.get_argument("fid")
            status = self.get_argument("status")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)

        w = yield self.redis.get("win:%s" % fid)
        try:
            wid, cid = w.split(':') 
            loser = yield self.get_user(cid)
        except Exception:
            raise web.HTTPError(400, "Argument error")
        if int(status) and int(uid) == int(wid):
            pid_list = E.check4prisonid(user)
            res = yield self.sql.runQuery("SELECT * FROM core_prison WHERE user_id=%s AND prisoner_id=%s", (uid, cid))
            position = 0
            if not res: 
                res = yield self.sql.runQuery("SELECT position FROM core_prison WHERE user_id=%s", (uid, ))
                pids = list(set(pid_list) - set([r[0] for r in res]))
                if len(res) < len(pid_list):
                    position = pids[0]
                else:
                    self.write(dict(err=E.ERR_PRISION_FULL, msg=E.errmsg(E.ERR_PRISION_FULL)))
                    return
            else:
                self.write(dict(err=E.ERR_REPEAT, msg=E.errmsg(E.ERR_REPEAT)))
                return
        
            yield self.init_prison(user, cid, position)
            yield self.redis.lpush('huntrecord:%s' % cid, (D.DEFENCE_FAILED_PRISON % (E.lose, cid, int(time.time()), loser['nickname']), ))

        else:
            yield self.set_release(user, cid, E.release)
            yield self.redis.lpush('huntrecord:%s' % cid, (D.DEFENCE_FAILED_RELEASE % (E.lose, cid, int(time.time()), loser['nickname']), ))

        prisoner = yield self.get_prison(user)
        ret = dict(prisoner=prisoner, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class InfoHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Prison info', '/prison/info/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="prison info")
    def get(self):
        uid = self.uid
        user = yield self.get_user(uid)
        gainsttimes = yield self.redis.get('gainsttimes:%s' % uid)
        gainstresets = yield self.redis.get('gainstresets:%s' % uid)
        if not gainsttimes:
            gainsttimes = 0
        if not gainstresets:
            gainstresets = 0
        gainst = dict(gainsttimes=gainsttimes, maxgainsttimes=E.gainstmaxtimes(user['vrock']), resettimes=gainstresets)

        res = yield self.sql.runQuery("SELECT a.user_id, b.nickname FROM core_prison AS a, core_user AS b WHERE prisoner_id=%s AND a.user_id=b.id LIMIT 1", (uid, ))
        if res:
            arrest=dict(nickanme=res[0][1], uid=res[0][0])
        else:
            arrest = {}
        prisoner = yield self.get_prison(user)
        ret = dict(prisoner=prisoner, timestamp=int(time.time()), gainst=gainst, arrest=arrest)
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class StatusHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Prison status', '/prison/status/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('cid', False, str, '1', '1', 'cid'),
        Param('status', False, int, '0/1/2', 1, '0 idle, 1 reclaim, 2 assart'),
        Param('result', False, int, '0/1', 1, '0 start, 1 end'),
        ], filters=[ps_filter], description="prison status")
    def get(self):
        uid = self.uid
        user = yield self.get_user(uid)
        if self.has_arg('cid') and self.has_arg('status') and self.has_arg('result'):
            if self.arg('cid') == uid:
                raise web.HTTPError(400, "Argument error")
            prisoner = yield self.set_prison(user, self.arg('cid'), int(self.arg('status')), int(self.arg('result')))
        else:
            prisoner = yield self.get_prison(user)
        ret = dict(prisoner=prisoner, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)


@handler
class HarvestHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Prison harvest', '/prison/harvest/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('cid', False, str, '1', '1', 'cid'),
        Param('status', False, int, '0/1', 1, '0 收获任务, 1 立即完成'),
        ], filters=[ps_filter], description="prison harvest")
    def get(self):
        uid = self.uid
        user = yield self.get_user(uid)
        instanttimes = yield self.redis.get('instanttimes:%s' % uid)
        if not instanttimes:
            instanttimes = 0
        else:
            if instanttimes > E.limit_by_instant:
                self.write(dict(err=E.ERR_DISSATISFY_MAXENTRY, msg=E.errmsg(E.ERR_DISSATISFY_MAXENTRY)))
                return

        if self.has_arg('cid') and self.has_arg('status'):
            hunt = yield self.get_hunt(self.arg('cid'))
            prisoner = yield self.get_user(self.arg('cid'))
            if self.arg('cid') == uid:
                raise web.HTTPError(400, "Argument error")
            if int(self.arg('status')):
                cost = E.cost4instant(instanttimes)
                if user['rock'] < cost.get('rock', 0):
                    self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
                    return 
                else:
                    user['rock'] -= cost.get('rock', 0)
                    #获取奖励
                    earn = E.earn4reclaim(prisoner, hunt['guards'].keys(), prisoner['heros'])
                    user['feat'] = user['feat'] + earn.get('feat', 0)
                    user['gold'] = user['gold'] + earn.get('gold', 0)
                    cuser = dict(rock=user['rock'], feat=user['feat'], gold=user['gold'])
                    yield self.redis.incr('instanttimes:%s' % uid)
                    yield self.set_prison(user, self.arg('cid'), E.idle, E.true)

            else:
                res = yield self.sql.runQuery("SELECT status, created_at FROM core_prison WHERE user_id=%s \
                 AND prisoner_id=%s AND status !=0 LIMIT 1", (user['uid'], self.arg('cid')))
                done = False
                if res:
                    for r in res:     
                        if int(time.time()) - r[1] > E.timer_by_reclaim:
                            interval = 0
                        else:
                            interval = E.timer_by_reclaim - (int(time.time()) - r[1])
                        if interval < 0:
                            interval = 0
                        if not interval:
                            done = True
                if done:
                    earn = E.earn4reclaim(prisoner, hunt['guards'].keys(), prisoner['heros'])
                    user['feat'] = user['feat'] + earn.get('feat', 0)
                    user['gold'] = user['gold'] + earn.get('gold', 0)
                    cuser = dict(feat=user['feat'], gold=user['gold'])
                    yield self.set_prison(user, self.arg('cid'), E.idle, E.true)
                else:
                    self.write(dict(err=E.ERR_DISSATISFY_COLDDOWN, msg=E.errmsg(E.ERR_DISSATISFY_COLDDOWN)))
                    return 
            ret = dict(user=cuser, timestamp=int(time.time()))
            reb = zlib.compress(escape.json_encode(ret))
            self.write(ret)

        else:
            raise web.HTTPError(400, "Argument error")

@handler
class GainstHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Prison gainst', '/prison/gainst/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('cid', True, str, '1', '1', 'cid'),
        Param('result', False, int, 1, 1, '0 反抗失败, 1 反抗成功'),
        ], filters=[ps_filter], description="Prison gainst")
    def get(self):
        uid = self.uid
        user = yield self.get_user(uid)
        gainsttimes = yield self.redis.get('gainsttimes:%s' % uid)
        if not gainsttimes:
            gainsttimes = 0
        else:
            if gainsttimes > E.limit_by_gainst:
                self.write(dict(err=E.ERR_DISSATISFY_MAXENTRY, msg=E.errmsg(E.ERR_DISSATISFY_MAXENTRY)))
                return
        if self.has_arg('cid'):
            if self.arg('cid') == uid:
                raise web.HTTPError(400, "Argument error")
            prisoner = yield self.get_user(self.arg('cid'))
            hunt = yield self.get_hunt(self.arg('cid'))
            if self.has_arg('result'):
                if int(self.arg('result')):
                    res = yield self.sql.runQuery("SELECT user_id FROM core_prison WHERE user_id=%s AND prisoner_id=%s", (self.arg('cid'), uid))
                    if res:
                        pid = yield self.set_release(user, self.arg('cid'), E.resist)
                        if pid:
                            yield self.sql.runQuery("DELETE FROM core_prison WHERE user_id=%s AND prisoner_id=%s RETURNING id", (self.arg('cid'), uid))
                            earn = E.earn4against(prisoner, hunt['guards'].keys(), prisoner['heros'])
                            user['gold'] += earn.get('gold', 0)
                            user['feat'] += earn.get('feat', 0)
                            cuser=dict(gold=user['gold'], feat=user['feat'])
                            yield self.redis.incr('gainsttimes:%s' % uid)
                            yield self.set_user(uid, **cuser)
                    else:
                        raise web.HTTPError(400, "Argument error")
            else:
                res = yield self.sql.runQuery("SELECT prisoner_id, status, created_at, ended_at FROM core_prison WHERE user_id=%s AND prisoner_id=%s", (self.arg('cid'), uid))
                if res:
                    cuser = yield self.get_hunt(self.arg('cid'))
                else:
                    raise web.HTTPError(400, "Argument error")
        else:
            raise web.HTTPError(400, "Argument error")

        ret = dict(user=cuser, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class ResetHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Prison gainst reset', '/prison/reset/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Prison reset")
    def get(self):
        uid = self.uid
        user = yield self.get_user(uid)
        gainstresets = yield self.redis.get('gainstresets:%s' % uid)
        if not gainstresets:
            gainstresets = 0
        if gainstresets > E.gainstmaxtimes(user['vrock']):
            self.write(dict(err=E.ERR_DISSATISFY_MAXRESETS, msg=E.errmsg(E.ERR_DISSATISFY_MAXRESETS)))
            return
        else:
            gainsttimes = 0
            yield self.redis.set('gainsttimes:%s' % uid, gainsttimes)
            huntresets = yield self.redis.incr('gainstresets:%s' % uid)
        ret = dict(gainsttimes=gainsttimes, resettimes=gainstresets, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)
