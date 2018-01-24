# 自定义存储类
from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client
from django.conf import settings


class FDFSStorage(Storage):
    """自定义文件存储类"""
    def __init__(self,client_conf=None,nginx_url=None):
        if client_conf is None:
            client_conf = settings.FDFS_CLIENT_CONF
        self.client_conf = client_conf
        if nginx_url is None:
            nginx_url = settings.FDFS_NGINX_URL
        self.nginx_url = nginx_url

    def _open(self,name,mode='rb'):
        pass
    def _save(self,name,content):
        # name 上传的文件名
        # content 包含上传文件内容的File对象
        client = Fdfs_client(self.client_conf)
        content = content.read()
        # 使用upload_by_buffer()方法将content上传到FDFS系统，返回值为文件的id
        res = client.upload_by_buffer(content)
        """
        {
            'Group name': group_name,
            'Remote file_id': remote_file_id,   # 返回文件的id
            'Status': 'Upload successed.',   # 是否上传成功
            'Local file name': '',
            'Uploaded size': upload_size,
            'Storage IP': storage_ip
        }
        """
        # 获取文件的上传状态
        if res.get("Status") != "Upload successed.":
            raise Exception("文件上传失败！")
        # 获取文件的id
        file_id = res.get("Remote file_id")
        # 返回文件的id ，django会自动将此id保存在数据库的表中
        return file_id

    def exists(self, name):
        """在save方法前执行，判断文件是否存在"""
        # 返回False则是文件不存在，返回True则文件存在
        return False
    def url(self, name):
        # name是文件的id
        return self.nginx_url+name