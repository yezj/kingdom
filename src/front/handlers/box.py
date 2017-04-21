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
class BuyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Soulbox buy', '/box/buy/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Soulbox buy")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        weekday = datetime.date.today().weekday()
        res = yield self.sql.runQuery("SELECT proba, rock, gold, feat, prods, nums FROM core_soulproba WHERE week=%s LIMIT 1", (weekday, ))
        if res:
            proba, rock, gold, feat, prod, nums = res[0]
            #print 'prod', prod
            #print len(proba.strip().split(','))
            prods = dict(zip(prod.strip().split(','), nums.strip().split(',')))
        else:
            raise web.HTTPError(400, "Argument error")
        boxbuytimes = yield self.predis.get('boxbuytimes:%s:%s' % (ZONE_ID, uid))
        if not boxbuytimes:
            boxbuytimes = 0
            yield self.predis.set('boxbuytimes:%s:%s' % (ZONE_ID, uid), boxbuytimes)
        boxgroup = yield self.predis.get('boxgroup:%s:%s' % (ZONE_ID, uid))
        if not boxgroup:
            boxgroup = random.randint(0, len(proba.strip().split(','))/100-1)
            yield self.predis.set('boxgroup:%s:%s' % (ZONE_ID, uid), boxgroup)

        #print 'boxbuytimes', boxbuytimes, weekday
        #boxbuytimes = boxbuytimes % len(proba.strip().split(','))
        #print 'buytimes', buytimes, len(prod.strip().split(',')), prod.strip().split(',')
        proba_list = proba.strip().split(',')
        #print boxbuytimes, proba_list[boxbuytimes], weekday, proba_list[boxgroup*100+boxbuytimes]
        if proba_list[boxbuytimes] == 'random':
            res = yield self.sql.runQuery("SELECT prod, proba FROM core_soulbox WHERE week=%s", (weekday, ))
            if res:
                prod = self.random_pick(res)
                res = yield self.sql.runQuery("SELECT prod, num FROM core_soulbox WHERE week=%s AND prod=%s", (weekday, prod))
                if res:
                    prod, num = res[0]
                    pid = prod.zfill(5)
            else:
                raise web.HTTPError(400, "Argument error")
        else:
            res = yield self.sql.runQuery("SELECT prod, num FROM core_soulbox WHERE week=%s AND prod=%s", (weekday, proba_list[boxgroup*100+boxbuytimes]))
            if res:
                prod, num = res[0]
                pid = prod.zfill(5)
        if len(pid):
            prods[pid] = num
        if user['rock'] < rock:
            self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
            return
        user['rock'] -= rock
        consume = yield self.set_consume(user, rock)
        user['gold'] += gold
        user['feat'] += feat
        for pid, num in prods.items():
            if pid in user['prods']:
                user['prods'][pid] += int(num)
            else:
                user['prods'][pid] = int(num)
            if user['prods'][pid] > 9999:
                user['prods'][pid] = 9999
        #print 'boxgroup is %s, boxbuytimes is %s' % (boxgroup, boxbuytimes)
        #print 'prods', prods
        awards = dict(prods=prods, gold=gold, feat=feat)
        cuser = dict(prods=user['prods'], rock=user['rock'], gold=user['gold'], feat=user['feat'])
        cwork = E.tagworks(user, {'CALL': 1})
        if cwork:
            cuser['works'] = user['works']
        logmsg = u'魂匣:购买 (%s组%s次)' % (boxgroup, boxbuytimes)
        yield self.set_user(uid, logmsg, **cuser)
        consume = yield self.get_consume(user)
        cuser['consume'] = consume
        if boxbuytimes + 1 == 100:
            boxgroup = random.randint(0, len(proba.strip().split(','))/100-1)
            yield self.predis.set('boxgroup:%s:%s' % (ZONE_ID, uid), boxgroup)
            yield self.predis.set('boxbuytimes:%s:%s' % (ZONE_ID, uid), 0)
        else:
            yield self.predis.incr('boxbuytimes:%s:%s' % (ZONE_ID, uid))
        ret = dict(out=dict(awards=awards), user=cuser, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

