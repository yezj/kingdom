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

@handler
class InfoHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('seckill info', '/seckill/info/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="seckill info")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        groups = {}
        for i in xrange(1, 4):
            res = yield self.sql.runQuery("SELECT index, groups, prod, num, gold, rock, total FROM core_seckill WHERE groups=%s", (i, ))
            prods = []
            if res:
                for r in res:
                    index, group, prod, num, gold, rock, total = r
                    buy = yield self.redis.get('seckill:%s:%s' % (group, prod))
                    if not buy:
                        buy = 0 
                    left = int(total) - int(buy)
                    if left < 0:
                        left = 0 
                    prods.append(dict(index=index, group=group, prod=prod, num=num, left=left, gold=gold, rock=rock, total=total))
            groups[i] = dict(prods=prods)
        res = yield self.sql.runQuery("SELECT created_at, ended_at from core_seckilltime")
        if res:
            created_at, ended_at = res[0]
            created_at = int(time.mktime(created_at.timetuple()))
            ended_at = int(time.mktime(ended_at.timetuple()))
        else:
            raise web.HTTPError(400, "Argument error")
        ret = dict(out=dict(groups=groups, created_at=created_at, ended_at=ended_at), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)


@handler
class BuyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Seckill buy', '/seckill/buy/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        Param('group', True, str, '1', '1', 'group'),
        Param('pid', True, str, '01030', '01030', 'pid'),
        ], filters=[ps_filter], description="Seckill buy")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        try:
            group = self.get_argument("group")
            pid = self.get_argument("pid")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        res = yield self.sql.runQuery("SELECT index, groups, prod, num, gold, rock, total FROM core_seckill WHERE groups=%s AND prod=%s", (group, pid))
        if res:
            index, groups, prod, num, gold, rock, total = res[0]
            seckill = yield self.redis.get('seckill:%s:%s' % (group, pid))
            is_buy = yield self.redis.get('seckill:%s:%s:%s' % (group, pid, uid))
            if is_buy:
                self.write(dict(err=E.ERR_SECKILL_REPEAT, msg=E.errmsg(E.ERR_SECKILL_REPEAT)))
                return 
            if seckill < int(total):
                if user['rock'] < rock:
                    self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
                    return 
                if user['gold'] < gold:
                    self.write(dict(err=E.ERR_NOTENOUGH_GOLD, msg=E.errmsg(E.ERR_NOTENOUGH_GOLD)))
                    return

                user['rock'] -= int(rock)
                yield self.set_consume(user, int(rock))
                #print 'rock', rock
                user['gold'] -= int(gold)
                if pid in user['prods']:
                    user['prods'][pid] += int(num)
                else:
                    user['prods'][pid] = int(num)
                if user['prods'][pid] > 9999:
                    user['prods'][pid] = 9999
                cuser = dict(prods=user['prods'], gold=user['gold'], rock=user['rock'])
                logmsg = u'秒杀:购买组%s的%s' % (group, pid)
                yield self.set_user(uid, logmsg, **cuser)
                yield self.redis.incr('seckill:%s:%s' % (group, pid))
                yield self.redis.set('seckill:%s:%s:%s' % (group, pid, uid), E.true)
                prods = []
                res = yield self.sql.runQuery("SELECT index, groups, prod, num, gold, rock, total FROM core_seckill WHERE groups=%s", (group, ))
                for r in res:
                    index, group, prod, num, gold, rock, total = r
                    buy = yield self.redis.get('seckill:%s:%s' % (group, prod))
                    if not buy:
                        buy = 0 
                    left = int(total) - int(buy)
                    if left < 0:
                        left = 0 
                    prods.append(dict(index=index, group=group, prod=prod, num=num, left=left, gold=gold, rock=rock, total=total))
                consume = yield self.get_consume(user)
                cuser['consume'] = consume
                ret = dict(out=dict(user=cuser, prods=prods), timestamp=int(time.time()))
                reb = zlib.compress(escape.json_encode(ret))
                self.write(ret)
            else:
                self.write(dict(err=E.ERR_SECKILL_OVER, msg=E.errmsg(E.ERR_SECKILL_OVER)))
                return 
        else:
            self.write(dict(err=E.ERR_SECKILL_NOTFOUND, msg=E.errmsg(E.ERR_SECKILL_NOTFOUND)))
            return