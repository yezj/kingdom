# -*- coding: utf-8 -*-

import time
import zlib
from twisted.internet import defer
from cyclone import escape, web
from front import storage
from front import utils
from front.utils import E
# from front.handlers.base import BaseHandler
from front.wiapi import *
from front.handlers.base import ApiHandler, ApiJSONEncoder

@handler
class SetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Seal set', '/mseal/set/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Prod equipcom")
    def post(self):

        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return

        uid = self.uid
        user = yield self.get_user(uid)
        userseals = user['seals']
        #print 'userseals', userseals
        if userseals:
            sealnu, sealday = userseals
        else:
            sealnu, sealday = 0, 0
        today = datetime.date.today().day
        month = datetime.date.today().month
        if sealnu != 0 and sealday-1 == today:
            self.write(dict(err=E.ERR_SEAL_ALREADYGOT, msg=E.errmsg(E.ERR_SEAL_ALREADYGOT)))
            return
        res = yield self.sql.runQuery("SELECT gold, rock, feat, prods, nums, vip FROM core_seal WHERE day=%s AND month=%s LIMIT 1", (sealnu+1, month))
        if res:
            gold, rock, feat, prod, num, vip = res[0]
            #print gold, rock, feat, prod, num, vip
            if E.vip(user['vrock']) >= vip and E.vip(user['vrock']) > 0:
                times = 2
            else:
                times = 1
            if vip == 0:
                times = 1
            if prod:
                prods = dict(zip([p.zfill(5) for p in prod.split(',')], num.split(',')))
                for prod, n in prods.items():
                    if prod in user['prods']:
                        user['prods'][prod] += int(float(n))*times
                    else:
                        user['prods'][prod] = int(float(n))*times
                    if user['prods'][prod] > 9999:
                        user['prods'][prod] = 9999
                    elif user['prods'][prod] == 0:
                        del user['prods'][prod]
                    else:pass
            user['gold'] += gold*times
            user['rock'] += rock*times
            user['feat'] += feat*times
            userseals[0] += 1
            userseals[1] = today + 1

        cuser = dict(gold=user['gold'], rock=user['rock'], feat=user['feat'], prods=user['prods'], seals=user['seals'])
        nuser = dict(gold=user['gold'], rock=user['rock'], feat=user['feat'], prods=user['prods'], seals=user['seals'])
        ctask = E.pushtasks(user)
        if ctask:
            cuser['tasks'] = user['tasks']
            nuser['tasks'] = user['tasks']
        cmail = E.checkmails(user)
        if cmail:
            cuser['mails'] = user['mails']
            nuser['mails'] = user['mails']
        logmsg = u'月签:第%s天' % (sealnu+1)
        yield self.set_user(uid, logmsg, **cuser)
        ret = dict(out=dict(user=nuser), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)
