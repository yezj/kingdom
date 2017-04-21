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
from front import storage, D
from twisted.python import log
#from front.handlers.base import BaseHandler
from front.wiapi import *
from front.handlers.base import ApiHandler, ApiJSONEncoder
from local_settings import ZONE_ID

@handler
class GetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Batt get', '/batt/get/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('bid', True, str, '010101', '010101', 'bid'),
        Param('hids', True, str, '01002,01001', '01002,01001', 'hids'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Batt")
    def post(self):

        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return
        is_double = False
        res = yield self.sql.runQuery("SELECT created_at, ended_at FROM core_doubleevent_channels AS a, core_doubleevent AS b,\
         core_channel AS c WHERE a.doubleevent_id=b.id AND a.channel_id=c.id AND c.slug=%s LIMIT 1",\
          (self.get_argument("channel", "putaogame"), ))
        if res:
            created_at, ended_at = res[0]
            created_at = int(time.mktime(created_at.timetuple()))
            ended_at = int(time.mktime(ended_at.timetuple()))
            now = int(time.mktime(datetime.datetime.now().timetuple()))
            if now >= created_at and now <= ended_at:
                is_double = True
        try:
            eid = self.get_argument("bid")
            #print 'eid', eid
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
        res = yield self.sql.runQuery("SELECT prod, maxnum, minnum FROM core_match WHERE mid=%s LIMIT 1", (eid, ))
        if res:
            prod, match['maxnum'], match['minnum'] = res[0]
            match['prods'] = [str(p) for p in prod.split(',')]
        hp, tick = yield self.get_hp(user)
        if hp < match.get('hp', 0):
            self.write(dict(err=E.ERR_NOTENOUGH_HP, msg=E.errmsg(E.ERR_NOTENOUGH_HP)))
            return
        label = match.get('label', '')
        if not match.get('playterm', lambda x, y: True)(user, label):
            self.write(dict(err=E.ERR_DISSATISFY_PLAYTERM, msg=E.errmsg(E.ERR_DISSATISFY_PLAYTERM)))
            return
        entrycount = (yield self.redis.hget("entrycount:%s" % uid, label)) or 0
        if not entrycount:
            entrycount = 0
        if entrycount >= match.get('maxentry', 999):
            self.write(dict(err=E.ERR_DISSATISFY_MAXENTRY, msg=E.errmsg(E.ERR_DISSATISFY_MAXENTRY)))
            return
        entrytimer = (yield self.redis.hget("entrytimer:%s" % uid, label)) or 0
        if not entrytimer:
            entrytimer = 0
        if entrytimer + match.get('colddown', 0) > int(time.time()):
            self.write(dict(err=E.ERR_DISSATISFY_COLDDOWN, msg=E.errmsg(E.ERR_DISSATISFY_COLDDOWN)))
            return
        #print  -1 * round(match.get('hp', 6) / 6)
        hp, tick = yield self.add_hp(user, -1 * int(round(match.get('hp', 6) / 6))
                                     , u'准备%s关卡(第%s次)' % (label, entrycount+1))
        hp, tick = yield self.get_hp(user) 
        entrytimes = (yield self.redis.hget("entrytimes:%s" % uid, label)) or 0
        if not entrytimes:
            entrytimes = 0
        if label in D.BATT:
            step = 2
            #is_double = True
        elif label in D.HARDBATT:
            step = 4
            is_double = False
        else:
            rand = 1
        entrytimes = entrytimes % len(match.get('prods', []))
        # prods = E.random_prods(entrytimes, entrytimes+4, match.get('prods', []), 1*rand)
        #print 'entrytimes', entrytimes
        battentrytimes = (yield self.predis.hget("battentrytimes:%s:%s" % (ZONE_ID, uid), label)) or 0
        if not battentrytimes:
            battentrytimes = 0
        battgroup = (yield self.predis.hget("battgroup:%s:%s" % (ZONE_ID, uid), label)) or 0
        if not battgroup:
            battgroup = random.randint(0, len(match.get('prods', []))/100-1)
            yield self.predis.hset("battgroup:%s:%s" % (ZONE_ID, uid), label, battgroup)

        prods, group, battentrytimes = E.random_prods(battgroup, battentrytimes, battentrytimes + step, match.get('prods', []), 1)
        yield self.predis.hset("battgroup:%s:%s" % (ZONE_ID, uid), label, group)
        #yield self.predis.hset("battentrytimes:%s:%s" % (ZONE_ID, uid), label, battentrytimes)

        if is_double:
            for x, y in prods.items():
                prods[x] = y*2

        extra = {}
        awards = {}
        if label not in user['batts']:
            awards = E.awards4firstbatt(label)
            if awards:
                for prod, n in awards.get('prods', {}).items():
                    if prod in prods:
                        prods[prod] += n
                    else:
                        prods[prod] = n
                    if prods[prod] > 9999:
                        prods[prod] = 9999
                    elif prods[prod] == 0:
                        del prods[prod]
                    else:pass        
            extra['firstbatt'] = E.true
            is_double = False
        else:
            extra['firstbatt'] = E.false
        match = {
            'label': label,
            'hids': hids,
            'hp': match.get('hp', 0),
            'gold': match.get('gold', 0)+awards.get('gold', 0),
            'rock': match.get('rock', 0)+awards.get('rock', 0),
            'feat': match.get('feat', 0)+awards.get('feat', 0),
            'xp': match.get('xp', 0),
            'hxp': match.get('hxp', 0),
            'prods': prods,
            'extra': extra, 
        }
        fid = uuid.uuid4().hex
        yield self.set_flush(fid, match)
        nentrycounts = {label: entrycount}
        nentrytimers = {label: entrytimer}
        cuser = dict(hp=hp, tick=tick)
        ret = dict(out=dict(flush=fid, match=match, entrycounts=nentrycounts, entrytimers=nentrytimers), user=cuser, timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)

@handler
class SetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Batt set', '/batt/set/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('fid', True, str, '0cb9abd2f380497198c769344279a7cd', '0cb9abd2f380497198c769344279a7cd', 'fid'),
        Param('gain', True, str, '3', '3', 'gain'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Batt")
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
        if not prop or gain not in (1, 2, 3):
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return

        label = prop['label']
        entrycount = (yield self.redis.hget("entrycount:%s" % uid, label)) or 0
        try:
            user['xp'], ahp = E.normxp(user, user['xp'] + prop['xp'])
        except E.MAXLEVELREADYGOT:
            ahp = 0
        reason = u'攻打%s关卡(第%s次)' % (label, entrycount+1)
        if ahp > 0:
            reason += u'(升%s级)' % (user['xp']/100000)
        #print  -1 * round(prop['hp'] * 5 / 6) + ahp
        hp, tick = yield self.add_hp(user, -1 * int(round(prop['hp'] * 5 / 6)) + ahp, reason)
        hp, tick = yield self.get_hp(user) 
        user['gold'] += prop['gold']
        user['rock'] += prop['rock']
        user['feat'] += prop['feat']
        for hid in prop['hids']:
            hero = user['heros'][hid]
            hlvmit, hero['xp'] = E.normhxp(user, hero['xp'], prop['hxp'])
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
        #print 'prods', prop['prods']
        if label not in user['batts']:
            user['batts'][label] = {'gain': gain}
            awards = E.awards4firstbatt(label)
            if awards:
                if 'hero' in awards:
                    E.bornhero(user, awards['hero'])
        else:
            if int(gain) > int(user['batts'][label]['gain']):
                user['batts'][label]['gain'] = gain
        cuser = dict(gold=user['gold'], rock=user['rock'], feat=user['feat'], xp=user['xp'], heros=user['heros'],
                     prods=user['prods'], batts=user['batts'])
        nuser = dict(hp=hp, tick=tick, gold=user['gold'], rock=user['rock'], feat=user['feat'], xp=user['xp'],
                     heros=user['heros'], prods=user['prods'],
                     batts={label: user['batts'][label]})

        blackmarket = 0
        market = 0
        if label in D.BATT:
            step = 2
            cwork = E.tagworks(user, {'BATT': 1})
            market = yield self.open_market(user, 1)
        elif label in D.HARDBATT:
            step = 4
            cwork = E.tagworks(user, {'HARDBATT': 1})
            blackmarket = yield  self.open_bmmarket(user, 1)
        else:pass

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
        logmsg = u'战役:攻打%s关卡' % label
        yield self.set_user(uid, logmsg, **cuser)
        yield self.redis.hincrby("entrycount:%s" % uid, label, 1)
        yield self.redis.hincrby("entrytimes:%s" % uid, label, 4)
        yield self.redis.hset("entrytimer:%s" % uid, label, int(time.time()))
        battentrytimes = yield self.predis.hincrby("battentrytimes:%s:%s" % (ZONE_ID, uid), label, step)
        #print 'battentrytimes', battentrytimes
        if battentrytimes >= 100:
            yield self.predis.hset("battentrytimes:%s:%s" % (ZONE_ID, uid), label, battentrytimes-100)
        bminterval = yield self.redis.get('blackmarket:%s' % uid)
        if not bminterval:
            bminterval = 0
        else:
            bminterval = bminterval - int(time.time())
        minterval = yield self.redis.get('market:%s' % uid)
        if not minterval:
            minterval = 0
        else:
            minterval = minterval - int(time.time())
        entrycount = yield self.redis.hget("entrycount:%s" % uid, label)
        if not entrycount:
            entrycount = 0
        entrytimer = yield self.redis.hget("entrytimer:%s" % uid, label)
        if not entrytimer:
            entrytimer = 0
        nentrycounts = {label: entrycount}
        nentrytimers = {label: entrytimer}
        ret = dict(out=dict(user=nuser, entrycounts=nentrycounts, entrytimers=nentrytimers, blackmarket=blackmarket,\
         bminterval=bminterval, market=market, minterval=minterval), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)

@handler
class SweepHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Batt sweep', '/batt/sweep/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('bid', True, str, '010101', '010101', 'bid'),
        Param('times', True, int, 10, 10, 'times'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Batt")
    def post(self):
        #print 'SweepHandler get()'
        uu = self.get_argument("uu", None)
        if uu:
            uu = "%s:%s:%s" % (self.request.remote_ip, self.request.path, uu)
            ret = yield self.get_uu(uu)
            if ret:
                self.write(ret)
                return

        is_double = False
        res = yield self.sql.runQuery("SELECT created_at, ended_at FROM core_doubleevent_channels AS a, core_doubleevent AS b,\
            core_channel AS c WHERE a.doubleevent_id=b.id AND a.channel_id=c.id AND c.slug=%s LIMIT 1",\
            (self.get_argument("channel", "putaogame"), ))
        if res:
            created_at, ended_at = res[0]
            created_at = int(time.mktime(created_at.timetuple()))
            ended_at = int(time.mktime(ended_at.timetuple()))
            now = int(time.mktime(datetime.datetime.now().timetuple()))
            if now >= created_at and now <= ended_at:
                is_double = True
        try:
            eid = self.get_argument("bid")
        except Exception:
            raise web.HTTPError(400, "Argument error")


        uid = self.uid
        user = yield self.get_user(uid)
        times = int(self.get_argument("times", 1))
        try:
            match = E.match4entry(eid)
            assert  user['batts'].get(eid)['gain'] == 3
        except Exception:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return
        res = yield self.sql.runQuery("SELECT prod, maxnum, minnum FROM core_match WHERE mid=%s LIMIT 1", (eid, ))
        if res:
            prod, match['maxnum'], match['minnum']  = res[0]
            match['prods'] = [str(p) for p in prod.split(',')]

        hp, tick = yield self.get_hp(user) 
        if hp < match.get('hp', 0) * times:
            self.write(dict(err=E.ERR_NOTENOUGH_HP, msg=E.errmsg(E.ERR_NOTENOUGH_HP)))
            return
        label = match.get('label', '')
        if not match.get('playterm', lambda x, y: True)(user, label):
            self.write(dict(err=E.ERR_DISSATISFY_PLAYTERM, msg=E.errmsg(E.ERR_DISSATISFY_PLAYTERM)))
            return
        entrycount = (yield self.redis.hget("entrycount:%s" % uid, label)) or 0
        if not entrycount:
            entrycount = 0
        if entrycount + times > match.get('maxentry', 999):
            self.write(dict(err=E.ERR_DISSATISFY_MAXENTRY, msg=E.errmsg(E.ERR_DISSATISFY_MAXENTRY)))
            return
        entrytimer = (yield self.redis.hget("entrytimer:%s" % uid, label)) or 0
        if entrytimer + match.get('colddown', 0) > int(time.time()):
            self.write(dict(err=E.ERR_DISSATISFY_COLDDOWN, msg=E.errmsg(E.ERR_DISSATISFY_COLDDOWN)))
            return
        entrytimes = (yield self.redis.hget("entrytimes:%s" % uid, label)) or 0
        if not entrytimes:
            entrytimes = 0
        battentrytimes = (yield self.predis.hget("battentrytimes:%s:%s" % (ZONE_ID, uid), label)) or 0
        if not battentrytimes:
            battentrytimes = 0

        battgroup = (yield self.predis.hget("battgroup:%s:%s" % (ZONE_ID, uid), label)) or 0
        if not battgroup:
            battgroup = random.randint(0, len(match.get('prods', []))/100-1)
            yield self.predis.hset("battgroup:%s:%s" % (ZONE_ID, uid), label, battgroup)
        blackmarket = 0
        market = 0
        rand = 0
        if label in D.BATT:
            step = 2
            cwork = E.tagworks(user, {'BATT': 1*times})
            market = yield self.open_market(user, 1*times)
            #is_double = True
        elif label in D.HARDBATT:
            step = 4
            cwork = E.tagworks(user, {'HARDBATT': 1*times})
            blackmarket = yield self.open_bmmarket(user, 1*times)
            is_double = False
        else:step = 1
        prods, group, battentrytimes = E.random_prods(battgroup, battentrytimes, battentrytimes + times*step, match.get('prods', []), 1)
        yield self.predis.hset("battgroup:%s:%s" % (ZONE_ID, uid), label, group)
        log.msg("user %s, batt sweep %s , group %s, times %s, prods %s" % (uid, label, group, battentrytimes, prods))
        #print 'prods', prods
        # battentrytimes = battentrytimes % len(match.get('prods', []))
        # prods = E.random_prods(battentrytimes, battentrytimes + times*4, match.get('prods', []), times*rand)
        if is_double:
            for x, y in prods.items():
                prods[x] = y*2
        match = {
            'label': label,
            'hp': match.get('hp', 0),
            'gold': match.get('gold', 0),
            'rock': match.get('rock', 0),
            'feat': match.get('feat', 0),
            'xp': match.get('xp', 0),
            'prods': prods,
        }
        try:
            user['xp'], ahp = E.normxp(user, user['xp'] + match['xp']*times)
        except E.MAXLEVELREADYGOT:
            ahp = 0
        reason = u'扫荡%s关卡(第%s-%s次)' % (label, entrycount+1, entrycount+times)
        if ahp > 0:
            reason += u'(升%s级)' % (user['xp']/100000)
        hp, tick = yield self.add_hp(user, -1 * match['hp']*times + ahp, reason)
        hp, tick = yield self.get_hp(user)
        user['hp'] = hp
        user['gold'] += match['gold']*times
        #user['rock'] += match['rock']
        user['feat'] += match['feat']*times
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
        label = match['label']
        #print 'label', label, eid
        cuser = dict(gold=user['gold'], rock=user['rock'], feat=user['feat'], xp=user['xp'], heros=user['heros'],
                     prods=user['prods'], batts=user['batts'])
        nuser = dict(hp=hp, tick=tick, gold=user['gold'], rock=user['rock'], feat=user['feat'], xp=user['xp'],
                     heros=user['heros'], prods=user['prods'], match=match, batts={label: user['batts'][label]})

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

        bminterval = yield self.redis.get('blackmarket:%s' % uid)
        if not bminterval:
            bminterval = 0
        else:
            bminterval = bminterval - int(time.time())
        minterval = yield self.redis.get('market:%s' % uid)
        if not minterval:
            minterval = 0
        else:
            minterval = minterval - int(time.time())
        logmsg = u'战役:%s次扫荡%s关卡' % (times, label)
        yield self.set_user(uid, logmsg, **cuser)
        yield self.redis.hincrby("entrycount:%s" % uid, label, 1*times)
        yield self.redis.hincrby("entrytimes:%s" % uid, label, 4*times)
        yield self.predis.hset("battentrytimes:%s:%s" % (ZONE_ID, uid), label, battentrytimes)
        yield self.redis.hset("entrytimer:%s" % uid, label, int(time.time()))
        entrycount = yield self.redis.hget("entrycount:%s" % uid, label)
        if not entrycount:
            entrycount = 0
        entrytimer = yield self.redis.hget("entrytimer:%s" % uid, label)
        if not entrytimer:
            entrytimer = 0
        nentrycounts = {label: entrycount}
        nentrytimers = {label: entrytimer}
        ret = dict(out=dict(user=nuser, entrycounts=nentrycounts, entrytimers=nentrytimers, blackmarket=blackmarket,\
         bminterval=bminterval, market=market, minterval=minterval), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)

@handler
class ResetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Batt info', '/batt/info/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('bid', True, str, '010101', '010101', 'bid'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Batt info")
    def post(self):
        #print 'SweepHandler get()'
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
        try:
            match = E.match4entry(eid)
            assert  user['batts'].get(eid)['gain'] == 3
        except Exception:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return

        label = match.get('label', '')
        if label not in D.HARDBATT:
            raise web.HTTPError(400, "Argument error")

        if not match.get('playterm', lambda x, y: True)(user, label):
            self.write(dict(err=E.ERR_DISSATISFY_PLAYTERM, msg=E.errmsg(E.ERR_DISSATISFY_PLAYTERM)))
            return
        battbuytimes = yield self.redis.get('battbuytimes:%s:%s' % (uid, label))
        if not battbuytimes:
            battbuytimes = 0 
        ret = dict(out=dict(buytimes=battbuytimes), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)    

@handler
class BuyHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Batt buy', '/batt/buy/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('bid', True, str, '010101', '010101', 'bid'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Batt buy")
    def post(self):
        #print 'SweepHandler get()'
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
        try:
            match = E.match4entry(eid)
            assert  user['batts'].get(eid)['gain'] == 3
        except Exception:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return

        label = match.get('label', '')
        if label not in D.HARDBATT:
            raise web.HTTPError(400, "Argument error")

        if not match.get('playterm', lambda x, y: True)(user, label):
            self.write(dict(err=E.ERR_DISSATISFY_PLAYTERM, msg=E.errmsg(E.ERR_DISSATISFY_PLAYTERM)))
            return

        battbuytimes = yield self.redis.get('battbuytimes:%s:%s' % (uid, label))
        if not battbuytimes:
            battbuytimes = 0 
        if battbuytimes >= E.battmaxtimes(user['vrock']):
            self.write(dict(err=E.ERR_DISSATISFY_MAXRESETS, msg=E.errmsg(E.ERR_DISSATISFY_MAXRESETS)))
            return
        cost = E.buy4batt(battbuytimes)
        if user['rock'] < cost.get('rock', 0):
            self.write(dict(err=E.ERR_NOTENOUGH_ROCK, msg=E.errmsg(E.ERR_NOTENOUGH_ROCK)))
            return
        user['rock'] -= cost.get('rock', 0)
        consume = yield self.set_consume(user, cost.get('rock', 0))
        cuser = dict(rock=user['rock'])
        logmsg = u'战役:购买%s关卡次数' % label
        yield self.set_user(uid, logmsg, **cuser)
        consume = yield self.get_consume(user)
        cuser['consume'] = consume
        yield self.redis.hdel("entrycount:%s" % uid, label)
        entrycount = yield self.redis.hget("entrycount:%s" % uid, label)
        if not entrycount:
            entrycount = 0
        yield self.redis.hdel("entrytimer:%s" % uid, label)
        entrytimer = yield self.redis.hget("entrytimer:%s" % uid, label)
        if not entrytimer:
            entrytimer = 0
        yield self.redis.incr('battbuytimes:%s:%s' % (uid, label))
        nentrycounts = {label: entrycount}
        nentrytimers = {label: entrytimer}
        ret = dict(out=dict(user=cuser, entrycounts=nentrycounts), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)

        if uu:
            yield self.set_uu(uu, ret)


