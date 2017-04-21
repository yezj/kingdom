# -*- coding: utf-8 -*-

import random
import time
import zlib
import uuid
from twisted.internet import defer
from cyclone import escape, web
from front import storage
from front import utils
from front.utils import E
# from front.handlers.base import BaseHandler
from front.wiapi import *
from front.handlers.base import ApiHandler, ApiJSONEncoder

@handler
class GetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Task get', '/task/get/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Task get")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        cuser = dict(tasks=user['tasks'])
        ret = dict(out=dict(user=cuser), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

@handler
class SetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Task set', '/task/set/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('tid', True, str, '02001', '02001', 'tid'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Task set")
    def post(self):

        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return

        try:
            tid = self.get_argument("tid")
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        
        try:
            E.drawtask(user, tid)
        except E.TASKNOTFOUND:
            self.write(dict(err=E.ERR_TASK_NOTFOUND, msg=E.errmsg(E.ERR_TASK_NOTFOUND)))
            return
        except E.TASKALREADYGOT:
            self.write(dict(err=E.ERR_TASK_ALREADYGOT, msg=E.errmsg(E.ERR_TASK_ALREADYGOT)))
            return
        except E.TASKDISSATISFY:
            self.write(dict(err=E.ERR_TASK_DISSATISFY, msg=E.errmsg(E.ERR_TASK_DISSATISFY)))
            return
        cuser = dict(gold=user['gold'], rock=user['rock'], feat=user['feat'], prods=user['prods'], tasks=user['tasks'])
        nuser = dict(gold=user['gold'], rock=user['rock'], feat=user['feat'], prods=user['prods'], tasks=user['tasks'])
        ctask = E.pushtasks(user)

        if ctask:
            cuser['tasks'] = user['tasks']
            nuser['tasks'] = user['tasks']
        cmail = E.checkmails(user)
        if cmail:
            cuser['mails'] = user['mails']
            nuser['mails'] = user['mails']
        logmsg = u'活动:%s奖励' % tid
        yield self.set_user(uid, logmsg, **cuser)
        ret = dict(out=dict(user=nuser), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)