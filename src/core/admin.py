from django.contrib import admin
import simplejson as json
from django.utils.translation import ugettext_lazy as _
from models import *


class ChannelAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug')
    search_fields = ('title',)
    fields = ('title', 'slug')


class UserAdmin(admin.ModelAdmin):
    #list_display = ('nickname', 'avat', 'xp', 'gold', 'rock')
    search_fields = ('nickname',)


class MailAdmin(admin.ModelAdmin):
    list_display = ('sender', 'to', 'title', 'type', 'created_at')
    search_fields = ('title',)





admin.site.register(Channel, ChannelAdmin)
admin.site.register(User, UserAdmin)
admin.site.register(Mail, MailAdmin)
