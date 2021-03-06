from django.conf.urls import url

import allianceauth.urls
from . import views

urlpatterns = allianceauth.urls.urlpatterns

urlpatterns += [
    # Navhelper test urls
    url(r'^main-page/$', views.page, name='p1'),
    url(r'^main-page/sub-section/$', views.page, name='p1-s1'),
    url(r'^second-page/$', views.page, name='p1'),
]

handler500 = 'allianceauth.views.Generic500Redirect'
handler404 = 'allianceauth.views.Generic404Redirect'
handler403 = 'allianceauth.views.Generic403Redirect'
handler400 = 'allianceauth.views.Generic400Redirect'
