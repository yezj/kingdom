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
    @api('Pay order', '/lgpay/order/', [
        Param('channel', False, str, 'pt_lovegame', 'pt_lovegame', 'channel'),
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

        app_order_id = uuid.uuid4().hex[:10] + str(ZONE_ID)
        query = "INSERT INTO core_lgorder(channel_id, app_order_id, user_id, pid, amount, timestamp) VALUES (%s, %s, %s, %s, %s, %s) RETURNING app_order_id"
        params = (channel, app_order_id, uid, pid, amount, int(time.time()))
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
    @api('pay notify', '/lgpay/notify/', [
        Param('serial_no', True, str, '9786bffc-996d-4553-aa33-f7e92c0b29d5', '9786bffc-996d-4553-aa33-f7e92c0b29d5', 'serial_no'), 
        Param('transaction_id', True, str, '9786bffc-996d-4553-aa33-f7e92c0b29d5', '9786bffc-996d-4553-aa33-f7e92c0b29d5', 'transaction_id'), 
        Param('fee', True, int, 1, 1, 'fee'),   
        ], filters=[ps_filter], description="pay notify")
    def get(self):
        try:
            serial_no = self.get_argument("serial_no")
            transaction_id = self.get_argument("transaction_id")
            fee = self.get_argument("fee")          
        except Exception:
            raise web.HTTPError(400, "Argument error")
        channels = yield self.sql.runQuery("SELECT id FROM core_channel WHERE slug=%s LIMIT 1", ("pt_lovegame", ))
        if not channels:
            raise web.HTTPError(400, "Argument error")
        else:
            channel_id, = channels[0]
        rockstore = yield self.get_rockstore(channel_id)
        res = yield self.sql.runQuery("SELECT user_id, pid FROM core_lgorder WHERE app_order_id=%s", (serial_no, ))
        if res:
            uid, product = res[0]
            user = yield self.get_user(uid)
            rec = yield self.sql.runQuery("SELECT * FROM core_lgpayrecord WHERE user_id=%s AND app_order_id=%s LIMIT 1", (uid, serial_no))
            if not rec:
                yield self.set_lgpayrecord(uid, product, serial_no, transaction_id, fee)    
                payrecords = yield self.predis.get('payrecords:%s:%s' % (ZONE_ID, uid)) 
                if payrecords:
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
                        logmsg = u'充值(爱游戏):购买%s' % product
                        yield self.set_user(uid, logmsg, **cuser)
                        yield self.set_inpour(user, rockstore[pos*8+4])
                        yield self.predis.set('payrecords:%s:%s' % (ZONE_ID, uid), pickle.dumps(payrecords))
                yield self.update_lgpayrecord(user, rockstore)                


            
