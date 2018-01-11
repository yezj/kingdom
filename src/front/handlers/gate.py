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
# from front.handlers.base import BaseHandler
from front.wiapi import *
from front.handlers.base import ApiHandler, ApiJSONEncoder
from local_settings import ZONE_ID


@handler
class GetHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    # @utils.signed
    @api('Gate get', '/gate/get/', [
        Param('gate_id', True, str, '010208_0', '010208_0', 'gate_id'),
    ], filters=[ps_filter], description="Gate get")
    def get(self):
        try:
            gate_id = self.get_argument("gate_id")
        except Exception:
            raise web.HTTPError(400, "Argument error")

        # // "battleId":"id20170608_023_65678",
        # // "rs1":456897635,
        # // "rs2":12345,
        # // "rs3":98765,
        # // "is1PLeft":false,
        #
        # // "name_1P":"我要霸占你你秀发",
        # // "name_2P":"浅时光Bonns",
        # // "level_1P":23,
        # // "level_2P":35,
        # // "icon_1P":301,
        # // "icon_2P":401,
        #
        # // "resource":500,
        # // "resourceLimit":1000,
        # // "resourceGrowSpeed":1,
        fid = uuid.uuid4().hex

        res = yield self.sql.runQuery("""SELECT gate_id, type, "is1PLeft", "winCondition", "winTarget", "winTargetNum",
                    "lostTarget", "lostTargetNum", "winTime", "rageTime", "supplyNow1p", "supplyMax1p", "supplyGrowSpeed1p",
                    "supplyNow2p", "supplyMax2p", "supplyGrowSpeed2p", map, barrie, "wave1P", "wave2P", "name_2P", "level_2P", "icon_2P", "herosNum1P", "herosPermit1P",
                      "herosLevelPermit1P", "soldiersPermit1P", "heros2P", "initTeam1P", "initTeam2P" FROM core_gate
                       WHERE gate_id=%s LIMIT 1""", (gate_id,))
        if res:
            gate_id, type, is1PLeft, winCondition, winTarget, winTargetNum, lostTarget, lostTargetNum, winTime, \
            rageTime, supplyNow1p, supplyMax1p, supplyGrowSpeed1p, supplyNow2p, supplyMax2p, supplyGrowSpeed2p, map, barrie, wave1P, wave2P, name_2P, level_2P, \
            icon_2P, herosNum1P, herosPermit1P, herosLevelPermit1P, soldiersPermit1P, heros2P, initTeam1P, \
            initTeam2P = res[0]
            # print 'jgates', jgates
            # jgates = escape.json_decode(jgates)
            jgates = dict(gate_id=gate_id,
                          type=type,
                          is1PLeft=is1PLeft,
                          winCondition=winCondition,
                          winTarget=winTarget,
                          winTargetNum=winTargetNum,
                          lostTarget=lostTarget,
                          lostTargetNum=lostTargetNum,
                          winTime=winTime,
                          rageTime=rageTime,
                          supplyNow1p=supplyNow1p,
                          supplyMax1p=supplyMax1p,
                          supplyGrowSpeed1p=supplyGrowSpeed1p,
                          supplyNow2p=supplyNow2p,
                          supplyMax2p=supplyMax2p,
                          supplyGrowSpeed2p=supplyGrowSpeed2p,
                          map=map,
                          barrie=escape.json_decode(barrie),
                          wave1P=escape.json_decode(wave1P),
                          wave2P=escape.json_decode(wave2P),
                          name_2P=name_2P,
                          level_2P=level_2P,
                          icon_2P=icon_2P,
                          herosNum1P=herosNum1P,
                          herosPermit1P=escape.json_decode(herosPermit1P),
                          herosLevelPermit1P=herosLevelPermit1P,
                          soldiersPermit1P=escape.json_decode(soldiersPermit1P),
                          heros2P=escape.json_decode(heros2P),
                          initTeam1P=escape.json_decode(initTeam1P),
                          initTeam2P=escape.json_decode(initTeam2P),
                          timestamp=int(time.time())
                          )
        else:
            jgates = dict(timestamp=int(time.time()))
        # jgates.update(dict(gate_id=gate_id, timestamp=int(time.time())))
        # ret = dict(result=jgates)
        # reb = zlib.compress(escape.json_encode(ret))
        self.write(jgates)


