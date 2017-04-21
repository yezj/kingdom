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
class InfoHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Draw info', '/draw/info/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('pid', True, str, '', 1, 'pid'),
    ], filters=[ps_filter], description="Draw info")
    def post(self):
        try:
            pid = self.get_argument("pid")
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        res = yield self.sql.runQuery("SELECT type, key_id, key_num, chest_id, prods, nums FROM core_chest WHERE chest_id=%s LIMIT 1", (pid,))
        if res:
            ctype, key_id, key_num, chest_id, prods, nums = res[0]
            if len(prods):
                prods = dict(zip(prods.split(','), [int(n) for n in nums.split(',')]))
            else:
                prods = {}
            ret = dict(out=dict(prods=prods, key_id=key_id, key_num=key_num), timestamp=int(time.time()))
            self.write(ret)
        else:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return


@handler
class SetHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Draw set', '/draw/set/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        Param('pid', True, str, '', 1, 'pid'),
        Param('sid', True, str, '', 1, 'sid'),
    ], filters=[ps_filter], description="Draw set")
    def post(self):
        try:
            pid = self.get_argument("pid")
            sid = self.get_argument("sid")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        if pid not in user['prods']:
            self.write(dict(err=E.ERR_NOTENOUGH_PROD, msg=E.errmsg(E.ERR_NOTENOUGH_PROD)))
            return
        if user['prods'][pid] <= 0:
            self.write(dict(err=E.ERR_NOTENOUGH_PROD, msg=E.errmsg(E.ERR_NOTENOUGH_PROD)))
            return
        res = yield self.sql.runQuery("SELECT type, key_id, key_num, chest_id, prods, nums FROM core_chest WHERE chest_id=%s LIMIT 1", (pid,))
        if res:
            ctype, key_id, key_num, chest_id, prods, nums = res[0]
            if len(key_id):
                if key_id in user['prods']:
                    if user['prods'][key_id] >= int(key_num):
                        user['prods'][key_id] -= int(key_num)
                        if user['prods'][key_id] == 0:
                            del user['prods'][key_id]
                    else:
                        self.write(dict(err=E.ERR_NOTENOUGH_PROD, msg=E.errmsg(E.ERR_NOTENOUGH_PROD)))
                        return
                else:
                    self.write(dict(err=E.ERR_NOTENOUGH_PROD, msg=E.errmsg(E.ERR_NOTENOUGH_PROD)))
                    return
            prods = dict(zip(prods.split(','), [int(n) for n in nums.split(',')]))
            if sid in prods:
                if sid in user['prods']:
                    user['prods'][sid] += int(prods[sid])
                else:
                    user['prods'][sid] = int(prods[sid])
                if user['prods'][sid] > 9999:
                    user['prods'][sid] = 9999
                elif user['prods'][sid] == 0:
                    del user['prods'][sid]
                user['prods'][pid] -= 1
                cuser = dict(prods=user['prods'])
                logmsg = u'物品:选择%s宝箱%s' % (pid, sid)
                yield self.set_user(uid, logmsg, **cuser)
                ret = dict(user=cuser, timestamp=int(time.time()))
                self.write(ret)
            else:
                raise web.HTTPError(400, "Argument error")
        else:
            raise web.HTTPError(400, "Argument error")
