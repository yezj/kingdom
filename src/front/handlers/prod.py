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
class EquipcomHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Prod equipcom', '/prod/equipcom/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('pid', True, str, '01014', '01014', 'pid'),
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

        try:
            pid = self.get_argument("pid")

        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        cost = E.cost4equipcom(pid)
        if not cost:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return

        if user['gold'] < cost.get('gold', 0):
            self.write(dict(err=E.ERR_NOTENOUGH_GOLD, msg=E.errmsg(E.ERR_NOTENOUGH_GOLD)))
            return
        user['gold'] -= cost.get('gold', 0)
        for p, n in cost.get('prods', {}).items():
            if p in user['prods'] and user['prods'][p] >= int(n):
                user['prods'][p] -= int(n)
            else:
                self.write(dict(err=E.ERR_NOTENOUGH_PROD, msg=E.errmsg(E.ERR_NOTENOUGH_PROD)))
                return
        if pid in user['prods']:
            user['prods'][pid] += 1
        else:
            user['prods'][pid] = 1
        if user['prods'][pid] == 0:
            del user['prods'][pid]
        cuser = dict(gold=user['gold'], prods=user['prods'])
        nuser = dict(gold=user['gold'], prods=user['prods'])
        ctask = E.pushtasks(user)
        if ctask:
            cuser['tasks'] = user['tasks']
            nuser['tasks'] = user['tasks']
        cmail = E.checkmails(user)
        if cmail:
            cuser['mails'] = user['mails']
            nuser['mails'] = user['mails']
        logmsg = u'装备:合成%s' % pid
        yield self.set_user(uid, logmsg, **cuser)
        ret = dict(out=dict(user=nuser), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)

@handler
class SelloutHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Prod sellout', '/prod/sellout/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('pid', True, str, '01014', '01014', 'pid'),
        Param('nu', True, str, '0', '0', 'nu'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Prod sellout")

    def post(self):

        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return

        try:
            pid = self.get_argument("pid")
            nu = int(self.get_argument("nu", 1))
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        cost = E.cost4sellout(pid)
        if not cost:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return

        if pid not in user['prods'] or (pid in user['prods'] and user['prods'][pid] < nu):
            self.write(dict(err=E.ERR_NOTENOUGH_PROD, msg=E.errmsg(E.ERR_NOTENOUGH_PROD)))
            return
        user['gold'] += cost.get('gold', 0) * nu
        for p, n in cost.get('prods', {}).items():
            if p in user['prods']:
                user['prods'][p] += n * nu
            else:
                user['prods'][p] = n * nu
        user['prods'][pid] -= nu
        if user['prods'][pid] == 0:
            del user['prods'][pid]
        cuser = dict(gold=user['gold'], prods=user['prods'])
        nuser = dict(gold=user['gold'], prods=user['prods'])
        ctask = E.pushtasks(user)
        if ctask:
            cuser['tasks'] = user['tasks']
            nuser['tasks'] = user['tasks']
        cmail = E.checkmails(user)
        if cmail:
            cuser['mails'] = user['mails']
            nuser['mails'] = user['mails']
        logmsg = u'装备:售卖%s' % pid
        yield self.set_user(uid, logmsg, **cuser)
        ret = dict(out=dict(user=nuser), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)
