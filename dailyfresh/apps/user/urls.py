from django.conf.urls import url
from .views import RegisterView, ActiveView, LoginView, LogoutView,UserInfoView, OrderView, AddressView, VerifyCode
from django.contrib.auth.decorators import login_required

urlpatterns = [
    url(r'^register$', RegisterView.as_view(), name='register'),
    url(r'^active/(?P<token>.*)$', ActiveView.as_view(), name='active'),
    url(r'^login$', LoginView.as_view(), name='login'),
    url(r'^logout$', LogoutView.as_view(), name='logout'),
    url(r'^$', login_required(UserInfoView.as_view()), name='user'),
    url(r'^order/(?P<page>\d+)$', login_required(OrderView.as_view()), name='order'),
    url(r'^address$', login_required(AddressView.as_view()), name='address'),
    url(r'^verify.*$', VerifyCode.as_view(), name='verify')
]
