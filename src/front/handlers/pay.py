# -*- coding: utf-8 -*-

import random
import time
import zlib
import uuid
import json
import datetime
import pickle
import base64
import requests
import urllib
import urlparse
from urllib import unquote
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
    @api('Pay info', '/pay/info/', [
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        ], filters=[ps_filter], description="Pay info")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        try:
            channel = self.get_argument("channel", "putaogame")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        payrecords = {}
        channels = yield self.sql.runQuery("SELECT id FROM core_channel WHERE slug=%s LIMIT 1", (channel, ))
        if not channels:
            channels = yield self.sql.runQuery("SELECT id FROM core_channel WHERE slug=%s LIMIT 1", ("putaogame", ))
        channel_id, = channels[0]
        rockstore = yield self.get_rockstore(channel_id)
        for i in xrange(0, len(rockstore)/8):
            if self.arg('channel') == 'pt_ali':
                res = yield self.sql.runQuery("SELECT * FROM core_alipayrecord WHERE user_id=%s AND pid=%s LIMIT 1", (uid, rockstore[i*8]))
            elif self.arg('channel') == 'putaogame':
                res = yield self.sql.runQuery("SELECT created_at FROM core_payrecord WHERE user_id=%s AND pid=%s LIMIT 1", (uid, rockstore[i*8]))
            elif self.arg('channel') == 'pt_xiaomi':
                res = yield self.sql.runQuery("SELECT * FROM core_alipayrecord WHERE user_id=%s AND pid=%s LIMIT 1", (uid, rockstore[i*8]))
            elif self.arg('channel') == 'pt_letv':
                res = yield self.sql.runQuery("SELECT * FROM core_letvpayrecord WHERE user_id=%s AND pid=%s LIMIT 1", (uid, rockstore[i*8]))
            elif self.arg('channel') == 'pt_chinamobile':
                res = yield self.sql.runQuery("SELECT * FROM core_cmpayrecord WHERE user_id=%s AND pid=%s LIMIT 1", (uid, rockstore[i*8]))
            elif self.arg('channel') == 'pt_lovegame':
                res = yield self.sql.runQuery("SELECT * FROM core_lgpayrecord WHERE user_id=%s AND pid=%s LIMIT 1", (uid, rockstore[i*8]))
            elif self.arg('channel') == 'dangbei':
                res = yield self.sql.runQuery("SELECT * FROM core_dangbeipayrecord WHERE user_id=%s AND pid=%s LIMIT 1", (uid, rockstore[i*8]))
            elif self.arg('channel') == 'atet':
                res = yield self.sql.runQuery("SELECT * FROM core_atetpayrecord WHERE user_id=%s AND pid=%s LIMIT 1", (uid, rockstore[i*8]))
            else:
                res = yield self.sql.runQuery("SELECT created_at FROM core_payrecord WHERE user_id=%s AND pid=%s LIMIT 1", (uid, rockstore[i*8]))
            lefttime = '-1'
            if res:
                if rockstore[i*8+2] == 0:
                    if rockstore[i*8+3] == 1:
                        res = yield self.sql.runQuery("SELECT created_at, ended_at FROM core_card WHERE user_id=%s AND gid=%s LIMIT 1", (user['uid'], rockstore[i*8]))
                        if res:
                            created_at, ended_at = res[0]
                            t = datetime.datetime.today().date()
                            today = int(time.mktime(t.timetuple()))
                            #lefttime = (ended_at - int(time.mktime(t.timetuple())))/3600/24
                            lefttime = (ended_at - created_at)/3600/24
                            if lefttime < 0:
                                lefttime = '-1'
                            if ended_at < today:
                                lefttime = '-1'
                        payrecords[rockstore[i*8]] = lefttime

                    elif rockstore[i*8+3] == 2:
                        payrecords[rockstore[i*8]] = lefttime
                    else:

                        gid, = [rockstore[j*8] for j in xrange(0, len(rockstore)/8) if rockstore[j*8+1] == rockstore[i*8+1] and rockstore[j*8+3] == 2]
                        payrecords[gid] = lefttime
            else:
                if rockstore[i*8+2] == 0:
                    payrecords[rockstore[i*8]] = lefttime
        yield self.predis.set('payrecords:%s:%s' % (ZONE_ID, uid), pickle.dumps(payrecords))

        ret = dict(vrock=user['vrock'], goods=payrecords, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class NotifyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('pay notify', '/notify/', [
        # Param('uid', True, str, '109', '109', 'uid'),
        Param('product', True, str, '08001', '08001', 'product id'),
        Param('extra', False, str, '1', '1', 'extra'),
        Param('trans_no', True, str, '0c9a45136c4', '0c9a45136c4', 'trans_no'), 
        Param('result', True, str, 'T/F/C', 'C', 'result'),  
        Param('notify_id', True, str, '0a2311121121', '0a2311121121', 'notify_id'),  
        Param('trade_time', True, int, 1408952618, 1408952618, 'trade_time'),  
        Param('amount', True, int, 500, 500, 'amount'),  
        Param('currency', True, str, 'CNY', 'CNY', 'currency'),  
        Param('sign', True, str, '121aaac22a222bbaaa2222aaaa', '121aaac22a222bbaaa2222aaaa', 'sign'),  
        Param('sign_type', True, str, 'rsa', 'rsa', 'sign_type'), 
        ], filters=[ps_filter], description="pay notify")
    def get(self):
        #product=bltx08010&trans_no=76a6719b085a4dd7b775e3e9fb919b0f&extra=test_params&sign=IAWwxt8nKl%2Bvp7ngHd5ORrjFAmSzjYa%2Fw%2FWOi4dkHwnDPza4eRHBPXEDjqpOsWz%2BQdQdn4GbxpeTuErCXyZNsxYV8IbjEssKuYFEdib1lLZmcLnegsf%2BSlNtT6VQuuhXQqgKDOt7luxA3g5Qr53D95cWczIdoqNpaCqV3o1UxMImlg46Y2PWlgit3svfBkWRF6sZ8LkEHUtVI6be1atp9khrmk%2BNW%2BtdkSq%2FpDEFVRisdHxIwj%2FzZRpP%2F6Cdn%2BaTkwQm5t0PHyEHoxBjesyYVFrzVL%2FK2OOZxlPcrAtiC6afFErp0hyo4PgpufV1egYtMWgOYVIgjwtRew4scZUOMw%3D%3D&currency=CNY&amount=1&trade_time=1429005943&result=T&sign_type=rsa&notify_id=cc658fd3dc3e4725a9f430b24120b919
        try:
            # uid = self.get_argument("uid")
            product = self.get_argument("product")
            extra = self.get_argument("extra")
            trans_no = self.get_argument("trans_no")
            result = self.get_argument("result")
            trade_time = self.get_argument("trade_time")
            amount = self.get_argument("amount")
            currency = self.get_argument("currency")
            sign = self.get_argument("sign")
            sign_type = self.get_argument("sign_type")

        except Exception:
            raise web.HTTPError(400, "Argument error")
        channels = yield self.sql.runQuery("SELECT id FROM core_channel WHERE slug=%s LIMIT 1", ('putaogame', ))
        if not channels:
            raise web.HTTPError(400, "Argument error")
        else:
            channel_id, = channels[0]
        rockstore = yield self.get_rockstore(channel_id)
        params = self.request.arguments.copy()
        params.pop('sign')
        params.pop('sign_type')
        for x, y in params.items():
            params[x] = y[0]
        params = yield self.format_params(params, False)
        verify = yield self.verify_sign(params, sign)
        if not verify:
            raise web.HTTPError(400, "Argument error")
        product, uid = extra.split(',')
        user = yield self.get_user(uid)
        res = yield self.sql.runQuery("SELECT * FROM core_payrecord WHERE user_id=%s AND pid=%s AND trans_no=%s AND result=%s AND trade_time=%s AND amount=%s AND currency=%s LIMIT 1", (uid, product, trans_no, 'T', trade_time, amount, currency))
        if res:
            self.write('success')
        else:
            yield self.set_payrecord(uid, product, trans_no, result, trade_time, amount, currency)    
            payrecords = yield self.predis.get('payrecords:%s:%s' % (ZONE_ID, uid)) 
            if payrecords and result == 'T':
                payrecords = pickle.loads(payrecords)
                if product in payrecords:
                    is_first = 0
                    pos, = [i for i in xrange(0, len(rockstore)/8) if rockstore[i*8] == product]

                    if rockstore[pos*8+2] == 0:
                        if rockstore[pos*8+3] == 1:
                            #card
                            lefttime, is_first = yield self.set_card(user, rockstore[pos*8])
                            if lefttime:
                                payrecords[rockstore[pos*8]] = lefttime
                            if is_first:
                                user['works']['01007'] = {"_": 1, "tags": {"CARD": [1, 1]}}

                        elif rockstore[pos*8+3] == 3:
                            gid, = [rockstore[i*8] for i in xrange(0, len(rockstore)/8) if rockstore[i*8+1] == rockstore[pos*8+1] and rockstore[i*8+3] == 2]
                            del payrecords[product]
                            payrecords[gid] = '-1'

                        else:pass
                    else:pass

                    user['vrock'] += rockstore[pos*8+4]
                    user['rock'] += rockstore[pos*8+4]
                    user['rock'] += rockstore[pos*8+5]
                    if is_first:
                        cuser = dict(rock=user['rock'], vrock=user['vrock'], works=user['works'])
                    else:
                        cuser = dict(rock=user['rock'], vrock=user['vrock'])
                    logmsg = u'充值(葡萄):购买%s(notify)' % product
                    yield self.set_user(uid, logmsg, **cuser)
                    yield self.set_inpour(user, rockstore[pos*8+4])
                    yield self.predis.set('payrecords:%s:%s' % (ZONE_ID, uid), pickle.dumps(payrecords))
                yield self.update_payrecord(user, rockstore)       
                self.write('success')

@handler
class VerifyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('pay verify', '/verify/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('product', True, str, '08001', '08001', 'product id'),
        Param('app_order_id', False, str, '69b9d245544542f8923039ea0ffce61a', '69b9d245544542f8923039ea0ffce61a', 'app_order_id'),
        ], filters=[ps_filter], description="pay notify")
    def post(self):
        try:
            product = self.get_argument("product")
            trans_no = self.get_argument("app_order_id", "")
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        channels = yield self.sql.runQuery("SELECT id FROM core_channel WHERE slug=%s LIMIT 1", (self.arg('channel'), ))
        if not channels:
            channels = yield self.sql.runQuery("SELECT id FROM core_channel WHERE slug=%s LIMIT 1", ("putaogame", ))
        channel_id, = channels[0]
        rockstore = yield self.get_rockstore(channel_id)
        if self.arg('channel') == 'pt_ali':
            res = yield self.sql.runQuery("SELECT * FROM core_alipayrecord WHERE user_id=%s AND pid=%s AND app_order_id=%s LIMIT 1",\
             (uid, product, self.arg('app_order_id')))
            if not res:
                raise web.HTTPError(404)
        elif self.arg('channel') == 'pt_xiaomi':
            res = yield self.sql.runQuery("SELECT * FROM core_xmpayrecord WHERE user_id=%s AND pid=%s AND app_order_id=%s LIMIT 1",\
             (uid, product, self.arg('app_order_id')))
            if not res:
                raise web.HTTPError(404)
        elif self.arg('channel') == 'pt_chinamobile':
            res = yield self.sql.runQuery("SELECT * FROM core_cmpayrecord WHERE user_id=%s AND pid=%s AND app_order_id=%s LIMIT 1",\
             (uid, product, self.arg('app_order_id')))
            if not res:
                raise web.HTTPError(404)
        elif self.arg('channel') == 'pt_letv':
            res = yield self.sql.runQuery("SELECT * FROM core_letvpayrecord WHERE user_id=%s AND pid=%s AND app_order_id=%s LIMIT 1",\
             (uid, product, self.arg('app_order_id')))
            if not res:
                raise web.HTTPError(404)

        elif self.arg('channel') == 'pt_lovegame':
            res = yield self.sql.runQuery("SELECT * FROM core_lgpayrecord WHERE user_id=%s AND pid=%s AND app_order_id=%s LIMIT 1",\
             (uid, product, self.arg('app_order_id')))
            if not res:
                raise web.HTTPError(404)

        elif self.arg('channel') == 'dangbei':
            res = yield self.sql.runQuery("SELECT * FROM core_dangbeipayrecord WHERE user_id=%s AND pid=%s AND app_order_id=%s LIMIT 1",\
             (uid, product, self.arg('app_order_id')))
            if not res:
                raise web.HTTPError(404)
        elif self.arg('channel') == 'atet':
            res = yield self.sql.runQuery("SELECT * FROM core_atetpayrecord WHERE user_id=%s AND pid=%s AND app_order_id=%s LIMIT 1",\
             (uid, product, self.arg('app_order_id')))
            if not res:
                raise web.HTTPError(404)
        else:
            res = yield self.sql.runQuery("SELECT * FROM core_payrecord WHERE user_id=%s AND pid=%s AND result=%s AND trans_no=%s LIMIT 1", (uid, product, 'T', trans_no))
            if not res:
                data = dict(app="com.putao.PtSanguo", receipt=trans_no)
                params = yield self.format_params(data, False)
                sign =  yield self.create_sign(params)
                data['sign'] = sign
                try:
                    response = requests.get("https://play.putaogame.com/api/v1/notify/query?{}".format(urllib.urlencode(data)))
                    assert response.status_code == 200
                except Exception:
                    raise web.HTTPError(404)
                content = urlparse.parse_qs(unquote(response.content), True)
                try:
                    extra, = content['extra']
                    product, uuid = extra.split(',')
                    trans_no, = content['trans_no']
                    result, = content['result']
                    trade_time, = content['trade_time']
                    amount, = content['amount']
                    currency, = content['currency']
                    try:
                        assert int(uuid) == int(uid)
                    except Exception:
                        raise web.HTTPError(404)
                    # payrecords = {}
                    res = yield self.sql.runQuery("SELECT * FROM core_payrecord WHERE user_id=%s AND pid=%s AND trans_no=%s AND result=%s AND trade_time=%s AND amount=%s AND currency=%s LIMIT 1",\
                     (uid, product, trans_no, 'T', trade_time, amount, currency))
                    if not res:
                        yield self.set_payrecord(uid, product, trans_no, result, trade_time, amount, currency)    
                        payrecords = yield self.predis.get('payrecords:%s:%s' % (ZONE_ID, uid)) 
                        if payrecords and result == 'T':
                            payrecords = pickle.loads(payrecords)
                            if product in payrecords:
                                is_first = 0
                                pos, = [i for i in xrange(0, len(rockstore)/8) if rockstore[i*8] == product]

                                if rockstore[pos*8+2] == 0:
                                    if rockstore[pos*8+3] == 1:
                                        #card
                                        lefttime, is_first = yield self.set_card(user, rockstore[pos*8])
                                        if lefttime:
                                            payrecords[rockstore[pos*8]] = lefttime
                                        if is_first:
                                            user['works']['01007'] = {"_": 1, "tags": {"CARD": [1, 1]}}

                                    elif rockstore[pos*8+3] == 3:
                                        gid, = [rockstore[i*8] for i in xrange(0, len(rockstore)/8) if rockstore[i*8+1] == rockstore[pos*8+1] and rockstore[i*8+3] == 2]
                                        del payrecords[product]
                                        payrecords[gid] = '-1'

                                    else:pass
                                else:pass

                                user['vrock'] += rockstore[pos*8+4]
                                user['rock'] += rockstore[pos*8+4]
                                user['rock'] += rockstore[pos*8+5]
                                if is_first:
                                    cuser = dict(rock=user['rock'], vrock=user['vrock'], works=user['works'])
                                else:
                                    cuser = dict(rock=user['rock'], vrock=user['vrock'])
                                logmsg = u'充值:购买%s(verify)' % product
                                user = yield self.set_user(uid, logmsg, **cuser)
                                yield self.set_inpour(user, rockstore[pos*8+4])
                                yield self.predis.set('payrecords:%s:%s' % (ZONE_ID, uid), pickle.dumps(payrecords))
                        yield self.update_payrecord(user, rockstore)     
                except Exception:
                    raise web.HTTPError(404)
        #dayrecharge = yield self.get_dayrecharge(user, self.arg('channel'))
        inpour = yield self.get_inpour(user)
        cuser = dict(rock=user['rock'], vrock=user['vrock'], works=user['works'], inpour=inpour)
        ret = dict(out=dict(user=cuser), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)  
