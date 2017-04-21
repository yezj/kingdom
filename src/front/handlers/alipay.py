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
import hashlib  
from urllib import unquote
from twisted.internet import defer
from cyclone import escape, web
from twisted.python import log
from front import storage
from front import utils
from front.utils import E
from front.wiapi import *
from front import D
from front.handlers.base import ApiHandler, ApiJSONEncoder
from local_settings import ZONE_ID

@handler
class OrderHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Pay order', '/alipay/order/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        Param('pid', True, str, '08001', '08001', 'product id'),
        Param('amount', True, int, 500, 500, 'amount'),  
        ], filters=[ps_filter], description="Pay order")
    def post(self):
        try:
            channel = self.get_argument("channel")
            pid = self.get_argument("pid")
            amount = self.get_argument("amount")   
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        channels = yield self.sql.runQuery("SELECT id FROM core_channel WHERE slug=%s LIMIT 1", (channel, ))
        if channels:
            channel, = channels[0]
        else:
            raise web.HTTPError(404)

        user = yield self.get_user(uid)
        if not user:
            raise web.HTTPError(400, "Argument error")
        #app_order_id = uuid.uuid4().hex
        query = "INSERT INTO core_aliorder(channel_id, app_order_id, user_id, pid, amount, timestamp) VALUES (%s, %s, %s, %s, %s, %s) RETURNING app_order_id"
        params = (channel, uuid.uuid4().hex, uid, pid, amount, int(time.time()))
        for i in range(5):
            try:
                res = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        if res:
            app_order_id, = res[0]
            ret = dict(app_order_id=app_order_id, timestamp=int(time.time()))
            reb = zlib.compress(escape.json_encode(ret))
            self.write(ret)
        else:
            raise web.HTTPError(500)

@handler
class NotifyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('pay notify', '/alipay/notify/', [
        Param('app_order_id', True, str, '0c9a45136c4', '0c9a45136c4', 'app_order_id'), 
        Param('coin_order_id', True, str, '0c9a45136c4', '0c9a45136c4', 'coin_order_id'), 
        Param('consume_amount', True, int, 500, 500, 'consume_amount'),  
        Param('credit_amount', False, int, 500, 500, 'credit_amount'), 
        Param('ts', True, int, 1408952618, 1408952618, 'ts'), 
        Param('is_success', True, str, 'T/F', 'T', 'is_success'),   
        Param('error_code', False, str, '0', '0', 'error_code'), 
        Param('sign', True, str, '121aaac22a222bbaaa2222aaaa', '121aaac22a222bbaaa2222aaaa', 'sign'),   
        ], filters=[ps_filter], description="pay notify")
    def get(self):
        try:
            app_order_id = self.get_argument("app_order_id")
            coin_order_id = self.get_argument("coin_order_id")
            consume_amount = self.get_argument("consume_amount")
            credit_amount = self.get_argument("credit_amount", 0)
            ts = self.get_argument("ts")
            is_success = self.get_argument("is_success")
            error_code = self.get_argument("error_code", 0)
            sign = self.get_argument("sign")            
        except Exception:
            raise web.HTTPError(400, "Argument error")
        channels = yield self.sql.runQuery("SELECT id FROM core_channel WHERE slug=%s LIMIT 1", ("pt_ali", ))
        if not channels:
            raise web.HTTPError(400, "Argument error")
        else:
            channel_id, = channels[0]
        rockstore = yield self.get_rockstore(channel_id)
        params = self.request.arguments.copy()
        params.pop('sign')
        for x, y in params.items():
            params[x] = y[0]
        params = yield self.format_params(params, False)
        m = hashlib.md5()   
        m.update(params) 
        _sign = m.hexdigest()  
        if sign != _sign :
            res = yield self.sql.runQuery("SELECT user_id, pid FROM core_aliorder WHERE app_order_id=%s", (app_order_id, ))
            if res:
                uid, product = res[0]
                user = yield self.get_user(uid)
                yield self.set_alipayrecord(uid, product, app_order_id, coin_order_id, consume_amount, credit_amount, ts,\
                 is_success, error_code, sign)    
                payrecords = yield self.predis.get('payrecords:%s:%s' % (ZONE_ID, uid)) 
                if payrecords and is_success == 'T':
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
                        logmsg = u'充值(阿里):购买%s' % product
                        yield self.set_user(uid, logmsg, **cuser)
                        yield self.set_inpour(user, rockstore[pos*8+4])
                        yield self.predis.set('payrecords:%s:%s' % (ZONE_ID, uid), pickle.dumps(payrecords))
                yield self.update_alipayrecord(user, rockstore)                
            else:
                pass
            ret = dict(is_success='T', app_order_id=app_order_id, coin_order_id=coin_order_id)
        else:
            ret = dict(is_success='F', app_order_id=app_order_id, coin_order_id=coin_order_id, error_code=E.ERR_SIGN,\
             Msg=E.errmsg(E.ERR_SIGN))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

            
