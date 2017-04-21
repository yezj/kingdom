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
    @api('Seal set', '/seal/set/', [
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
        
        try:
            E.drawseal(user)
        except E.SEALALREADYGOT:
            self.write(dict(err=E.ERR_SEAL_ALREADYGOT, msg=E.errmsg(E.ERR_SEAL_ALREADYGOT)))
            return

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
        yield self.set_user(uid, **cuser)
        ret = dict(out=dict(user=nuser), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)
