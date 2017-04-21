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
from front.handlers.base import BaseHandler


class FindHandler(BaseHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    def get(self):

        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return

        uid = self.uid
        user = yield self.get_user(uid)
        res = yield self.sql.runQuery("SELECT id, name, avat, xp, jheros, jfight FROM core_user WHERE xp >= %s AND id <> %s LIMIT 1", (user['xp'], uid))
        if res:
            jheros = escape.json_decode(res[0][4])
            jfight = escape.json_decode(res[0][5])
            playerheros = dict(jhero.items()[:5])
            player = dict(uid=res[0][0], name=res[0][1], avat=res[0][2], xp=res[0][3],
                          heros=playerheros)
            ret = dict(out=dict(player=player), timestamp=int(time.time()))
            reb = zlib.compress(escape.json_encode(ret))
            self.write(ret)

            if uu:
                yield self.set_uu(uu, ret)


class WardHandler(BaseHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    def get(self):

        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return

        try:
            hids = self.get_argument("hids").split(',')    # "12,32,56,1,10"
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        did = 1
        playerheros = dict(user['heros'].items()[:5])
        player = dict(uid=user['uid'], name=user['name'], avat=user['avat'], xp=user['xp'],
                      heros=playerheros)
        ret = dict(out=dict(door=did, player=player), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)


class GetHandler(BaseHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    def get(self):

        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return

        try:
            did = self.get_argument("did")
            hids = self.get_argument("hids").split(',')    # "12,32,56,1,10"
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        try:
            match = E.match4entry(did)
            heros = {hid: [user['heros'][hid] for hid in hids]}
        except Exception:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return

        hp, tick = yield self.get_hp(uid)
        if hp < match.get('hp', 0):
            self.write(dict(err=E.ERR_NOTENOUGH_HP, msg=E.errmsg(E.ERR_NOTENOUGH_HP)))
            return
        if not match.get('playterm', lambda x: True)(user):
            self.write(dict(err=E.ERR_DISSATISFY_OPENTERM, msg=E.errmsg(E.ERR_DISSATISFY_OPENTERM)))
            return
        label = match.get('label', '')
        entrycount = (yield self.redis.hget("entrycount:%s" % uid, label)) or 0
        if entrycount >= match.get('maxentry', 999):
            self.write(dict(err=E.ERR_DISSATISFY_MAXENTRY, msg=E.errmsg(E.ERR_DISSATISFY_MAXENTRY)))
            return
        entrytimer = (yield self.redis.hget("entrytimer:%s" % uid, label)) or 0
        if entrytimer + match.get('colddown', 0) > int(time.time()):
            self.write(dict(err=E.ERR_DISSATISFY_COLDDOWN, msg=E.errmsg(E.ERR_DISSATISFY_COLDDOWN)))
            return

        prods = {}
        for prod, rate in match.get('prods', []):
            if random.random() < rate:
                if prod in prods:
                    prods[prod] += 1
                else:
                    prods[prod] = 1
        match = {
            'label': label,
            'hids': hids,
            'hp': match.get('hp', 0),
            'gold': match.get('gold', 0),
            'rock': match.get('rock', 0),
            'feat': match.get('feat', 0),
            'xp': match.get('xp', 0),
            'hxp': match.get('hxp', 0),
            'prods': prods
        }
        fid = uuid.uuid4().hex
        yield self.set_flush(fid, match)
        ret = dict(out=dict(flush=fid, match=match), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)


class SetHandler(BaseHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    def get(self):

        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return

        try:
            fid = self.get_argument("fid")
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        prop = yield self.get_flush(fid)
        if not prop or gain < 1 or gain > 3:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return

        hp, tick = yield self.add_hp(uid, -1 * prop['hp'])
        user['gold'] += prop['gold']
        user['rock'] += prop['rock']
        user['feat'] += prop['feat']
        user['xp'] = E.normxp(user, user['xp'] + prop['xp'])
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
            else:pass
        label = prop['label']
        if label in user['batts']:
            user['batts'][label]['gain'] = gain
        else:
            user['batts'][label] = {'gain': gain}
        cuser = dict(gold=user['gold'], rock=user['rock'], feat=user['feat'], xp=user['xp'], heros=user['heros'],
                     prods=user['prods'], batts=user['batts'])
        nuser = dict(hp=hp, tick=tick, gold=user['gold'], rock=user['rock'], feat=user['feat'], xp=user['xp'],
                     heros={hid: {'xp': user['heros'][hid]['xp']} for hid in prop['hids']}, prods=user['prods'],
                     batts={label: user['batts'][label]})
        cwork = E.tagworks(user, {'BATT': 1})
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
        yield self.set_user(uid, **cuser)
        yield self.redis.hincrby("entrycount:%s" % uid, label, 1)
        yield self.redis.hset("entrytimer:%s" % uid, label, int(time.time()))
        nentrycounts = {label: (yield self.redis.hget("entrycount:%s" % uid, label))}
        nentrytimers = {label: (yield self.redis.hget("entrytimer:%s" % uid, label))}
        ret = dict(out=dict(user=nuser, entrycounts=nentrycounts, entrytimers=nentrytimers), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)
