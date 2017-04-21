# -*- coding: utf-8 -*-

import random
import time
import zlib
import uuid
import json
from twisted.internet import defer
from cyclone import escape, web
from front import storage
from front import utils
from front.utils import E
#from front.handlers.base import BaseHandler
from front.wiapi import *
from front.handlers.base import ApiHandler, ApiJSONEncoder
from local_settings import ZONE_ID

@handler
class GetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Mail get', '/mail/get/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Get mail")
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
        yield self.update_mails(user)
        cuser = {}
        nuser = {}
        cuser['mails'] = user['mails']
        nuser['mails'] = user['mails']
        # mailcomming = E.checkmails(user)
        # if mailcomming:
        #     cuser['mails'] = user['mails']
        #     nuser['mails'] = user['mails']
        usermails = user['mails']
        mids = filter(lambda x: usermails[x] != 1, usermails.keys())
        mails = yield self.get_mails(user, mids)
        mails.sort(key=lambda i: -i['timestamp'])
        mailsws = []
        for mail in mails:
            if mail:
                mid = mail['mid']
                mail['state'] = usermails[mid]
                mailsws.append(mail)
        ctask = E.pushtasks(user)
        if ctask:
            cuser['tasks'] = user['tasks']
            nuser['tasks'] = user['tasks']
        #cuser['guide'] = 1
        yield self.set_user(uid, **cuser)
        ret = dict(out=dict(user=nuser, mails=mailsws), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)

@handler
class SetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Mail set', '/set/mail/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('mid', True, str, '1', '1', 'mid'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Startup")
    def post(self):

        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return

        try:
            mid = self.get_argument("mid")
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)

        try:
            assert mid in user['mails']
        except Exception:
            self.write(dict(err=E.ERR_MAIL_NOTFOUND, msg=E.errmsg(E.ERR_MAIL_NOTFOUND)))
            return

        E.checkmails(user)
        mail = yield self.get_mails(user, [mid])
        if mail:
            mail, = mail
        usermails = user['mails']
        if usermails[mid] == 0:
            awards = mail['awards']
            if awards:
                user['gold'] += int(awards.get('gold', 0))
                user['rock'] += int(awards.get('rock', 0))
                user['feat'] += int(awards.get('feat', 0))
                if awards.has_key('versus_coin'):
                    yield self.update_versuscoin(user, int(awards.get('versus_coin', 0)))
                if int(awards.get('hp', 0)) > 0:
                    reason = u'%s领取邮件体力%s' % (uid, int(awards.get('hp', 0)))
                    yield self.add_hp(user, int(awards.get('hp', 0)), reason)

                yield self.update_arenacoin(user, int(awards.get('arena_coin', 0)))
                for prod, n in awards.get('prods', {}).items():
                    if prod in user['prods']:
                        user['prods'][prod] += int(n)
                    else:
                        user['prods'][prod] = int(n)
                    if user['prods'][prod] > 9999:
                        user['prods'][prod] = 9999
                    elif user['prods'][prod] ==0:
                        del user['prods'][prod]
                    else:pass
                usermails[mid] = 1
            else:
                usermails[mid] = 1

        else:
            self.write(dict(err=E.ERR_MAIL_ALREADYGOT, msg=E.errmsg(E.ERR_MAIL_ALREADYGOT)))
            return
        hp, tick = yield self.get_hp(user)
        user['hp'] = hp
        #yield self.update_mails(user)
        cuser = dict(gold=user['gold'], rock=user['rock'], feat=user['feat'], prods=user['prods'], mails=user['mails'])
        nuser = dict(gold=user['gold'], rock=user['rock'], feat=user['feat'], prods=user['prods'], mails=user['mails'], hp=user['hp'])
        ctask = E.pushtasks(user)
        if ctask:
            cuser['tasks'] = user['tasks']
            nuser['tasks'] = user['tasks']
        logmsg = u'邮件:领取%s奖励' % mid
        yield self.set_user(uid, logmsg, **cuser)
        ret = dict(out=dict(user=nuser), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)
