from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse
from ..goods.models import GoodsSKU
from django_redis import get_redis_connection


# Create your views here.
class CartAddView(View):
    """"购物车记录的添加"""
    def post(self, request):
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        # 1.接收参数
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 2.检验参数
        # 2.1验证参数的完整性
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 2.２判断商品的id是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品信息错误'})
        # 2.3校验商品的数目是否合法
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 3, 'errmsg': '商品数目非法'})
        if count <= 0:
            return JsonResponse({'res': 3, 'errmsg': '商品数目非法'})
        # 3.业务处理,添加购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 先尝试用redis中获取shu_id的值，判断此商品是否已经在购物车中存在
        cart_count = conn.hget(cart_key, sku_id)
        if cart_count:
            count = int(cart_count)+count
        # 判断商品库存是否足够
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品库存不足'})
        conn.hset(cart_key, sku_id, count)
        # 获取购物车中商品的条目数
        cart_count = conn.hlen(cart_key)
        # 返回应答
        return JsonResponse({'res': 5, 'cart_count': cart_count})


class CartInfoView(View):
    """购物车页面显示"""
    def get(self, request):
        # 获取登录用户
        user = request.user
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        cart_dict = conn.hgetall(cart_key)
        skus = []
        total_count = 0
        total_price = 0
        for sku_id,count in cart_dict.items():
            # 根据商品的id获取商品的sku
            sku = GoodsSKU.objects.get(id=sku_id)
            # 计算商品的小计
            amount = sku.price*int(count)
            sku.count = count
            sku.amount = amount
            skus.append(sku)
            total_count += int(count)
            total_price += amount
        context = {"skus": skus, "total_count": total_count, "total_price": total_price}
        return render(request, 'cart.html', context)


class CartUpdateView(View):
    def post(self,request):
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        # 1.接收参数
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        # 2.检验参数
        # 2.1验证参数的完整性
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 2.２判断商品的id是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品信息错误'})

        # 2.3校验商品的数目是否合法
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 3, 'errmsg': '商品数目非法'})

        if count <= 0:
            return JsonResponse({'res': 3, 'errmsg': '商品数目非法'})
        # 3.业务处理,添加购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        if count >sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品库存不足'})
        # 更新redis中对应的记录
        conn.hset(cart_key, sku_id, count)

        # 计算购物车中的商品总件数
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)
        return JsonResponse({'res': 5, 'total_count': total_count})


class CartDeleteView(View):
    def post(self, request):
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        # 1.接收参数
        sku_id = request.POST.get('sku_id')
        # 2.检验参数
        # 2.1验证参数的完整性
        if not all([sku_id]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 2.２判断商品的id是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在
            return JsonResponse({'res': 2, 'errmsg': '商品信息错误'})
        # 业务处理，删除购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        conn.hdel(cart_key,sku_id)
        # 计算购物车中的商品总件数
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)
        return JsonResponse({'res': 3, 'total_count': total_count})