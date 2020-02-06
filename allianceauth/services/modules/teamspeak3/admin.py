from django.contrib import admin
from allianceauth.eveonline.models import EveCharacter

from .models import AuthTS, Teamspeak3User, StateGroup


class MainCorporationsFilter(admin.SimpleListFilter):
    """Custom filter to show corporations from service users only"""
    title = 'corporation'
    parameter_name = 'main_corporations'

    def lookups(self, request, model_admin):
        qs = EveCharacter.objects\
            .exclude(userprofile=None)\
            .exclude(userprofile__user__teamspeak3=None)\
            .values('corporation_id', 'corporation_name')\
            .distinct()
        return tuple([
           (x['corporation_id'], x['corporation_name']) for x in qs
        ])

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.all()
        else:    
            return queryset\
                .filter(user__profile__main_character__corporation_id=self.value())


class MainAllianceFilter(admin.SimpleListFilter):
    """Custom filter to show alliances from service users only"""
    title = 'alliance'
    parameter_name = 'main_alliances'

    def lookups(self, request, model_admin):
        qs = EveCharacter.objects\
            .exclude(alliance_id=None)\
            .exclude(userprofile=None)\
            .exclude(userprofile__user__teamspeak3=None)\
            .values('alliance_id', 'alliance_name')\
            .distinct()
        return tuple([
            (x['alliance_id'], x['alliance_name']) for x in qs
        ])

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.all()
        else:    
            return queryset\
                .filter(user__profile__main_character__alliance_id=self.value())


class Teamspeak3UserAdmin(admin.ModelAdmin):    
    ordering = ('user__username', )
    list_select_related = True  
    
    list_display = (
        'user', 
        'uid',        
        '_corporation',
        '_alliance',        
        '_date_joined',
        'perm_key',
    )
    search_fields = (
        'user__username', 
        'uid',
        'perm_key'
    )
    list_filter = (
        MainCorporationsFilter,        
        MainAllianceFilter,
        'user__date_joined',
    )

    def _corporation(self, obj):
        if obj.user.profile.main_character:
            return obj.user.profile.main_character.corporation_name
        else:
            return ''
    
    _corporation.short_description = 'corporation (main)'
    _corporation.admin_order_field \
        = 'user__profile__main_character__corporation_name'


    def _alliance(self, obj):        
        if (obj.user.profile.main_character 
            and obj.user.profile.main_character.alliance_id
        ):
            return obj.user.profile.main_character.alliance_name
        else:
            return ''
    
    _alliance.short_description = 'alliance (main)'
    _alliance.admin_order_field \
        = 'user__profile__main_character__alliance_name'


    def _date_joined(self, obj):
        return obj.user.date_joined
    
    _date_joined.short_description = 'date joined'
    _date_joined.admin_order_field = 'user__date_joined'


class AuthTSgroupAdmin(admin.ModelAdmin):
    ordering = ('auth_group__name', )
    list_select_related = True  
    
    list_display = ('auth_group', '_ts_group')
    list_filter = ('ts_group', )
    
    fields = ('auth_group', 'ts_group')
    filter_horizontal = ('ts_group',)

    def _ts_group(self, obj):
        return [x for x in obj.ts_group.all().order_by('ts_group_id')]
    
    _ts_group.short_description = 'ts groups'
    #_ts_group.admin_order_field = 'profile__state'


@admin.register(StateGroup)
class StateGroupAdmin(admin.ModelAdmin):
    list_display = ('state', 'ts_group')
    search_fields = ('state__name', 'ts_group__ts_group_name')


admin.site.register(AuthTS, AuthTSgroupAdmin)
admin.site.register(Teamspeak3User, Teamspeak3UserAdmin)
