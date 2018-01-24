from django.shortcuts import render, redirect
from django.views.generic import View
from django.core.urlresolvers import reverse
from django.contrib.auth import login, logout, authenticate
from django.conf import settings
from django.http import HttpResponse
from django.core.paginator import Paginator
import re

from .models import User, Address
from ..goods.models import GoodsSKU
from ..order.models import OrderGoods, OrderInfo

from django_redis import get_redis_connection
from celery_task.tasks import send_register_active_mail
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from PIL import Image, ImageDraw, ImageFont
from django.utils.six import BytesIO

# Create your views here.


class RegisterView(View):
    """注册账号"""
    def get(self, request):
        """显示注册页面"""
        return render(request, 'register.html')

    def post(self, request):
        """处理注册信息"""
        # 接收参数
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get("allow")
        # 参数校验
        # 校验参数的完整性
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': "数据不完整"})
        # 验证是否同意协议
        if allow != "on":
            return render(request, 'register.html', {'errmsg': "请阅读并同意协议"})
        # 校验邮箱
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': "邮箱不合法"})
        # 验证用户名是否已注册
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None

        if user:
            return render(request, 'register.html', {'errmsg': '用户名已注册'})
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 加密用户的信息，为发送邮件做准备
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {"confirm": user.id}

        # 加密数据
        token = serializer.dumps(info)
        # 加密后的数据为byts类型，需要decode解码
        token = token.decode()

        # 使用celery给客户邮箱发送邮件
        send_register_active_mail.delay(email, username, token)
        return redirect(reverse('goods:index'))


class ActiveView(View):
    """激活账号"""
    def get(self, request, token):
       serializer = Serializer(settings.SECRET_KEY, 3600)
       try:
            # 对token进行解密
            info = serializer.loads(token)
            user_id = info["confirm"]
            # 根据user_id查找用户，激活用户账户
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            return redirect(reverse('user:login'))
       except SignatureExpired:
           return HttpResponse("激活链接失效")


class LoginView(View):
    """登录"""
    def get(self, request):
        """显示登录页面"""
        # 先尝试从COOKIES获取记住的用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES["username"]
            checked = 'checked'
        else:
            username = ''
            checked = ''
        return render(request, 'login.html', {'username': username, 'checked': checked})

    def post(self, request):
        """处理登录请求"""
        # 获取数据
        username = request.POST.get("username")
        password = request.POST.get("pwd")
        remember = request.POST.get("remember")
        verify = request.POST.get('yzm')
        # 校验参数是否完整
        if not all([username, password, verify]):
            return render(request, 'login.html', {'errmsg': '账号和密码不能为空'})

        # 使用django认证系统查询用户名与密码是否匹配
        user = authenticate(username=username, password=password)
        if user is not None:
            # 获取验证码
            verifycode = request.session['verifycode']
            if verify == verifycode:
                 if user.is_active:
                    # 使用django认证系统login（）记录用户登录状态
                    login(request, user)
                    response = redirect(reverse('goods:index'))
                    # 判断是否记住用户名
                    if remember == "on":
                        response.set_cookie('username', username, max_age=604800)
                    else:
                        response.delete_cookie('username')
                    return response
                 else:
                     # 用户名未激活
                     return render(request, 'login.html', {'errmsg': "用户名未激活"})
            else:
                return render(request, 'login.html', {'errmsg':'验证码输入错误'})

        # 用户名或密码错误
        else:
            return render(request, 'login.html', {'errmsg': '用户名或密码错误'})


class LogoutView(View):
    """退出登录"""
    def get(self,request):
        # 清除用户的登录状态
        logout(request)
        return redirect(reverse('goods:index'))


class UserInfoView(View):
    """用户中心－信息页"""
    def get(self,request):
        """显示页面内容"""
        # 获取登录的用户
        user = request.user
        address = Address.objects.get_default_address(user)
        # 链接redis数据库
        conn = get_redis_connection('default')
        history_key = 'history_%d' % user.id
        # 查询键为history_key的５个值
        sku_ids = conn.lrange(history_key, 0, 4)
        skus = []
        for sku_id in sku_ids:
            sku = GoodsSKU.objects.get(id = sku_id)
            skus.append(sku)
        context = {
            'skus': skus,
            'page': 'user',
            'address': address
        }
        return render(request, 'user_center_info.html', context)


