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
from local_settings import ZONE_ID

@handler
class GetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Work get', '/work/get/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Work get")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        work = breakfast = lunch = dinner = False
        taxmark = yield self.redis.get('taxmark:%s' % uid)
        if not taxmark:
            work = E.tagworks(user, {'TAX': 1})
        if datetime.datetime.now().hour>=8 and datetime.datetime.now().hour<=24:
            breakfast = E.tagworks(user, {'BREAKFAST': 1})
        if datetime.datetime.now().hour>=12 and datetime.datetime.now().hour<=24:
            lunch = E.tagworks(user, {'LUNCH': 1})
        if datetime.datetime.now().hour>=18 and datetime.datetime.now().hour<=24:
            dinner = E.tagworks(user, {'DINNER': 1})
        if work or breakfast or lunch or dinner: 
            cuser = dict(works=user['works'])
            yield self.set_user(uid, **cuser)
        user['works'] = E.checkworks(user)
        cuser = dict(works=user['works'], seals=user['seals'])
        cuser['card'] = yield self.get_card(user)
        ret = dict(out=dict(user=cuser), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class SetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Work set', '/work/set/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('wid', True, str, '01002', '01002', 'wid'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Work set")
    def post(self):

        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return
        try:
            wid = self.get_argument("wid")
            #print 'wid', wid
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        user['card'] = yield self.get_card(user)
        try:
            E.drawwork(user, wid)
        except E.WORKNOTFOUND:
            self.write(dict(err=E.ERR_WORK_NOTFOUND, msg=E.errmsg(E.ERR_WORK_NOTFOUND)))
            return
        except E.WORKALREADYGOT:
            self.write(dict(err=E.ERR_WORK_ALREADYGOT, msg=E.errmsg(E.ERR_WORK_ALREADYGOT)))
            return
        except E.WORKDISSATISFY:
            self.write(dict(err=E.ERR_WORK_DISSATISFY, msg=E.errmsg(E.ERR_WORK_DISSATISFY)))
            return
        except E.MAXLEVELREADYGOT:
            self.write(dict(err=E.ERR_MAXLEVEL_ALREADYGOT, msg=E.errmsg(E.ERR_MAXLEVEL_ALREADYGOT)))
            return 
        work = D.WORKS[wid]
        userwork = user['works'][wid]
        awards = work.get('awards')
        if awards:
            addhp = awards.get('hp', 0)
            addxp = awards.get('xp', 0)
            if addxp:
                try:
                    user['xp'], ahp = E.normxp(user, user['xp'] + addxp)
                except E.MAXLEVELREADYGOT:
                    ahp = 0
            else:
                ahp = 0
            if (addhp + ahp) > 0:
                reason = u'每日%s任务奖励' % wid
                if ahp > 0:
                    reason += u'(升%s级)' % (user['xp']/100000)
                currhp, tick = yield self.add_hp(user, addhp+ahp, reason)
        currhp, tick = yield self.get_hp(user)
        user['hp'] = currhp
        user['tick'] = tick
        lefttime = 0
        if userwork['tags'].keys()[0] == 'CARD':
            lefttime = yield self.draw_card(user)

        elif userwork['tags'].keys()[0] == 'TAX':
            taxmark = yield self.redis.get('taxmark:%s' % uid)
            if not taxmark and user['batts']:
                all_batts = [str(D.TAX[one*3]).zfill(6) for one in xrange(0, len(D.TAX)/3)]
                now_batts = filter(lambda j:j in all_batts, user['batts'].keys())
                now_batts = sorted(now_batts, reverse=True)
                awards = E.earn4tax(int(now_batts[0]))
                user['feat'] += awards['feat']
                user['gold'] += awards['gold']
                yield self.redis.set('taxmark:%s' % uid, E.true)
        else:pass
        lefttime = yield self.get_card(user)
        cuser = dict(gold=user['gold'], rock=user['rock'], feat=user['feat'], prods=user['prods'], works=user['works'], xp=user['xp'])
        nuser = dict(gold=user['gold'], rock=user['rock'], feat=user['feat'], prods=user['prods'], works=user['works'], xp=user['xp'],\
            hp=user['hp'], tick=user['tick'], card=lefttime)
        
        ctask = E.pushtasks(user)
        if ctask:
            cuser['tasks'] = user['tasks']
            nuser['tasks'] = user['tasks']
        cmail = E.checkmails(user)
        if cmail:
            cuser['mails'] = user['mails']
            nuser['mails'] = user['mails']
        logmsg = u'每日:%s奖励' % wid
        yield self.set_user(uid, logmsg, **cuser)
        ret = dict(out=dict(user=nuser), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)
