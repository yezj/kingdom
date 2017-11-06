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

        res = yield self.sql.runQuery("SELECT jgates FROM core_gate WHERE gate_id=%s LIMIT 1", (gate_id,))
        if res:
            jgates, = res[0]
            print 'jgates', jgates
            jgates = escape.json_decode(jgates)
        else:
            jgates = {}
        jgates.update(dict(gate_id=gate_id, timestamp=int(time.time())))
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
        Param('is1PLeft', True, bool, True, True, 'is1PLeft'),
        Param('winCondition', True, int, 1, 1, 'winCondition'),

        Param('winTarget', True, int, -1, -1, 'winTarget'),
        Param('winTargetNum', True, int, 0, 0, 'winTargetNum'),
        Param('lostTarget', True, int, -1, -1, 'lostTarget'),
        Param('lostTargetNum', True, int, 0, 0, 'lostTargetNum'),
        Param('winTime', True, int, 120, 120, 'winTime'),
        Param('rageTime', True, int, 40, 40, 'rageTime'),
        Param('resource', True, int, 500, 500, 'resource'),
        Param('resourceLimit', True, int, 1000, 1000, 'resourceLimit'),
        Param('resourceGrowSpeed', True, int, 1, 1, 'resourceGrowSpeed'),
        Param('map', True, int, 1, 1, 'map'),

        Param('barrie', True, str, '[]', '[]', 'barrie'),
        Param('wave1P', True, str, '[]', '[]', 'wave1P'),
        Param('wave2P', True, str, '[]', '[]', 'wave2P'),
        Param('name_2P', True, str, u'Siege3', u'Siege3', 'name_2P'),
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
            jgates = self.get_argument("jgates")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        res = yield self.sql.runQuery("SELECT jgates FROM core_gate WHERE gate_id=%s LIMIT 1", (gate_id,))
        if not res:
            query = "INSERT INTO core_gate (gate_id, jgates, timestamp) VALUES (%s, %s, %s) RETURNING id"
            params = (gate_id, jgates, int(time.time()))
            for i in range(5):
                try:
                    gid = yield self.sql.runOperation(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        else:
            query = "UPDATE core_gate SET jgates=%s,  timestamp=%s WHERE gate_id=%s"
            params = (jgates, int(time.time()), gate_id)
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
