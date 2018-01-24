from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.views.generic import View
from django.http import JsonResponse
from django.db import transaction

from ..user.models import Address
from ..goods.models import GoodsSKU
from ..order.models import OrderInfo, OrderGoods

from django_redis import get_redis_connection
from datetime import datetime
# Create your views here.


class OrderPlaceView(View):
    """显示订单页面内容"""
    def post(self, request):
        # 获取要购买的商品的id
        sku_ids = request.POST.getlist('sku_id')
        if not all([sku_ids]):
            # 跳转到购物车页面
            return redirect(reverse('cart:show'))
        # 业务处理，页面信息获取
        # 获取用户的收货地址
        user = request.user
        addrs = Address.objects.filter(user=user)

        # 从购物车中获取商品信息
        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id
        skus = []
        total_count = 0
        total_price = 0
        for sku_id in sku_ids:
            # 根据商品id获取商品信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 从购物车获取商品的数量
            count = conn.hget(cart_key,sku_id)
            # 计算商品的小计
            amount = sku.price*int(count)
            sku.count = count
            sku.amount = amount
            skus.append(sku)
            # 累加商品的数量和总价
            total_count += int(count)
            total_price += amount
        # 运费
        transit_price = 10
        # 总运费
        total_pay = total_price+transit_price

        # 组织上下文
        # 因为getlist获取的数据是列表格式，所以转换成字符串
        sku_ids = ','.join(sku_ids)
        context = {
            'total_count': total_count,
            'total_price': total_price,
            'transit_price': transit_price,
            'total_pay': total_pay,
            'addrs': addrs,
            'skus': skus,
            'sku_ids': sku_ids
        }
        return render(request, 'place_order.html', context)


# 订单创建流程
    # 接收参数
    # 校验参数
    # 组织订单信息

# /order/commit
# 前段采用ajax请求
# 需要接收的参数，收货地址的id,支付方式，需要购买的商品的id
class OrderCommitView(View):
    """订单创建"""
    # 使用@transaction.Atomic给视图添加一个mysql事务
    @transaction.atomic
    def post(self, request):
        """订单创建"""
        # 验证用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        # 接收参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 验证地址id
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '用户地址不存'})

        # 验证支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 3, 'errmsg': '支付方式错误'})

        # 组织订单信息
        order_id = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)
        transit_price = 10
        total_count = 0
        total_price = 0

        # 在往数据库更新数据时，设置保存点，当后面的sql语句执行出错时，回滚到此保存点
        sid = transaction.savepoint()
        try:
            # 向df_order_info中添加一条数据
            order = OrderInfo.objects.create(
                order_id=order_id,
                user=user,
                addr=addr,
                pay_method=pay_method,
                total_count=total_count,
                total_price=total_price,
                transit_price=transit_price
            )

            # 遍历向df_order_goods中添加数据
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id

            # 把sku_ids转变成列表
            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                try:
                    # sku = GoodsSKU.objects.get(id=sku_id)
                    # todo 使用悲观锁，防止订单并发问题，造成数据的处理不准确
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    # 当商品不存在时，数据库的操作需要回滚到保存点
                    transaction.savepoint_rollback(sid)
                    return JsonResponse({'res': 4, 'errmsg': '商品不存在'})

                # 从redis的购物车中获取商品的数量
                count = conn.hget(cart_key, sku_id)

                # 判断库存是否足够，防止在添加到购物车到提交订单的过程中库存数量发生变化
                if int(count) > sku.stock:
                    # 当商品库存不足时，需要把数据库的操作回滚到设置的保存点
                    transaction.savepoint_rollback(sid)
                    return JsonResponse({'res': 6, 'errmsg': '商品库存不足'})

                # 向df_order_goods中添加一条数据
                OrderGoods.objects.create(
                    order=order,
                    sku=sku,
                    count=count,
                    price=sku.price,
                )

                # 减少商品的库存量，增加商品的销量
                sku.stock -= int(count)
                sku.sales += int(count)
                sku.save()
                total_count += int(count)
                total_price += sku.price*int(count)

            # 更新df_order_info中的商品总数和商品总价
            order.total_price = total_price
            order.total_count = total_count
            order.save()

        except Exception as e:
            # 只要数据库操作出现问题时，都回滚到保存点
            transaction.savepoint_rollback(sid)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})

        # 删除购物车中的记录,*sku_ids是对列表进行解包
        conn.hdel(cart_key, *sku_ids)
        return JsonResponse({'res': 5, 'message': '订单创建成功'})


# /order/pay
# 采用ajax　post 请求
class OrderPayView(View):
    """订单支付"""
    def post(self, request):
        """订单支付"""
        # 验证用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 获取订单id
        order_id = request.POST.get('user_id')
        # 参数校验
        if not all([order_id]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 验证用户订单信息是否正确
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return  JsonResponse({'res': 2, 'errmsg': '订单信息错误'})

        # 业务处理，调用支付宝下单支付接口
        pass