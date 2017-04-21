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
from twisted.python import log
from front import D
from front.handlers.base import ApiHandler, ApiJSONEncoder
from local_settings import ZONE_ID


@handler
class InfoHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Package info', '/package/info/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Package info")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        res = yield self.sql.runQuery("SELECT id, level, prods, nums, gold, rock, feat, hp FROM core_vippackage")
        out = {}
        if res:
            for r in res:
                vid, level, prods, nums, gold, rock, feat, hp = r
                if prods:
                    prods = dict(zip(prods.split(','), nums.split(',')))
                else:
                    prods = {}
                result = yield self.sql.runQuery("SELECT * FROM core_userpackage WHERE user_id=%s AND package_id=%s LIMIT 1", (uid, vid))
                #status1 = yield self.predis.keys('package:%s:%s:%s:*' % (ZONE_ID, uid, vid))
                #status = yield self.predis.get('package:%s:%s:%s' % (ZONE_ID, uid, vid))
                #print 'status1', not status1
                #print 'status', not status
                if result:
                    status = 1
                else:
                    status = -1

                out[level] = dict(prods=prods, gold=gold, rock=rock, feat=feat, hp=hp, status=status)
        ret = dict(out=out, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class SetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Package set', '/package/set/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '4GRwMApTJ3VpZCcKcDEKUyc4NycKcDIKcyK', '_sign'),
        Param('level', True, int, 1, 1, 'level'),
        ], filters=[ps_filter], description="Package set")
    def post(self):
        try:
            level = int(self.get_argument("level"))
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        #print level, E.vip(user['vrock'])
        # self.write(dict(err=E.ERR_VIPPACKAGE_CLOSED, msg=E.errmsg(E.ERR_VIPPACKAGE_CLOSED)))
        # return
        if level > E.vip(user['vrock']):
            self.write(dict(err=E.ERR_VIPPACKAGE_DISSATISFY, msg=E.errmsg(E.ERR_VIPPACKAGE_DISSATISFY)))
            return

        res = yield self.sql.runQuery("SELECT id, prods, nums, gold, rock, feat, hp FROM core_vippackage WHERE level=%s LIMIT 1", (level, ))
        if res:
            vid, prods, nums, gold, rock, feat, hp = res[0]
            if prods:
                prods = dict(zip(prods.split(','), nums.split(',')))
            else:
                prods = {}
            result = yield self.sql.runQuery("SELECT * FROM core_userpackage WHERE user_id=%s AND package_id=%s LIMIT 1", (uid, vid))
            # status1 = yield self.predis.keys('package:%s:%s:%s:*' % (ZONE_ID, uid, vid))
            # status = yield self.predis.get('package:%s:%s:%s' % (ZONE_ID, uid, vid))
            if result:
                self.write(dict(err=E.ERR_VIPPACKAGE_ALREADYGOT, msg=E.errmsg(E.ERR_VIPPACKAGE_ALREADYGOT)))
                return

            user['rock'] += int(rock)
            user['gold'] += int(gold)
            user['feat'] += int(feat)
            hp, tick = yield self.add_hp(user, hp, u'VIP礼包%s奖励' % level)
            hp, tick = yield self.get_hp(user)
            for prod, num in prods.items():
                if prod in user['prods']:
                    user['prods'][prod] += int(num)
                else:
                    user['prods'][prod] = int(num)
                if user['prods'][prod] > 9999:
                    user['prods'][prod] = 9999
                elif user['prods'][prod] == 0:
                    del user['prods'][prod]
            cuser = dict(gold=user['gold'], rock=user['rock'], prods=user['prods'], feat=user['feat'])
            nuser = dict(gold=user['gold'], rock=user['rock'], prods=user['prods'], feat=user['feat'], hp=hp)
            logmsg = u'VIP礼包:级别%s奖励' % level
            yield self.set_user(uid, logmsg, **cuser)
            query = "INSERT INTO core_userpackage(user_id, package_id) VALUES (%s, %s) RETURNING id"
            params = (uid, vid)
            for i in range(5):
                try:
                    res = yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
            ret = dict(user=nuser, timestamp=int(time.time()))
            reb = zlib.compress(escape.json_encode(ret))
            self.write(ret)

        else:
            self.write(dict(err=E.ERR_VIPPACKAGE_NOTFOUND, msg=E.errmsg(E.ERR_VIPPACKAGE_NOTFOUND)))
            return

