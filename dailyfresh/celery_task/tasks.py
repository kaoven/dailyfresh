from django.conf import settings
from django.core.mail import send_mail

from celery import Celery

# 初始化django所依赖的环境
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dailyfresh.settings")

app = Celery('celery_task.tasks', broker='redis://192.168.128.134:6379/5')

@app.task
def send_register_active_mail(to_mail, username, token):
    subject = '欢迎使用天天生鲜－注册激活'
    message = ''
    sender = settings.EMAIL_FROM
    receiver = [to_mail]
    html_message = '<h1>%s,欢迎您成为天天生鲜注册会员</h1>请点击以下链接激活您的账户：<br/><a href ="http://192.168.128.134:8000/user/active/%s">http://192.168.128.134:8000/user/active/%s</a>'%(username, token, token)
    send_mail(subject, message, sender, receiver, html_message=html_message)