@handler
class SetHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    # @utils.signed
    @api('Gate set', '/gate/set/', [
        Param('gate_id', True, str, '010208_0', '010208_0', 'gate_id'),
        Param('type', True, str, 'Siege3', 'Siege3', 'type'),
        Param('is1PLeft', True, int, 1, 1, 'is1PLeft'),
        Param('winCondition', True, int, 1, 1, 'winCondition'),

        Param('winTarget', True, int, -1, -1, 'winTarget'),
        Param('winTargetNum', True, int, 0, 0, 'winTargetNum'),
        Param('lostTarget', True, int, -1, -1, 'lostTarget'),
        Param('lostTargetNum', True, int, 0, 0, 'lostTargetNum'),
        Param('winTime', True, int, 120, 120, 'winTime'),
        Param('rageTime', True, int, 40, 40, 'rageTime'),
        Param('supplyNow1p', True, int, 500, 500, 'supplyNow1p'),
        Param('supplyMax1p', True, int, 1000, 1000, 'supplyMax1p'),
        Param('supplyGrowSpeed1p', True, int, 1, 1, 'supplyGrowSpeed1p'),

        Param('supplyNow2p', True, int, 500, 500, 'supplyNow2p'),
        Param('supplyMax2p', True, int, 1000, 1000, 'supplyMax2p'),
        Param('supplyGrowSpeed2p', True, int, 1, 1, 'supplyGrowSpeed2p'),

        Param('map', True, int, 1, 1, 'map'),

        Param('barrie', True, str, '[]', '[]', 'barrie'),
        Param('wave1P', True, str, '[]', '[]', 'wave1P'),
        Param('wave2P', True, str, '[]', '[]', 'wave2P'),
        Param('name_2P', True, str, 'Siege3', 'Siege3', 'name_2P'),
        Param('level_2P', True, int, 1, 1, 'level_2P'),
        Param('icon_2P', True, int, 1, 1, 'icon_2P'),

        Param('herosNum1P', True, int, 1, 1, 'herosNum1P'),
        Param('herosPermit1P', True, str, '[]', '[]', 'herosPermit1P'),

        Param('herosLevelPermit1P', True, int, 1, 1, 'herosLevelPermit1P'),
        Param('soldiersPermit1P', True, str, '[]', '[]', 'soldiersPermit1P'),

        Param('heros2P', True, str, '[]', '[]', 'heros2P'),
        Param('initTeam1P', True, str, '[]', '[]', 'initTeam1P'),
        Param('initTeam2P', True, str, '[]', '[]', 'initTeam2P'),
    ], filters=[ps_filter], description="Batt")
    def get(self):
        try:
            gate_id = self.get_argument("gate_id")
            type = self.get_argument("type")
            is1PLeft = self.get_argument("is1PLeft")
            winCondition = self.get_argument("winCondition")
            winTarget = self.get_argument("winTarget")
            winTargetNum = self.get_argument("winTargetNum")
            lostTarget = self.get_argument("lostTarget")
            lostTargetNum = self.get_argument("lostTargetNum")
            winTime = self.get_argument("winTime")
            rageTime = self.get_argument("rageTime")
            supplyNow1p = self.get_argument("supplyNow1p")
            supplyMax1p = self.get_argument("supplyMax1p")
            supplyGrowSpeed1p = self.get_argument("supplyGrowSpeed1p")

            supplyNow2p = self.get_argument("supplyNow2p")
            supplyMax2p = self.get_argument("supplyMax2p")
            supplyGrowSpeed2p = self.get_argument("supplyGrowSpeed2p")

            map = self.get_argument("map")
            barrie = self.get_argument("barrie")
            wave1P = self.get_argument("wave1P")
            wave2P = self.get_argument("wave2P")
            level_2P = self.get_argument("level_2P")
            name_2P = self.get_argument("name_2P")
            icon_2P = self.get_argument("icon_2P")
            herosNum1P = self.get_argument("herosNum1P")
            herosPermit1P = self.get_argument("herosPermit1P")
            herosLevelPermit1P = self.get_argument("herosLevelPermit1P")
            soldiersPermit1P = self.get_argument("soldiersPermit1P")
            heros2P = self.get_argument("heros2P")
            initTeam1P = self.get_argument("initTeam1P")
            initTeam2P = self.get_argument("initTeam2P")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        res = yield self.sql.runQuery("SELECT * FROM core_gate WHERE gate_id=%s LIMIT 1", (gate_id,))
        if not res:
            query = """INSERT INTO core_gate (gate_id, type, "is1PLeft", "winCondition", "winTarget", "winTargetNum",
                    "lostTarget", "lostTargetNum", "winTime", "rageTime", "supplyNow1p", "supplyMax1p", "supplyGrowSpeed1p",
                    "supplyNow2p", "supplyMax2p", "supplyGrowSpeed2p", map, barrie, "wave1P", "wave2P", "name_2P",
                     "level_2P", "icon_2P", "herosNum1P", "herosPermit1P", "herosLevelPermit1P", "soldiersPermit1P",
                      "heros2P", "initTeam1P", "initTeam2P", created_at) 
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s, %s, %s %s, %s, %s, %s, %s, %s, %s, %s,
                       %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"""
            params = (gate_id, type, is1PLeft, winCondition, winTarget, winTargetNum, lostTarget, lostTargetNum,
                      winTime, rageTime, supplyNow1p, supplyMax1p, supplyGrowSpeed1p, supplyNow2p, supplyMax2p,
                      supplyGrowSpeed2p, map, barrie, wave1P, wave2P,
                      name_2P, level_2P, icon_2P, herosNum1P, herosPermit1P, herosLevelPermit1P, soldiersPermit1P,
                      heros2P, initTeam1P, initTeam2P, int(time.time()))
            print query % params
            for i in range(5):
                try:
                    gid = yield self.sql.runOperation(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        else:
            query = """UPDATE core_gate SET type=%s, "is1PLeft"=%s, "winCondition"=%s, "winTarget"=%s,
                    "winTargetNum"=%s, "lostTarget"=%s, "lostTargetNum"=%s, "winTime"=%s, "rageTime"=%s, "supplyNow1p"=%s,
                     "supplyMax1p"=%s, "supplyGrowSpeed1p"=%s, "supplyNow2p"=%s,
                     "supplyMax2p"=%s, "supplyGrowSpeed2p"=%s, map=%s, barrie=%s, "wave1P"=%s, "wave2P"=%s,
                      "name_2P"=%s, "level_2P"=%s, "icon_2P"=%s, "herosNum1P"=%s, "herosPermit1P"=%s,
                      "herosLevelPermit1P"=%s, "soldiersPermit1P"=%s, "heros2P"=%s, "initTeam1P"=%s, "initTeam2P"=%s,
                       created_at=%s WHERE gate_id=%s"""
            params = (type, is1PLeft, winCondition, winTarget, winTargetNum, lostTarget, lostTargetNum,
                      winTime, rageTime, supplyNow1p, supplyMax1p, supplyGrowSpeed1p, supplyNow2p, supplyMax2p,
                      supplyGrowSpeed2p, map, barrie, wave1P, wave2P,
                      name_2P, level_2P, icon_2P, herosNum1P, herosPermit1P, herosLevelPermit1P, soldiersPermit1P,
                      heros2P, initTeam1P, initTeam2P, int(time.time()), gate_id)
            print query % params
            for i in range(5):
                try:
                    yield self.sql.runOperation(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        # jgates = escape.json_encode(jgates)
        ret = dict(timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)
