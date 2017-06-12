import cyclone.web
import api_doc
from twisted.internet.tcp import _AbortingMixin
from wiapi import api_manager
from front.handlers import home
from front.handlers import hero
from front.handlers import prod
from front.handlers import batt
from front.handlers import inst
from front.handlers import door
from front.handlers import work
from front.handlers import seal
from front.handlers import task
from front.handlers import mail
from front.handlers import user
from front.handlers import guide
from front.handlers import lott
from front.handlers import arena
from front.handlers import hunt
#from front.handlers import prison
from front.handlers import hp
from front.handlers import gold
from front.handlers import rock
from front.handlers import pay
from front.handlers import book
from front.handlers import tax
from front.handlers import sp
from front.handlers import blackmarket
from front.handlers import market
from front.handlers import store
from front.handlers import cron
from front.handlers import box
from front.handlers import worship
from front.handlers import beauty
from front.handlers import pearl
from front.handlers import monthseal
from front.handlers import robot
from front.handlers import alipay
from front.handlers import xmpay
from front.handlers import letvpay
from front.handlers import chinamobile
from front.handlers import lovegame
from front.handlers import activity
from front.handlers import code
from front.handlers import recharge
from front.handlers import seckill
from front.handlers import dangbei
from front.handlers import package
from front.handlers import draw
from front.handlers import expedition
from front.handlers import versus

from front.handlers import fourteenseal
from front.handlers import atet
from front.handlers import guild
from front.handlers import gate
from front.handlers import stage
from front.debug import gmprod
from front.debug import gmaccount
from front.debug import gmhero
from operate import operate
from local_settings import DEBUG

url_patterns = [
    (r'/', home.HomeHandler),
    (r'/active/', home.ActiveHandler),
    (r'/startup/', home.StartupHandler),
    (r'/sync/', home.SyncHandler),
    (r'/guide/', guide.GuideHandler),
    (r'/syncdb/', home.SyncdbHandler),
    (r'/flushdb/', home.FlushdbHandler),
    (r'/hero/skillup/', hero.SkillUpHandler),
    (r'/hero/equipon/', hero.EquipOnHandler),
    (r'/hero/levelup/', hero.LevelUpHandler),
    (r'/hero/starup/', hero.StarUpHandler),
    (r'/hero/colorup/', hero.ColorUpHandler),
    (r'/hero/recruit/', hero.RecruitHandler),
    (r'/prod/equipcom/', prod.EquipcomHandler),
    (r'/prod/sellout/', prod.SelloutHandler),
    (r'/batt/get/', batt.GetHandler),
    (r'/batt/set/', batt.SetHandler),
    (r'/batt/sweep/', batt.SweepHandler),
    (r'/inst/get/', inst.GetHandler),
    (r'/inst/set/', inst.SetHandler),
    (r'/door/find/', door.FindHandler),
    (r'/door/ward/', door.WardHandler),
    (r'/door/get/', door.GetHandler),
    (r'/door/set/', door.SetHandler),
    
    (r'/work/get/', work.GetHandler),
    (r'/work/set/', work.SetHandler),

    (r'/seal/set/', seal.SetHandler),

    (r'/task/get/', task.GetHandler),
    (r'/task/set/', task.SetHandler),
    (r'/mail/get/', mail.GetHandler),
    (r'/mail/set/', mail.SetHandler),
    (r'/user/get/', user.GetHandler),
    (r'/user/set/', user.SetHandler),
    (r'/user/login/', user.LoginHandler),
    (r'/user/register/', user.RegisterHandler),
    (r'/lott/info/', lott.InfoHandler),
    (r'/lott/get/', lott.GetHandler),

    (r'/arena/info/', arena.InfoHandler),
    (r'/arena/match/', arena.MatchHandler),
    (r'/arena/guard/', arena.GuardHandler),
    (r'/arena/reset/', arena.ResetHandler),
    (r'/arena/rank/', arena.RankHandler),
    (r'/arena/change/', arena.ChangeHandler),
    (r'/arena/record/', arena.RecordHandler),
    (r'/arena/shop/', arena.ShopHandler),
    (r'/arena/buy/', arena.BuyHandler),
    (r'/arena/refresh/', arena.RefreshHandler),
    (r'/arena/resetcd/', arena.ResetCDHandler),
    #(r'/arena/create/', arena.CreateUserHandler),

    (r'/hunt/info/', hunt.InfoHandler),
    (r'/hunt/search/', hunt.SearchHandler),
    (r'/hunt/create/', hunt.CreateUserHandler),

    # (r'/notify/', pay.NotifyHandler),
    # (r'/verify/', pay.VerifyHandler),
    # gm tools
    (r'/gm/account/edit/', gmaccount.EditHandler),
    (r'/gm/prod/edit/', gmprod.EditProdHandler),

    (r'/crossdomain\.xml', home.CrossdomainHandler),
    (r'/crossdomain\.xml', cyclone.web.RedirectHandler,
     {'url': '/static/crossdmain.xml'}),
]
if DEBUG == True:
    apiurls = api_manager.get_urls() + url_patterns + [(r"/doc$", api_doc.ApiDocHandler), (r"/map$", api_doc.ApiMapHandler),]
else:
    apiurls = url_patterns
