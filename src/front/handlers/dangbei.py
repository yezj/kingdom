# -*- coding: utf-8 -*-

import time
import datetime
import uuid
# import cPickle as pickle
import pickle
import json
import hashlib
from urllib import unquote

from twisted.internet import defer
from cyclone import web
from twisted.python import log

from front import storage
from front import utils
from front.wiapi import handler, api, Param
from front.handlers.base import ApiHandler
from local_settings import ZONE_ID

PRODUCT_SEQUENCE_FIRST = 0
PRODUCT_SEQUENCE_SECOND = 1

PRODUCT_TYPE_CARD = 1
PRODUCT_TYPE_UNLIMIT = 2
PRODUCT_TYPE_LIMIT = 3

DANGBEI_APP_KEY = 'eb9c7d9c667c1690ddf180a7a8c0036c'
DANGBEI_MAGIC = 'sign_85445221145'


@handler
class OrderHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api(
        'Dangbei pay order', '/dangbei/order/', [
            Param('channel', required=False, param_type=str, default='dangbei', example='', description='channel'),
            Param('_sign', required=True, param_type=str, example='4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', description='_sign'),
            Param('pid', required=True, param_type=str, example='08001', description='product id'),
            Param('amount', required=True, param_type=int, example=500, description='amount'),
        ], description="Pay order")
    def post(self):
        try:
            channel = self.get_argument("channel")
            pid = self.get_argument("pid")
            amount = self.get_argument("amount")
            self.get_argument("_sign")
        except Exception:
            raise web.HTTPError(400, "Argument error")

        channel = yield self.get_channel_id(channel)

        uid = self.uid
        user = yield self.get_user(uid)
        if not user:
            raise web.HTTPError(400, "Argument error")

        # 创建订单
        query = """
        INSERT INTO core_dangbeiorder(channel_id, app_order_id, user_id, pid, amount, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING app_order_id
        """
        for i in range(5):
            try:
                app_order_id = uuid.uuid4().hex[:10] + str(ZONE_ID)
                params = (channel, app_order_id, uid, pid, amount, int(time.time()))
                res = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error: dangbei_order retry(%i): %s" % (i, (query % params)))
                continue

        if res:
            app_order_id, = res[0]
            ret = dict(app_order_id=app_order_id, timestamp=params[5])
            self.write(ret)


