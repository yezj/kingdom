# -*- coding: utf-8 -*-

import random
import time
import zlib
import uuid
import json
import datetime
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
    @api('Lott info', '/lott/info/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Get loff info")
    def post(self):
        lott = D.LOTT
        uid = self.uid
        user = yield self.get_user(uid)
        lott = yield self.update_lott(user)
        box = yield self.get_soulbox(uid)
        ret = dict(lott=lott, box=box, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class GetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Lott get', '/lott/get/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('type', True, str, '1', '1', 'type'),
        Param('times', True, str, '1', '1', 'times'),
        ], filters=[ps_filter], description="Get lott result")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        lott = yield self.update_lott(user)
        cuser = {}
        awards = {}
        if self.has_arg('type') and self.has_arg('times'):
            cost = E.cost4lott(int(self.arg('type')), self.arg('times'))
            times = int(self.arg('times'))
            daylotts = yield self.redis.get('daylott:%s:%s' % (uid, self.arg('type')))
            if not daylotts:
                daylotts = 1
            try:
                assert int(times) == 1 or int(times) == 10
            except Exception:
                self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
                return
            if cost:
                if times == 1:
                    if int(self.arg('type')) == E.lott_by_gold:
                        lottfree = yield self.redis.get('lottfree:%s:%s' % (uid, E.lott_by_gold))
                        if lottfree == str(False):
                            if user['gold'] < cost.get('gold', 0):
                                self.write(dict(err=E.ERR_NOTENOUGH_GOLD, msg=E.errmsg(E.ERR_NOTENOUGH_GOLD)))
                                return
                            user['gold'] -= cost.get('gold', 0)
                            user['feat'] += 150
                            cuser['gold'] = user['gold']
                            cuser['feat'] = user['feat']
                        else:
                            times = 1
                            user['feat'] += 150
                            cuser['feat'] = user['feat']
                            yield self.redis.set('lottfree:%s:%s' % (uid, E.lott_by_gold), False)
                            yield self.redis.incr('freetimes:%s:%s' % (uid, E.lott_by_gold))
                            yield self.update_freelott(False, user, E.lott_by_gold)

                    elif int(self.arg('type')) == E.lott_by_rock:
                        lottfree = yield self.redis.get('lottfree:%s:%s' % (uid, E.lott_by_rock))
                        if lottfree == str(False):
                            if user['rock'] < cost.get('rock', 0):
                                self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
                                return
                            user['rock'] -= cost.get('rock', 0)
                            consume = yield self.set_consume(user, cost.get('rock', 0))
                            user['feat'] += 1500
                            cuser['feat'] = user['feat']
                            cuser['rock'] = user['rock']
                        else:
                            times = 1
                            user['feat'] += 1500
                            cuser['feat'] = user['feat']
                            yield self.redis.set('lottfree:%s:%s' % (uid, E.lott_by_rock), False)
                            yield self.update_freelott(False, user, E.lott_by_rock)
                    else:
                        raise web.HTTPError(400, "Argument error")
                    daylotts = yield self.redis.incr('daylott:%s:%s' % (uid, self.arg('type')))
                    if daylotts > 30:
                        daylotts = 30
                else:
                    if int(self.arg('type')) == E.lott_by_gold:
                        if user['gold'] < cost.get('gold', 0):
                            self.write(dict(err=E.ERR_NOTENOUGH_GOLD, msg=E.errmsg(E.ERR_NOTENOUGH_GOLD)))
                            return
                        user['gold'] -= cost.get('gold', 0)
                        user['feat'] += 1500
                        cuser['feat'] = user['feat']
                        cuser['gold'] = user['gold']

                    elif int(self.arg('type')) == E.lott_by_rock:
                        if user['rock'] < cost.get('rock', 0):
                            self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
                            return
                        user['rock'] -= cost.get('rock', 0)
                        consume = yield self.set_consume(user, cost.get('rock', 0))
                        user['feat'] += 15000
                        cuser['feat'] = user['feat']
                        cuser['rock'] = user['rock']

                    else:
                        raise web.HTTPError(400, "Argument error")
        
                    yield self.redis.set('daylott:%s:%s' % (uid, self.arg('type')), daylotts+times)
            firstlott = yield self.set_firstlott(user, int(self.arg('type')))
            prodproba, prodreward = yield self.get_prodproba()
            first_by_rock = user['first_by_rock']
            if firstlott and int(self.arg('type')) == E.lott_by_rock and int(times) == 1:
                awards = [D.LOTT_BY_FIRST]
                first_by_rock = 1
            elif firstlott and int(self.arg('type')) == E.lott_by_rock and int(times) == 10:
                awards =  E.random_prod(self.arg('type'), daylotts, int(times)-1, prodproba, prodreward)
                awards.append(D.LOTT_BY_FIRST)
                first_by_rock = 1
            elif firstlott and int(self.arg('type')) == E.lott_by_gold and int(times) == 1:
                awards = [D.LOTT_BY_GOLD_FIRST]
                first_by_rock = 1
            elif firstlott and int(self.arg('type')) == E.lott_by_gold and int(times) == 10:
                awards =  E.random_prod(self.arg('type'), daylotts, int(times)-1, prodproba, prodreward)
                awards.append(D.LOTT_BY_GOLD_FIRST)
                first_by_rock = 1            
            else:
                awards =  E.random_prod(self.arg('type'), daylotts, times, prodproba, prodreward)
            #print 'awards', awards
            #awards = [{'03021': 3}, {'03010': 3}, {'03025': 80}, {'03009': 10}, {'02011': 2}, {'03020': 8}, {'03011': 3}, {'03008': 3}, {'03025': 80}, {'03009': 10}]
            for award in awards:
                for p, n in award.items():
                    award['cate'] = 0
                    for x, y in D.HERORECRUIT.items():
                        if x in user['heros'] and p in y[0]['prods']:
                            if n >= y[0]['prods'][p]:
                                n = D.HEROTRANS[n]
                                award[p] = n
                                award['cate'] = 1
                        if x not in user['heros'] and p in y[0]['prods']:
                            if n in D.HEROTRANS:
                                trans = yield self.redis.get('trans:%s:%s' % (uid, p))
                                if trans == 1:
                                    n = D.HEROTRANS[n]
                                    award[p] = n
                                yield self.redis.set('trans:%s:%s' % (uid, p), E.true)
                                    
                    if p in D.STORMPROD and n > int(D.STORMPROD[p]['num']):
                        yield self.redis.rpush("message", pickle.dumps([D.LOTTMESSAGE[0] % (user['nickname'], D.STORMPROD[p]['name']), D.LOTTMESSAGE[1] % int(time.time())]))
                    if p in user['prods']:
                        user['prods'][p] += int(n)
                    else:
                        user['prods'][p] = int(n)
                    if user['prods'][p] > 9999:
                        user['prods'][p] = 9999

            for award in awards:
                for p, n in award.items():
                    yield self.redis.delete('trans:%s:%s' % (uid, p))

            cuser['prods'] = user['prods']
            cwork = E.tagworks(user, {'CALL': int(times)})
            if cwork:
                cuser['works'] = user['works']
            if self.arg('type') == '1':
                logtype = u'金币抽奖'
            elif self.arg('type') == '2':
                logtype = u'钻石抽奖'
            logmsg = u'抽奖:%s(%s次)' % (logtype, times)
            yield self.set_user(uid, logmsg, **cuser)
            consume = yield self.get_consume(user)
            cuser['consume'] = consume
            cuser['first_by_rock'] = first_by_rock
            times = yield self.update_daylott(user)

        else:
            raise web.HTTPError(400, "Argument error")        
        ret = dict(user=cuser, awards=awards, lott=lott, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)
