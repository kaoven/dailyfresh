from django.shortcuts import render, redirect
from django.views.generic import View
from django.core.urlresolvers import reverse
from .models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner, GoodsSKU
from django_redis import get_redis_connection
from ..order.models import OrderGoods
from django.core.paginator import Paginator
# Create your views here.


class IndexView(View):
    """首页"""
    def get(self,request):
        """显示"""
        # 获取商品分类信息
        types = GoodsType.objects.all()
        # 获取首页轮播图信息
        index_banner = IndexGoodsBanner.objects.all().order_by('index')
        # 获取首页促销活动信息
        promotion_banner = IndexPromotionBanner.objects.all().order_by('index')
        # 获取首页分类商品展示信息
        for type in types:
            title_banner = IndexTypeGoodsBanner.objects.filter(type=type,display_type=0).order_by('index')
            image_banner = IndexTypeGoodsBanner.objects.filter(type=type,display_type=1).order_by('index')
            # 为type添加一条属性，保存分类信息
            type.title_banner = title_banner
            type.image_banner = image_banner

        # 获取登陆用户购物车数量信息
        cart_count = 0
        # 获取登陆用户
        user = request.user
        if user.is_authenticated():
            conn = get_redis_connection("default")
            cart_key = "cart_%d"%user.id
            cart_count = conn.hlen(cart_key)

        # 组织上下文
        context = {
            'types':types,
            'index_banner':index_banner,
            'promotion_banner':promotion_banner,
            'cart_count':cart_count
        }

        return render(request, 'index.html', context)


class DetaliView(View):
    def get(self,request,sku_id):
        """显示"""
        # 获取id为sku_id的商品sku
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return redirect(reverse('goods:index'))
        # 获取商品的分类信息
        types= GoodsType.objects.all()
        # 获取同一类商品的最新两个商品
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]

        # 获取商品的评论信息
        order_skus = OrderGoods.objects.filter(sku=sku).exclude(comment='').order_by('-update_time')

        # 获取和sku商品同一spu的其他规格商品
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=sku_id)

        cart_count = 0
        # 获取登陆用户
        user = request.user
        # 判断用户是否登录，如果登录，则记录用户浏览记录，如果未登录，只显示页面
        if user.is_authenticated():
            # 用户已登录，获取登陆用户购物车数量信息
            conn = get_redis_connection("default")
            cart_key = "cart_%d" % user.id
            cart_count = conn.hlen(cart_key)
            # 增加用户历史浏览记录，保存在redis中，用list类型
            history_key = "history_%d" % user.id
            # 先尝试用redis中删除sku_id信息，当用户第二次浏览此商品时，就会删除上一次的浏览信息
            conn.lrem(history_key, 0, sku_id)
            # 保存sku_id到redis中,使用lpush从左边插入
            conn.lpush(history_key,sku_id)
            # 用户历史浏览只保持5个信息
            conn.ltrim(history_key, 0, 4)

        # 组织上下文
        context = {
            'types': types,
            'sku': sku,
            'new_skus': new_skus,
            'order_skus': order_skus,
            'same_spu_skus': same_spu_skus,
            'cart_count': cart_count
        }
        return render(request, 'detail.html', context)


class ListView(View):
    def get(self,request,type_id,page):
        # 获取type_id对应的分类信息
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            return redirect(reverse('goods:index'))
        # 获取商品分类信息
        types = GoodsType.objects.all()
        # 获取排列方式
        sort = request.GET.get('sort','default')
        # sort == ‘default’　按照默商品的id默认排序
        # sort == 'price' 按照商品的价钱排序
        # sort == 'hot　 按照商品的销量排序
        if sort== 'price':
            skus = GoodsSKU.objects.filter(type=type).order_by('price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_by('-sales')
        else:
            sort == 'default'
            skus = GoodsSKU.objects.filter(type=type).order_by('-id')

        # 分页
        paginator = Paginator(skus,1)
        # 处理页码
        page = int(page)
        if page > paginator.num_pages or page<0:
            page=1
        # 获取第page页的page对象
        skus_page = paginator.page(page)
        """
        页码处理：最多只能显示５个页码
        １．总页数不足５页时，全部显示
        ２．当前页是前三页，显示前５页
        ３．当前页时后三页，显示后５页
        ４．其他情况，显示当前页和当前页的前两页，后两页
        """
        num_pages = paginator.num_pages
        if num_pages <= 5:
            pages = range(1,num_pages+1)
        elif page <3:
            pages = range(1,6)
        elif num_pages-page <2:
            pages = range(page-2,page+3)

        # 获取分类的２个新品信息
        new_sku = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]

        cart_count = 0
        # 获取登陆用户
        user = request.user
        if user.is_authenticated():
            # 用户已登录，获取登陆用户购物车数量信息
            conn = get_redis_connection("default")
            cart_key = "cart_%d" % user.id
            cart_count = conn.hlen(cart_key)

        context = {
            'type':type,
            'types':types,
            'skus_page':skus_page,
            'pages':pages,
            'new_sku':new_sku,
            'cart_count':cart_count,
            'sort':sort,
        }

        return render(request,'list.html', context)