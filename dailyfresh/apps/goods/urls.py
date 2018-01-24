from django.conf.urls import url
from .views import IndexView, DetaliView,ListView

urlpatterns = [
    url(r'^$', IndexView.as_view(), name='index'),
    url(r'^goods/(?P<sku_id>\d+)$', DetaliView.as_view(), name='detail'),
    url(r'^list/(?P<type_id>\d+)/(?P<page>\d+)$', ListView.as_view(), name='list')
]
