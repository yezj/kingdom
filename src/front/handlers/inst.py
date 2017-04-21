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
    @api('Inst get', '/inst/get/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('iid', True, str, '020201', '020201', 'iid'),
        Param('hids', True, str, '01002,01001', '01002,01001', 'hids'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Inst get")

    def post(self):

        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return

        try:
            eid = self.get_argument("iid")
            hids = self.get_argument("hids").split(',')    # "12,32,56,1,10"
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        try:
            match = E.match4entry(eid)
            heros = {hid: [user['heros'][hid] for hid in hids]}
        except Exception:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return
        opendate = match.get('opendate')
        if datetime.datetime.now().weekday()+1 not in opendate:
            self.write(dict(err=E.ERR_DISSATISFY_ENTRYTIME, msg=E.errmsg(E.ERR_DISSATISFY_ENTRYTIME)))
            return  
        hp, tick = yield self.get_hp(user)
        if hp < match.get('hp', 0):
            self.write(dict(err=E.ERR_NOTENOUGH_HP, msg=E.errmsg(E.ERR_NOTENOUGH_HP)))
            return
        label = match.get('label', '')
        if not match.get('playterm', lambda x, y: True)(user, label):
            self.write(dict(err=E.ERR_DISSATISFY_PLAYTERM, msg=E.errmsg(E.ERR_DISSATISFY_PLAYTERM)))
            return
        entrycount = (yield self.redis.hget("entrycount:%s" % uid, label)) or 0
        if entrycount >= match.get('maxentry', 999):
            self.write(dict(err=E.ERR_DISSATISFY_MAXENTRY, msg=E.errmsg(E.ERR_DISSATISFY_MAXENTRY)))
            return
        entrytimer = (yield self.redis.hget("entrytimer:%s" % uid, label)) or 0
        if entrytimer + match.get('colddown', 0) > int(time.time()):
            self.write(dict(err=E.ERR_DISSATISFY_COLDDOWN, msg=E.errmsg(E.ERR_DISSATISFY_COLDDOWN)))
            return
        #print  -1 * round(match.get('hp', 6) / 6)
        hp, tick = yield self.add_hp(user, -1 * int(round(match.get('hp', 6) / 6)), u'准备%s试炼(第%s次)' % (label, entrycount+1))
        hp, tick = yield self.get_hp(user)
        prods = {}
        rand = match.get('rand', 0)
        if match.get('prods', []):
            prod, num = self.random_prod(match.get('prods', []))
            if prod in prods: 
                prods[prod] += num
            else:
                prods[prod] = num    
        # for one in xrange(0, D.INST_ITEMS_NUM*rand):
        #     prod, num = self.random_prod(match.get('prods', []))
        #     if prod in prods: 
        #         prods[prod] += num
        #     else:
        #         prods[prod] = num

        extra = {}
        match = {
            'label': label,
            'hids': hids,
            'hp': match.get('hp', 0),
            'gold': match.get('gold', 0),
            'rock': match.get('rock', 0),
            'feat': match.get('feat', 0)*D.INST_ITEMS_NUM,
            'xp': match.get('xp', 0),
            'hxp': match.get('hxp', 0),
            'prods': prods,
            'extra': extra,
            'eid': eid,
        }
        fid = uuid.uuid4().hex
        yield self.set_flush(fid, match)
        cuser = dict(hp=hp, tick=tick)
        ret = dict(out=dict(flush=fid, match=match), user=cuser, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)

@handler
class SetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Inst set', '/inst/set/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('fid', True, str, '020201', '020201', 'iid'),
        Param('gain', True, str, '3', '3', 'gain'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Inst set")
    def post(self):

        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return

        try:
            fid = self.get_argument("fid")
            gain = int(self.get_argument("gain"))
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        prop = yield self.get_flush(fid)
        if not prop:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return

        label = prop['label']
        entrycount = (yield self.redis.hget("entrycount:%s" % uid, label)) or 0
        try:
            user['xp'], ahp = E.normxp(user, user['xp'] + prop['xp'])
        except E.MAXLEVELREADYGOT:
            ahp = 0
        reason = u'攻打%s试炼(第%s次)' % (label, entrycount+1)
        if ahp > 0:
            reason += u'(升%s级)' % (user['xp']/100000)
        #print -1 * round(prop['hp'] * 5 / 6) + ahp
        hp, tick = yield self.add_hp(user, -1 * int(round(prop['hp'] * 5 / 6)) + ahp, reason)
        hp, tick = yield self.get_hp(user)
        user['gold'] += prop['gold']
        user['rock'] += prop['rock']
        user['feat'] += prop['feat']
        for hid in prop['hids']:
            hero = user['heros'][hid]
            hlvlimit, hero['xp'] = E.normhxp(user, hero['xp'], prop['hxp'])
        for prod, n in prop['prods'].items():
            if prod in user['prods']:
                user['prods'][prod] += n
            else:
                user['prods'][prod] = n
            if user['prods'][prod] > 9999:
                user['prods'][prod] = 9999
            elif user['prods'][prod] == 0:
                del user['prods'][prod]
        label = prop['label']
        eid = prop['eid']
        if eid not in user['insts']:
            user['insts'][eid] = {'gain': gain}
        else:
            if int(gain) > int(user['insts'][eid]['gain']):
                user['insts'][eid]['gain'] = gain

        cuser = dict(gold=user['gold'], rock=user['rock'], feat=user['feat'], xp=user['xp'], heros=user['heros'],
                     prods=user['prods'], insts=user['insts'])
        nuser = dict(hp=hp, tick=tick, gold=user['gold'], rock=user['rock'], feat=user['feat'], xp=user['xp'],
                     heros=user['heros'], prods=user['prods'], insts=user['insts'])
        if label.startswith('0201'):
            cwork = E.tagworks(user, {'INST1': 1})
        elif label.startswith('0202'):
            cwork = E.tagworks(user, {'INST2': 1})
        else:
            cwork = E.tagworks(user, {'INST3': 1})
        if cwork:
            cuser['works'] = user['works']
            nuser['works'] = user['works']
        ctask = E.pushtasks(user)
        if ctask:
            cuser['tasks'] = user['tasks']
            nuser['tasks'] = user['tasks']
        cmail = E.checkmails(user)
        if cmail:
            cuser['mails'] = user['mails']
            nuser['mails'] = user['mails']
        logmsg = u'试炼:攻打%s关卡' % label
        yield self.set_user(uid, logmsg, **cuser)
        yield self.redis.hincrby("entrycount:%s" % uid, label, 1)
        yield self.redis.hset("entrytimer:%s" % uid, label, int(time.time()))
        nentrycounts = {label: (yield self.redis.hget("entrycount:%s" % uid, label))}
        nentrytimers = {label: (yield self.redis.hget("entrytimer:%s" % uid, label))}
        ret = dict(out=dict(user=nuser, entrycounts=nentrycounts, entrytimers=nentrytimers), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)

@handler
class SweepHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Inst sweep', '/inst/sweep/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('bid', True, str, '010101', '010101', 'bid'),
        Param('times', True, int, 10, 10, 'times'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Inst sweep")
    def post(self):
        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return

        try:
            eid = self.get_argument("bid")
            # hids = self.get_argument("hids").split(',')    # "12,32,56,1,10"
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        times = int(self.get_argument("times", 1))
        try:
            match = E.match4entry(eid)
            assert  user['insts'].get(eid)['gain'] == 3
            #heros = {hid: [user['heros'][hid] for hid in hids]}
        except Exception:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return
        opendate = match.get('opendate')
        if datetime.datetime.now().weekday()+1 not in opendate:
            self.write(dict(err=E.ERR_DISSATISFY_ENTRYTIME, msg=E.errmsg(E.ERR_DISSATISFY_ENTRYTIME)))
            return  
        hp, tick = yield self.get_hp(user)
        if hp < match.get('hp', 0)*times:
            self.write(dict(err=E.ERR_NOTENOUGH_HP, msg=E.errmsg(E.ERR_NOTENOUGH_HP)))
            return
        label = match.get('label', '')
        if not match.get('playterm', lambda x, y: True)(user, label):
            self.write(dict(err=E.ERR_DISSATISFY_PLAYTERM, msg=E.errmsg(E.ERR_DISSATISFY_PLAYTERM)))
            return
        entrycount = (yield self.redis.hget("entrycount:%s" % uid, label)) or 0
        if entrycount >= match.get('maxentry', 999):
            self.write(dict(err=E.ERR_DISSATISFY_MAXENTRY, msg=E.errmsg(E.ERR_DISSATISFY_MAXENTRY)))
            return
        entrytimer = (yield self.redis.hget("entrytimer:%s" % uid, label)) or 0
        if entrytimer + match.get('colddown', 0) > int(time.time()):
            self.write(dict(err=E.ERR_DISSATISFY_COLDDOWN, msg=E.errmsg(E.ERR_DISSATISFY_COLDDOWN)))
            return
            
        prods = {}
        rand = match.get('rand', 0)
        if match.get('prods', []):
            prod, num = self.random_prod(match.get('prods', []))
            if prod in prods: 
                prods[prod] += num
            else:
                prods[prod] = num            
        # for one in xrange(0, D.INST_ITEMS_NUM*rand*times):
        #     prod, num = self.random_prod(match.get('prods', []))
        #     if prod in prods: 
        #         prods[prod] += num
        #     else:
        #         prods[prod] = num

        try:
            user['xp'], ahp = E.normxp(user, user['xp'] + match['xp']*times)
        except E.MAXLEVELREADYGOT:
            ahp = 0
        reason = u'扫荡%s试炼(第%s-%s次)' % (label, entrycount+1, entrycount+times)
        if ahp > 0:
            reason += u'(升%s级)' % (user['xp']/100000)
        hp, tick = yield self.add_hp(user, -1 * match['hp']*times + ahp, reason)
        hp, tick = yield self.get_hp(user)
        user['hp'] = hp
        user['gold'] += match.get('gold', 0)*times
        user['rock'] += match.get('rock', 0)*times
        user['feat'] += match.get('feat', 0)*times
        for prod, n in prods.items():
            if prod in user['prods']:
                user['prods'][prod] += n
            else:
                user['prods'][prod] = n
            if user['prods'][prod] > 9999:
                user['prods'][prod] = 9999
            elif user['prods'][prod] == 0:
                del user['prods'][prod]
        label = match.get('label', '')
        match = dict(gold=match.get('gold', 0), rock=match.get('rock', 0), feat=match.get('feat', 0),\
        xp=match.get('xp', 0), prods=prods)
        #print 'match', match
        cuser = dict(gold=user['gold'], rock=user['rock'], feat=user['feat'], xp=user['xp'], heros=user['heros'],
                     prods=user['prods'])
        nuser = dict(hp=hp, tick=tick, gold=user['gold'], rock=user['rock'], feat=user['feat'], xp=user['xp'],
                     heros=user['heros'], match=match, prods=user['prods'])
        if label.startswith('0201'):
            cwork = E.tagworks(user, {'INST1': times})
        elif label.startswith('0202'):
            cwork = E.tagworks(user, {'INST2': times})
        else:
            cwork = E.tagworks(user, {'INST3': times})
        if cwork:
            cuser['works'] = user['works']
            nuser['works'] = user['works']
        ctask = E.pushtasks(user)
        if ctask:
            cuser['tasks'] = user['tasks']
            nuser['tasks'] = user['tasks']
        cmail = E.checkmails(user)
        if cmail:
            cuser['mails'] = user['mails']
            nuser['mails'] = user['mails']
        logmsg = u'试炼:%s次扫荡%s关卡' % (times, label)
        yield self.set_user(uid, logmsg, **cuser)
        yield self.redis.hincrby("entrycount:%s" % uid, label, 1*times)
        yield self.redis.hset("entrytimer:%s" % uid, label, int(time.time()))
        nentrycounts = {label: (yield self.redis.hget("entrycount:%s" % uid, label))}
        nentrytimers = {label: (yield self.redis.hget("entrytimer:%s" % uid, label))}
        ret = dict(out=dict(user=nuser, entrycounts=nentrycounts, entrytimers=nentrytimers), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)

