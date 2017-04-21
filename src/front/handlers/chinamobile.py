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
from xml.dom import minidom 
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
from local_settings import *

@handler
class OrderHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Pay order', '/cmpay/order/', [
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
        #order_id = uuid.uuid4().hex
        query = "INSERT INTO core_cmorder(channel_id, app_order_id, user_id, pid, amount, timestamp) VALUES (%s, %s, %s, %s, %s, %s) RETURNING app_order_id"
        params = (channel, uuid.uuid4().hex[:13], uid, pid, amount, int(time.time()))
        for i in range(5):
            try:
                res = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        if res:
            orderId, = res[0]
            ret = dict(orderId=orderId, timestamp=int(time.time()))
            reb = zlib.compress(escape.json_encode(ret))
            self.write(ret)
        else:
            raise web.HTTPError(500)

@handler
class NotifyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('pay notify', '/cmpay/notify/', [  
        ], filters=[ps_filter], description="pay notify")
    def get(self):
        try:
            orderId = self.get_argument("orderId")
            contentId = self.get_argument("contentId")
            consumeCode = self.get_argument("consumeCode")
            cpid = self.get_argument("cpid")  
            hRet = self.get_argument("hRet")      
        except Exception:
            raise web.HTTPError(400, "Argument error")
        channels = yield self.sql.runQuery("SELECT id FROM core_channel WHERE slug=%s LIMIT 1", ("pt_chinamobile", ))
        if not channels:
            raise web.HTTPError(400, "Argument error")
        else:
            channel_id, = channels[0]
        rockstore = yield self.get_rockstore(channel_id)
        res = yield self.sql.runQuery("SELECT user_id, pid, amount FROM core_cmorder WHERE app_order_id=%s", (orderId, ))
        if res:
            uid, product, amount = res[0]
            user = yield self.get_user(uid)
            rec = yield self.sql.runQuery("SELECT * FROM core_cmpayrecord WHERE user_id=%s AND app_order_id=%s LIMIT 1", (uid, orderId))
            if not rec:
                yield self.set_cmpayrecord(uid, product, amount, orderId, contentId, consumeCode, cpid, hRet)    
                payrecords = yield self.predis.get('payrecords:%s:%s' % (ZONE_ID, uid)) 
                if payrecords and hRet == '0':
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
                        logmsg = u'充值(移动):购买%s' % product
                        yield self.set_user(uid, logmsg, **cuser)
                        yield self.set_inpour(user, rockstore[pos*8+4])
                        yield self.predis.set('payrecords:%s:%s' % (ZONE_ID, uid), pickle.dumps(payrecords))
                yield self.update_cmpayrecord(user, rockstore)                

            
