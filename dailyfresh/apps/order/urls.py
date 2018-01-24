from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from .views import OrderPlaceView, OrderCommitView
urlpatterns = [
    url(r'^place', login_required(OrderPlaceView.as_view()), name='place'),
    url(r'^commit', OrderCommitView.as_view(), name='commit')
]
