# -*- coding: utf-8 -*-

import time
import zlib
import pickle
from twisted.internet import defer
from cyclone import escape, web
from front import storage
from front import utils
from front.utils import E
# from front.handlers.base import BaseHandler
from front.wiapi import *
from front.handlers.base import ApiHandler, ApiJSONEncoder
from local_settings import ZONE_ID

@handler
class SkillUpHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hero skillup', '/hero/skillup/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('hid', True, str, '01002', '01002', 'hid'),
        Param('skills', True, str, '0,0,0,0', '0,0,0,0', 'skills'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Hero skillup")
    def post(self):
        try:
            hid = self.get_argument("hid")
            skills = map(int, self.get_argument("skills").split(','))    # "1,2,3,0"
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        try:
            hero = user['heros'][hid]
            assert len(skills) == 4
            assert skills[3] == 0
        except Exception:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return
        cursp, sptick = yield self.get_sp(user)
        sumsp = sum(skills)
        if cursp < sumsp:
            self.write(dict(err=E.ERR_NOTENOUGH_SP, msg=E.errmsg(E.ERR_NOTENOUGH_SP)))
            return
        lastskills = hero['skills'][:]
        try:
            E.addskills(user, hero, skills)
        except E.XPNOTENOUGH:
            self.write(dict(err=E.ERR_NOTENOUGH_XP, msg=E.errmsg(E.ERR_NOTENOUGH_XP)))
            return
        except E.GOLDNOTENOUGH:
            self.write(dict(err=E.ERR_NOTENOUGH_GOLD, msg=E.errmsg(E.ERR_NOTENOUGH_GOLD)))
            return
        except E.PRODNOTENOUGH:
            self.write(dict(err=E.ERR_NOTENOUGH_PROD, msg=E.errmsg(E.ERR_NOTENOUGH_PROD)))
            return
        except E.MAXSKILLREADYGOT:
            self.write(dict(err=E.ERR_MAXSKILL_ALREADYGOT, msg=E.errmsg(E.ERR_MAXSKILL_ALREADYGOT)))
            return
        sp, sptick = yield self.add_sp(user, -sumsp)
        msg = u"升级技能%s->%s, 消耗技能点%s" % (str(lastskills), str(hero['skills']), sumsp)
        yield self.predis.lpush('all:log:hero', pickle.dumps(['skill', int(time.time()), ZONE_ID, uid, hid, msg]))
        cuser = dict(gold=user['gold'], heros=user['heros'], prods=user['prods'])
        nuser = dict(gold=user['gold'], heros={hid: {'skills': hero['skills']}}, prods=user['prods'],\
         sp=sp, interval=sptick)
        cwork = E.tagworks(user, {'SKILLUP': sum(skills)})
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
        logmsg = u'英雄:%s升级技能' % hid
        yield self.set_user(uid, logmsg, **cuser)
        ret = dict(out=dict(user=nuser), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)


@handler
class EquipOnHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hero equipon', '/hero/equipon/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('hid', True, str, '01002', '01002', 'hid'),
        Param('equips', True, str, '1,0,0,0,0,0', '1,0,0,0,0,0', 'skills'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Hero equipon")
    def post(self):
        try:
            hid = self.get_argument("hid")
            equips = map(int, self.get_argument("equips").split(','))    # "0,1,0,0,1,0"
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        try:
            hero = user['heros'][hid]
            assert len(equips) == 6
        except Exception:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return

        lastequips = str(hero['equips'])
        try:
            E.setequips(user, hero, equips)

        except E.PRODNOTENOUGH:
            self.write(dict(err=E.ERR_NOTENOUGH_PROD, msg=E.errmsg(E.ERR_NOTENOUGH_PROD)))
            return

        msg = u"添加装备%s->%s, 消耗道具%s" % (str(lastequips), str(hero['equips']), str(equips))
        yield self.predis.lpush('all:log:hero', pickle.dumps(['equip', int(time.time()), ZONE_ID, uid, hid, msg]))

        cuser = dict(heros=user['heros'], prods=user['prods'])
        nuser = dict(heros={hid: {'equips': hero['equips']}}, prods=user['prods'])
        cwork = E.tagworks(user, {'EQUIP': 1})
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
        logmsg = u'英雄:%s添加装备' % hid
        yield self.set_user(uid, logmsg, **cuser)
        ret = dict(out=dict(user=nuser), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)


@handler
class LevelUpHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hero levelup', '/hero/levelup/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('hid', True, str, '01002', '01002', 'hid'),
        Param('feat', True, int, 100, 100, 'feat'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Hero levelup")
    def post(self):
        try:
            hid = self.get_argument("hid")
            feat = self.get_argument("feat", 0)
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        try:
            hero = user['heros'][hid]
        except Exception:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return

        lastxp = hero['xp']
        try:
            E.steplevel(user, hero, int(feat))
        except E.FEATNOTENOUGH:
            self.write(dict(err=E.ERR_NOTENOUGH_FEAT, msg=E.errmsg(E.ERR_NOTENOUGH_FEAT)))
            return
        except E.XPNOTENOUGH:
            self.write(dict(err=E.ERR_NOTENOUGH_XP, msg=E.errmsg(E.ERR_NOTENOUGH_XP)))
            return

        msg = u"提升等级%s->%s, 消耗功勋%s" % (lastxp, hero['xp'], feat)
        yield self.predis.lpush('all:log:hero', pickle.dumps(['level', int(time.time()), ZONE_ID, uid, hid, msg]))

        cuser = dict(feat=user['feat'], heros=user['heros'])
        nuser = dict(feat=user['feat'], heros={hid: {'xp': hero['xp']}})
        cwork = E.tagworks(user, {'FEAT': 1})
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

        logmsg = u'英雄:%s提升等级' % hid
        yield self.set_user(uid, logmsg, **cuser)
        ret = dict(out=dict(user=nuser), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)


@handler
class ColorUpHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hero colorup', '/hero/colorup/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('hid', True, str, '01002', '01002', 'hid'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Hero levelup")
    def post(self):
        try:
            hid = self.get_argument("hid")
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        try:
            hero = user['heros'][hid]
        except Exception:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return

        lastcolor = hero['color']
        try:
            E.stepcolor(user, hero)
        except E.GOLDNOTENOUGH:
            self.write(dict(err=E.ERR_NOTENOUGH_GOLD, msg=E.errmsg(E.ERR_NOTENOUGH_GOLD)))
            return
        except E.PRODNOTENOUGH:
            self.write(dict(err=E.ERR_NOTENOUGH_PROD, msg=E.errmsg(E.ERR_NOTENOUGH_PROD)))
            return
        msg = u"提升颜色%s->%s" % (lastcolor, hero['color'])
        yield self.predis.lpush('all:log:hero', pickle.dumps(['color', int(time.time()), ZONE_ID, uid, hid, msg]))

        cuser = dict(gold=user['gold'], heros=user['heros'], prods=user['prods'])
        nuser = dict(gold=user['gold'], heros={hid: {'color': hero['color'], 'equips': hero['equips']}}, prods=user['prods'])
        ctask = E.pushtasks(user)
        if ctask:
            cuser['tasks'] = user['tasks']
            nuser['tasks'] = user['tasks']
        cmail = E.checkmails(user)
        if cmail:
            cuser['mails'] = user['mails']
            nuser['mails'] = user['mails']
        logmsg = u'英雄:%s提升颜色' % hid
        yield self.set_user(uid, logmsg, **cuser)
        ret = dict(out=dict(user=nuser), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)


@handler
class StarUpHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hero starup', '/hero/starup/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('hid', True, str, '01002', '01002', 'hid'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Hero levelup")
    def post(self):
        try:
            hid = self.get_argument("hid")
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)
        try:
            hero = user['heros'][hid]
        except Exception:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return

        laststar = hero['star']
        try:
            E.stepstar(user, hero)
        except E.GOLDNOTENOUGH:
            self.write(dict(err=E.ERR_NOTENOUGH_GOLD, msg=E.errmsg(E.ERR_NOTENOUGH_GOLD)))
            return
        except E.MAXSTARREADYGOT:
            self.write(dict(err=E.ERR_MAXSTAR_ALREADYGOT, msg=E.errmsg(E.ERR_MAXSTAR_ALREADYGOT)))
            return
        except E.PRODNOTENOUGH:
            self.write(dict(err=E.ERR_NOTENOUGH_PROD, msg=E.errmsg(E.ERR_NOTENOUGH_PROD)))
            return
        msg = u"提升星星%s->%s" % (laststar, hero['star'])
        yield self.predis.lpush('all:log:hero', pickle.dumps(['star', int(time.time()), ZONE_ID, uid, hid, msg]))
        cuser = dict(gold=user['gold'], heros=user['heros'], prods=user['prods'])
        nuser = dict(gold=user['gold'], heros={hid: {'star': hero['star']}}, prods=user['prods'])
        ctask = E.pushtasks(user)
        if ctask:
            cuser['tasks'] = user['tasks']
            nuser['tasks'] = user['tasks']
        cmail = E.checkmails(user)
        if cmail:
            cuser['mails'] = user['mails']
            nuser['mails'] = user['mails']
        logmsg = u'英雄:%s提升星星' % hid
        yield self.set_user(uid, logmsg, **cuser)
        ret = dict(out=dict(user=nuser), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)


@handler
class RecruitHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Hero recruit', '/hero/recruit/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('hid', True, str, '01002', '01002', 'hid'),
        Param('_sign', True, str, '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '4GRwMApTJ3VpZCcKcDEKUycxMScKcDIKcyK', '_sign'),
        ], filters=[ps_filter], description="Hero recruit")
    def post(self):
        try:
            hid = self.get_argument("hid")
        except Exception:
            raise web.HTTPError(400, "Argument error")

        uid = self.uid
        user = yield self.get_user(uid)

        if hid in user['heros']:
            self.write(dict(err=E.ERR_INVALID, msg=E.errmsg(E.ERR_INVALID)))
            return

        try:
            E.recruit(user, hid)
        except E.GOLDNOTENOUGH:
            self.write(dict(err=E.ERR_NOTENOUGH_GOLD, msg=E.errmsg(E.ERR_NOTENOUGH_GOLD)))
            return
        except E.PRODNOTENOUGH:
            self.write(dict(err=E.ERR_NOTENOUGH_PROD, msg=E.errmsg(E.ERR_NOTENOUGH_PROD)))
            return
        msg = u"招募英雄%s" % (hid,)
        yield self.predis.lpush('all:log:hero', pickle.dumps(['recruit', int(time.time()), ZONE_ID, uid, hid, msg]))
        cuser = dict(heros=user['heros'], prods=user['prods'], gold=user['gold'])
        logmsg = u'英雄:招募%s' % hid
        yield self.set_user(uid, logmsg, **cuser)
        ret = dict(out=dict(user=cuser), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)
