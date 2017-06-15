from services.hooks import MenuItemHook, UrlHook
from alliance_auth import hooks
from timerboard import urls


class TimerboardMenu(MenuItemHook):
    def __init__(self):
        MenuItemHook.__init__(self, 'Structure Timers',
                              'fa fa-clock-o fa-fw grayiconecolor',
                              'timerboard:view',
                              navactive=['timerboard:'])

    def render(self, request):
        if request.user.has_perm('auth.timer_view'):
            return MenuItemHook.render(self, request)
        return ''


@hooks.register('menu_item_hook')
def register_menu():
    return TimerboardMenu()


@hooks.register('url_hook')
def register_url():
    return UrlHook(urls, 'timerboard', r'^timers/')