@handler
class NotifyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api(
        'Dangbei pay notify', '/dangbei/notify/', [
            Param('datastr', True, str, example='', description='datastr'),
            Param('sign', True, str, example='', description='sign'),
        ], description="Dangbei payment notify")
    def get(self):
        try:
            pay_info = json.loads(unquote(self.get_argument("datastr")))
            pay_info['Total_fee'] = int(float(pay_info['Total_fee']) * 100)
            sign = self.get_argument("sign")
            app_order_id = pay_info['extra'].split("&")[0]
        except Exception:
            raise web.HTTPError(400, "Argument error")

        if pay_info['start'] != 'success':
            return

        self.ensure_sign(pay_info, sign)

        # 1. 订单不存在，忽略当前请求
        res = yield self.sql.runQuery("SELECT user_id, pid FROM core_dangbeiorder WHERE app_order_id=%s", (app_order_id, ))
        if not res:
            return

        uid, pid = res[0]
        user = yield self.get_user(uid)

        # 2. 已记录，忽略当前请求
        recorded = yield self.has_been_recorded(uid, app_order_id)
        if recorded:
            return

        # 3. 发送首冲礼包并记录支付
        yield self.set_dangbeipayrecord(uid, app_order_id, pid, pay_info['extra'], pay_info['Total_fee'], pay_info['Out_trade_no'], pay_info['start'])

        # 4. 获取当贝渠道的所有商品列表
        channel_id = yield self.get_channel_id('dangbei')
        products = yield self.get_products(channel_id)

        payrecords = yield self.predis.get('payrecords:%s:%s' % (ZONE_ID, uid))
        if payrecords:
            payrecords = pickle.loads(str(payrecords))
            if pid in payrecords:
                is_first = 0   # 是否第一次购买月卡
                product = products[pid]
                if product['sequence'] == PRODUCT_SEQUENCE_FIRST:
                    if product['type'] == PRODUCT_TYPE_CARD:
                        left_days, is_first = yield self.set_card(user, pid)
                        if left_days > 0:
                            payrecords[pid] = left_days
                        if is_first:
                            user['works']['01007'] = {"_": 1, "tags": {"CARD": [1, 1]}}

                    elif product['type'] == PRODUCT_TYPE_LIMIT:
                        gid, = [product_id for product_id, p in products.iteritems() if p['code'] == product['code'] and p['type'] == PRODUCT_TYPE_UNLIMIT]
                        del payrecords[pid]
                        payrecords[gid] = '-1'

                user['vrock'] += product['value']
                user['rock'] += product['value']
                user['rock'] += product['extra']
                if is_first:
                    cuser = dict(rock=user['rock'], vrock=user['vrock'], works=user['works'])
                else:
                    cuser = dict(rock=user['rock'], vrock=user['vrock'])
                logmsg = u'充值(当贝):购买%s' % pid
                yield self.set_user(uid, logmsg, **cuser)
                yield self.set_inpour(user, product['value'])
                yield self.predis.set('payrecords:%s:%s' % (ZONE_ID, uid), pickle.dumps(payrecords))

        yield self.update_payrecord(user, products)

    def ensure_sign(self, pay_info, sign):
        message = ''.join([
            pay_info['Out_trade_no'],
            DANGBEI_APP_KEY,
            pay_info['Pay_user'],
            DANGBEI_MAGIC])
        _sign = hashlib.md5(message).hexdigest()
        if _sign != sign:
            raise web.HTTPError(400)

    @defer.inlineCallbacks
    def get_products(self, channel_id):
        products = {}

        query = """
        SELECT pid, code, sequence, type, value, extra, times, price
        FROM core_product_channels AS a, core_product AS b
        WHERE a.product_id=b.id AND a.channel_id=%s
        """
        rows = yield self.sql.runQuery(query, (channel_id, ))
        for r in rows:
            products[r[0]] = dict(
                pid=r[0], code=r[1], sequence=r[2], type=r[3], value=r[4],
                extra=r[5], times=r[6], price=r[7]
            )
        defer.returnValue(products)

    @defer.inlineCallbacks
    def has_been_recorded(self, uid, app_order_id):
        rec = yield self.sql.runQuery("SELECT * FROM core_dangbeipayrecord WHERE user_id=%s AND app_order_id=%s LIMIT 1", (uid, app_order_id))
        if rec:
            defer.returnValue(True)
        else:
            defer.returnValue(False)

    @defer.inlineCallbacks
    def update_payrecord(self, user, products):
        payrecords = {}
        for pid, product in products.iteritems():
            res = yield self.sql.runQuery("select paied_at from core_dangbeipayrecord where user_id=%s and pid=%s limit 1", (user['uid'], pid))
            lefttime = '-1'
            if res:
                if product['sequence'] == PRODUCT_SEQUENCE_FIRST:
                    if product['type'] == PRODUCT_TYPE_CARD:
                        res = yield self.sql.runQuery("SELECT created_at, ended_at FROM core_card WHERE user_id=%s AND gid=%s LIMIT 1", (user['uid'], pid))
                        if res:
                            created_at, ended_at = res[0]
                            t = datetime.datetime.today().date()
                            lefttime = (ended_at - int(time.mktime(t.timetuple()))) / 3600 / 24
                            if lefttime < 0:
                                lefttime = '-1'
                        payrecords[pid] = lefttime

                    elif product['type'] == PRODUCT_TYPE_UNLIMIT:
                        payrecords[pid] = lefttime
                    else:
                        gid, = [product_id for product_id, p in products.iteritems() if p['code'] == product['code'] and p['type'] == PRODUCT_TYPE_UNLIMIT]
                        payrecords[gid] = lefttime
            else:
                if product['sequence'] == PRODUCT_SEQUENCE_FIRST:
                    payrecords[pid] = lefttime
        yield self.predis.set('payrecords:%s:%s' % (ZONE_ID, user['uid']), pickle.dumps(payrecords))
        defer.returnValue(payrecords)