class OrderView(View):
    """用户全部订单显示页面"""
    def get(self, request,page):
        # 获取登录用户
        user = request.user
        # 根据user查询用户所有订单
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')
        for order in orders:
            order_skus = OrderGoods.objects.filter(order=order.order_id)
            for order_sku in order_skus:
                # 计算小计
                amount = order_sku.price*order_sku.count
                order_sku.amount = amount
            # 获取订单支付状态的名称
            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
            # 获取订单实付款
            order.total_pay = order.total_price+order.transit_price
            # 给order添加一条属性order_skus,商品的信息
            order.order_skus = order_skus

            # 分页
            paginator = Paginator(orders,3)
            # 处理分页
            page = int(page)
            if page > paginator.num_pages or page <0:
                page = 1
            # 获取第page页的page对象
            order_page = paginator.page(page)
            num_pages = paginator.num_pages
            if num_pages < 5:
                pages = range(1, num_pages+1)
            elif page <= 3:
                pages = range(1, 6)
            elif num_pages-page <= 2:
                pages = range(num_pages-4, num_pages+1)
            else:
                pages = range(page-2, page+3)

            # 组织上下文
            context = {'order_page': order_page,
                        'pages': pages,
                        'page': 'order'}
        return render(request, 'user_center_order.html', context)


class AddressView(View):
    def get(self, request):
        """显示页面"""
        user = request.user
        address = Address.objects.get_default_address(user)
        return render(request, 'user_center_site.html', {'page': 'addr', 'address': address})

    def post(self, request):
        """增加用户地址"""
        receiver = request.POST.get('receiver')
        addr = request.POST.get('address')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')
        if not all([receiver, addr, phone]):
            return render(request, 'user_center_site.html', {'errmsg':'信息不完整'})
        user = request.user
        # 通过自定义管理类查询默认地址
        address = Address.objects.get_default_address(user)
        is_default = True
        if address:
            is_default = False
        Address.objects.create(
            user=user,
            receiver=receiver,
            addr=addr,
            zip_code=zip_code,
            phone=phone,
            is_default=is_default
        )
        return redirect(reverse('user:address'))


class VerifyCode(View):
    def get(self, request):
        # 引入随机函数模块
        import random
        # 定义变量，用于画面的背景色、宽、高
        bgcolor = (random.randrange(20, 100), random.randrange(
            20, 100), 255)
        width = 100
        height = 32
        # 创建画面对象
        im = Image.new('RGB', (width, height), bgcolor)
        # 创建画笔对象
        draw = ImageDraw.Draw(im)
        # 调用画笔的point()函数绘制噪点
        for i in range(0, 100):
            xy = (random.randrange(0, width), random.randrange(0, height))
            fill = (random.randrange(0, 255), 255, random.randrange(0, 255))
            draw.point(xy, fill=fill)
            # 定义验证码的备选值
        str1 = 'ABCD123EFGHIJK456LMNOPQRS789TUVWXYZ0'
        # 随机选取4个值作为验证码
        rand_str = ''
        for i in range(0, 4):
            rand_str += str1[random.randrange(0, len(str1))]
        # 构造字体对象，ubuntu的字体路径为“/usr/share/fonts/truetype/freefont”
        font = ImageFont.truetype('FreeMono.ttf', 23)
        # 构造字体颜色
        fontcolor = (255, random.randrange(0, 255), random.randrange(0, 255))
        # 绘制4个字
        draw.text((5, 2), rand_str[0], font=font, fill=fontcolor)
        draw.text((25, 2), rand_str[1], font=font, fill=fontcolor)
        draw.text((50, 2), rand_str[2], font=font, fill=fontcolor)
        draw.text((75, 2), rand_str[3], font=font, fill=fontcolor)
        # 释放画笔
        del draw
        # 存入session，用于做进一步验证
        request.session['verifycode'] = rand_str
        # 内存文件操作
        buf = BytesIO()
        # 将图片保存在内存中，文件类型为png
        im.save(buf, 'png')
        # 将内存中的图片数据返回给客户端，MIME类型为图片png
        return HttpResponse(buf.getvalue(), 'image/png')

