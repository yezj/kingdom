 # -*- coding: utf-8 -*-

import random
import time
import zlib
import uuid
import datetime
from twisted.internet import defer
from cyclone import escape, web
from front import storage
from front import utils
from front.utils import E
from front import D
 # from front.handlers.base import BaseHandler
from front.wiapi import *
from front.handlers.base import ApiHandler, ApiJSONEncoder
from local_settings import *

@handler
class SetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Recharge set', '/recharge/set/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('rid', True, str, '80001', '80001', 'rid'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Activity set")
    def post(self):

        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return
        try:
            rid = self.get_argument("rid")
            channel = self.get_argument("channel", "putaogame")  
        except Exception:
            raise web.HTTPError(400, "Argument error")

        channels = yield self.sql.runQuery("SELECT id FROM core_channel WHERE slug=%s LIMIT 1", (channel, ))
        if channels:
            channel_id, = channels[0]
        else:
            raise web.HTTPError(404)

        uid = self.uid
        user = yield self.get_user(uid)
        recharge = yield self.predis.get('recharge:%s:%s:%s:%s' % (ZONE_ID, uid, rid, str(datetime.datetime.today().date())))
        if int(recharge) == 0:
            res = yield self.sql.runQuery("SELECT a.gold, a.rock, a.feat, a.hp, a.prods, a.nums FROM core_dayrecharge AS a,\
             core_dayrecharge_channels AS b WHERE rid=%s AND a.id=b.dayrecharge_id LIMIT 1", (rid, ))
            if not res:
                self.write(dict(err=E.ERR_ACTIVITY_NOTFOUND, msg=E.errmsg(E.ERR_ACTIVITY_NOTFOUND)))
                return
            gold, rock, feat, hp, prods, nums = res[0]
            if len(prods) > 0:
                prods = dict(zip(prods.split(','), [int(n) for n in nums.split(',')]))
            else:
                prods = {}
            user['gold'] += gold
            user['rock'] += rock
            user['feat'] += feat
            cost = hp
            hp, tick = yield self.add_hp(user, hp, u'日充奖励')
            hp, tick = yield self.get_hp(user)
            for prod, n in prods.items():
                if prod in user['prods']:
                    user['prods'][prod] += n
                else:
                    user['prods'][prod] = n
                if user['prods'][prod] > 9999:
                    user['prods'][prod] = 9999
                elif user['prods'][prod] == 0:
                    del user['prods'][prod]
                else:pass
            yield self.predis.set('recharge:%s:%s:%s:%s' % (ZONE_ID, uid, rid, str(datetime.datetime.today().date())), E.true)
            cuser = dict(gold=user['gold'], rock=user['rock'], hp=hp, feat=user['feat'], prods=user['prods'])
            nuser = dict(gold=user['gold'], rock=user['rock'], feat=user['feat'], prods=user['prods'])
            logmsg = u'大事件:日充%s奖励' % rid
            yield self.set_user(uid, logmsg, **nuser)
            ret = dict(out=dict(user=cuser), timestamp=int(time.time()))
            reb = zlib.compress(escape.json_encode(ret))
            self.write(ret)
        elif int(recharge) == -1:
            self.write(dict(err=E.ERR_ACTIVITY_DISSATISFY, msg=E.errmsg(E.ERR_ACTIVITY_DISSATISFY)))
            return
        elif int(recharge) == 1:
            self.write(dict(err=E.ERR_ACTIVITY_ALREADYGOT, msg=E.errmsg(E.ERR_ACTIVITY_ALREADYGOT)))
            return
        else:pass
       

